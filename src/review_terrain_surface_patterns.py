"""Descriptive terrain strata of surface changes; run with QGIS Python."""
import csv
from pathlib import Path
import numpy as np
from osgeo import gdal

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/processed/multiyear_2023_2025'
OUT=BASE/'surface_patterns'


def main():
    gdal.UseExceptions()
    ref=gdal.Open(str(BASE/'s2_NDMI_change_median_3years.tif'))
    def read(path):
        ds=gdal.Open(str(path))
        if (ds.RasterXSize,ds.RasterYSize,ds.GetGeoTransform(),ds.GetProjection())!=(ref.RasterXSize,ref.RasterYSize,ref.GetGeoTransform(),ref.GetProjection()):
            raise RuntimeError('Grid mismatch')
        a=ds.ReadAsArray().astype(float);nd=ds.GetRasterBand(1).GetNoDataValue()
        if nd is not None:a[a==nd]=np.nan
        return a
    optical=read(BASE/'s2_NDMI_change_median_3years.tif')
    vv=read(BASE/'s1_vv_change_median_3years.tif')
    vh=read(BASE/'s1_vh_change_median_3years.tif')
    levels={name:read(BASE/(filename+'.tif')) for name,filename in {
        'pre_ndmi':'s2_NDMI_pre_median_3years',
        'post_ndmi':'s2_NDMI_post_median_3years',
        'pre_ndvi':'s2_NDVI_pre_median_3years',
        'post_ndvi':'s2_NDVI_post_median_3years',
        'ndvi_change':'s2_NDVI_change_median_3years'}.items()}
    slope=read(ROOT/'data/processed/terrain_pilot/slope_degrees.tif')
    twi=read(ROOT/'data/processed/terrain_pilot/twi.tif')
    mask=read(BASE/'sensitivity/mask_scl_water_at_least_2_years.tif')
    common=(mask==1)&np.isfinite(optical)&np.isfinite(vv)&np.isfinite(vh)&np.isfinite(slope)&np.isfinite(twi)
    for value in levels.values():common &= np.isfinite(value)
    if not common.any():raise RuntimeError('No common support')
    rows=[]
    for name,terrain in [('slope_degrees',slope),('twi',twi)]:
        q1,q2=np.quantile(terrain[common],[1/3,2/3])
        labels=np.digitize(terrain,[q1,q2],right=True)
        total=0
        for group in range(3):
            selected=common&(labels==group);n=int(selected.sum());total+=n
            if not n:raise RuntimeError('Empty terrain group')
            rows.append(dict(terrain=name,stratum=['lower_third','middle_third','upper_third'][group],
                first_boundary=float(q1),second_boundary=float(q2),pixels=n,area_km2=n*.0009,
                median_terrain=float(np.median(terrain[selected])),median_ndmi_change=float(np.median(optical[selected])),
                median_vv_change_db=float(np.median(vv[selected])),median_vh_change_db=float(np.median(vh[selected])),
                fraction_ndmi_vv_both_positive=float(np.mean((optical[selected]>0)&(vv[selected]>0))),
                fraction_ndmi_vv_both_negative=float(np.mean((optical[selected]<0)&(vv[selected]<0)))))
            rows[-1].update({name+'_median':float(np.median(value[selected])) for name,value in levels.items()})
        assert total==int(common.sum())
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/'terrain_strata_statistics.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (OUT/'terrain_strata_notes.txt').write_text(
        'Exploratory thirds use local quantiles on identical common support across NDMI, VV, VH, slope and TWI, '
        'after recurrent SCL-water exclusion. Lower third <= first boundary; middle >first and <=second; upper >second. '
        'Ties can make counts unequal. Boundaries are descriptive, not hydrogeological thresholds or suitability classes. '
        'TWI missing/edge-flagged pixels are excluded. No independence, significance, causal relation or validation claimed. '
        'Pre/post levels are medians of multi-year seasonal medians; change is the median of within-year changes. '
        'Their differences need not equal the summarized change. Land use and irrigation remain confounders. No combined score or weights.\n',encoding='utf-8')
    print('Common valid pixels:',int(common.sum()))
    for row in rows:print(row)


if __name__=='__main__':main()
