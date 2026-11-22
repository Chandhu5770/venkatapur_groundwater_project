"""Offline paired May optical diagnostics; run with QGIS Python."""
import csv
import json
from pathlib import Path
import numpy as np
from osgeo import gdal, ogr, osr

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'data/processed/rainfall_context'


def main():
    gdal.UseExceptions()
    manifest = json.loads((ROOT/'data/processed/s2_seasons_2025/seasonal_manifest.json').read_text())
    observations = [o for s in manifest['seasons'].values() for o in s['observations'] if o['date'].startswith('2025-05-')]
    observations.sort(key=lambda o: o['date'])
    if len(observations) != 2:
        raise RuntimeError('This paired diagnostic requires exactly two selected May observations')
    ref = gdal.Open(str(ROOT/'data/raw/sentinel/s2/seasons_2025'/observations[0]['item_id']/'SCL.tif'))
    h, w = ref.RasterYSize, ref.RasterXSize
    mem = gdal.GetDriverByName('MEM').Create('', w, h, 1, gdal.GDT_Byte)
    mem.SetGeoTransform(ref.GetGeoTransform()); mem.SetProjection(ref.GetProjection())
    vector = ogr.Open(str(ROOT/'data/reference/venkatapur_initial_study_area_5km.geojson'))
    gdal.RasterizeLayer(mem, [1], vector.GetLayer(0), burn_values=[1])
    inside = mem.ReadAsArray() == 1
    dates = []
    for observation in observations:
        arrays, valid = {}, inside.copy()
        folder = ROOT/'data/raw/sentinel/s2/seasons_2025'/observation['item_id']
        for entry in observation['files']:
            band = entry['band']; ds = gdal.Open(str(folder/(band+'.tif')))
            if ds.GetGeoTransform()!=ref.GetGeoTransform() or ds.GetProjection()!=ref.GetProjection():
                raise RuntimeError('Grid mismatch')
            raw = ds.ReadAsArray(); meta = entry['scale_offset']
            valid &= raw != meta.get('nodata', 0)
            arrays[band] = raw if band == 'SCL' else raw.astype(float)*meta['scale']+meta['offset']
        scl = arrays['SCL']
        cloud = np.pad(np.isin(scl, [2,3,7,8,9,10]), 3)
        dilated = np.zeros((h,w), dtype=bool)
        for dy in range(-3,4):
            for dx in range(-3,4):
                if dx*dx+dy*dy<=9:
                    dilated |= cloud[3+dy:3+dy+h,3+dx:3+dx+w]
        valid &= ~np.isin(scl,manifest['scl_mask']) & ~dilated
        values = {}
        for name, a, b in [('NDMI','B08','B11'),('NDVI','B08','B04'),('MNDWI','B03','B11')]:
            first, second = arrays[a], arrays[b]
            good = valid & (first>=0) & (second>=0) & (first+second>1e-6)
            value = np.full((h,w), np.nan)
            np.divide(first-second,first+second,out=value,where=good)
            values[name] = value
        dates.append((values,scl))
    common = inside.copy()
    for values, scl in dates:
        for value in values.values(): common &= np.isfinite(value)
    masks = {'paired_valid':common}
    masks['exclude_scl_water_either_date'] = common & ~((dates[0][1]==6)|(dates[1][1]==6))
    masks['exclude_broad_water_either_date'] = masks['exclude_scl_water_either_date'] & ~((dates[0][0]['MNDWI']>0)|(dates[1][0]['MNDWI']>0))
    rows = []
    for scenario, mask in masks.items():
        for name in ['NDMI','NDVI','MNDWI']:
            a,b = [v[name][mask] for v,scl in dates]
            if not len(a): raise RuntimeError('Empty scenario')
            rows.append(dict(scenario=scenario,index=name,first_date=observations[0]['date'],second_date=observations[1]['date'],
                paired_pixels=len(a),fraction_planning_circle=len(a)/inside.sum(),first_median=float(np.median(a)),
                second_median=float(np.median(b)),median_pixel_change=float(np.median(b-a)),
                fraction_positive_change=float(np.mean(b>a))))
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/'may_paired_optical_statistics.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    (OUT/'may_optical_interpretation.txt').write_text(
        'Paired common pixels, same 20 m grid and seasonal masks/scaling. Changes are second minus first at each pixel. '
        'Water exclusions are sensitivity scenarios, not confirmed water maps. Different scenarios retain different populations. '
        'Two dates cannot establish a rainfall response or distinguish crop, irrigation, soil or atmospheric effects. '
        'No significance tests, groundwater scores, weights or recharge estimates. '
        'Read alongside may_acquisition_rainfall_context.csv; rainfall windows exclude acquisition day.\n',encoding='utf-8')
    for row in rows:
        if row['index']=='NDMI': print(row)


if __name__=='__main__': main()
