"""Offline common-pixel May radar diagnostics. Run with QGIS Python."""
import csv
import json
from pathlib import Path
import numpy as np
from osgeo import gdal, ogr

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'data/processed/rainfall_context'


def main():
    gdal.UseExceptions()
    manifest = json.loads((ROOT/'data/processed/s1_seasons_2025/radar_manifest.json').read_text())
    observations = sorted([o for s in manifest['seasons'].values() for o in s['observations']
                           if o['date'].startswith('2025-05-')], key=lambda o:o['date'])
    if len(observations)<2: raise RuntimeError('At least two radar dates required')
    arrays, ref = {}, None
    for observation in observations:
        folder = ROOT/'data/raw/sentinel/s1/seasons_2025'/observation['id']
        for pol in ['vv','vh']:
            ds = gdal.Open(str(folder/(pol+'_30m.tif')))
            if ref is None: ref = ds
            if (ds.RasterXSize,ds.RasterYSize,ds.GetGeoTransform(),ds.GetProjection()) != (ref.RasterXSize,ref.RasterYSize,ref.GetGeoTransform(),ref.GetProjection()):
                raise RuntimeError('Radar grid mismatch')
            values = ds.ReadAsArray().astype(float)
            nodata = ds.GetRasterBand(1).GetNoDataValue()
            valid = np.isfinite(values)&(values>0)
            if nodata is not None: valid &= values!=nodata
            db = np.full(values.shape,np.nan)
            db[valid] = 10*np.log10(values[valid])
            arrays[observation['date'],pol] = db
    mem = gdal.GetDriverByName('MEM').Create('',ref.RasterXSize,ref.RasterYSize,1,gdal.GDT_Byte)
    mem.SetGeoTransform(ref.GetGeoTransform()); mem.SetProjection(ref.GetProjection())
    vector = ogr.Open(str(ROOT/'data/reference/venkatapur_initial_study_area_5km.geojson'))
    gdal.RasterizeLayer(mem,[1],vector.GetLayer(0),burn_values=[1])
    inside = mem.ReadAsArray()==1
    common = inside.copy()
    for a in arrays.values(): common &= np.isfinite(a)
    if not common.any(): raise RuntimeError('No common valid pixels')
    rows = []
    for earlier,later in zip(observations,observations[1:]):
        for pol in ['vv','vh']:
            a,b = arrays[earlier['date'],pol][common],arrays[later['date'],pol][common]
            rows.append(dict(first_date=earlier['date'],second_date=later['date'],polarization=pol,
                paired_pixels=int(common.sum()),fraction_planning_circle=float(common.sum()/inside.sum()),
                first_median_db=float(np.median(a)),second_median_db=float(np.median(b)),
                median_pixel_change_db=float(np.median(b-a)),fraction_positive_change=float(np.mean(b>a))))
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/'may_paired_radar_statistics.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (OUT/'may_radar_interpretation.txt').write_text(
        'Common finite positive pixels across every selected May VV/VH acquisition; 30 m gamma0 intensity converted with 10log10. '
        'Consecutive-date differences use identical spatial support. Same platform/orbit/pass selection inherited from radar_manifest.json. '
        'No water/crop exclusion in these radar statistics. Roughness, crops, irrigation, surface water and geometry affect radar brightness. '
        'Only three dates: no causal rainfall response, statistical independence, groundwater inference or MCDA weights claimed. '
        'Compare with prior-complete-UTC-day rainfall context; no exact rolling-hour windows. No network access.\n',encoding='utf-8')
    for row in rows: print(row)


if __name__=='__main__': main()
