"""Offline common-pixel NDMI/NDVI change comparison; QGIS Python."""
import csv
from pathlib import Path
import numpy as np
from osgeo import gdal
from scipy.stats import spearmanr

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
    ndmi=read(BASE/'s2_NDMI_change_median_3years.tif')
    ndvi=read(BASE/'s2_NDVI_change_median_3years.tif')
    rows=[]
    for scenario in ['all_complete','scl_water_at_least_2_years','broad_water_at_least_2_years']:
        mask=read(BASE/'sensitivity'/f'mask_{scenario}.tif')
        common=(mask==1)&np.isfinite(ndmi)&np.isfinite(ndvi)
        n=int(common.sum())
        if n<2:raise RuntimeError('Insufficient common support')
        for label,epsilon in [('strict_sign',0.),('near_zero_sensitivity',.02)]:
            a,b=ndmi[common],ndvi[common]
            categories=[(a>epsilon)&(b>epsilon),(a < -epsilon)&(b < -epsilon),
                        (a>epsilon)&(b < -epsilon),(a < -epsilon)&(b>epsilon)]
            counts=[int(c.sum()) for c in categories]
            counts.append(n-sum(counts))
            assert sum(counts)==n and min(counts)>=0
            for category,count in zip(['both_increase','both_decrease','ndmi_up_ndvi_down','ndmi_down_ndvi_up','one_or_both_near_zero'],counts):
                rows.append(dict(mask_scenario=scenario,threshold_scenario=label,epsilon_each_index=epsilon,
                    category=category,pixels=count,common_pixels=n,fraction_common=count/n,
                    spearman_all_common=float(spearmanr(a,b).statistic)))
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/'optical_confounding_statistics.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (OUT/'optical_confounding_notes.txt').write_text(
        'NDMI and NDVI median within-year seasonal changes, 2023-2025, on identical common valid pixels per mask. '
        'Both indices share NIR and are not independent evidence. Spatial autocorrelation also limits inference. '
        'Correlation and same-sign changes do not identify crops/irrigation, establish causation or validate groundwater potential. '
        'Near-zero +/-0.02 for each index is an arbitrary sensitivity assumption, not measurement uncertainty. '
        'All fractions use complete common support, including near-zero category. Water exclusions are provisional. '
        'No labels, significance tests, supervised ML, weights or combined score.\n',encoding='utf-8')
    for row in rows:
        if row['mask_scenario']=='scl_water_at_least_2_years':print(row)


if __name__=='__main__':main()
