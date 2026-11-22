"""Common-support drainage-density threshold sensitivity; QGIS Python."""
import csv
from itertools import combinations
from pathlib import Path
import numpy as np
from osgeo import gdal
from scipy.stats import spearmanr

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/processed/terrain_pilot/drainage_diagnostics'


def main():
    gdal.UseExceptions();arrays={};ref=None
    for key in ['0p25','0p5','1p0']:
        ds=gdal.Open(str(BASE/f'density_{key}_km_per_km2.tif'))
        grid=(ds.RasterXSize,ds.RasterYSize,ds.GetGeoTransform(),ds.GetProjection())
        if ref is None:ref=grid
        if grid!=ref:raise RuntimeError('Grid mismatch')
        a=ds.ReadAsArray().astype(float);a[a==ds.GetRasterBand(1).GetNoDataValue()]=np.nan
        arrays[key]=a
    common=np.logical_and.reduce([np.isfinite(a) for a in arrays.values()])
    if not common.any():raise RuntimeError('No common density support')
    rows=[]
    for first,second in combinations(arrays,2):
        a,b=arrays[first][common],arrays[second][common]
        qa,qb=np.quantile(a,2/3),np.quantile(b,2/3)
        high_a,high_b=a>=qa,b>=qb
        union=(high_a|high_b).sum()
        rows.append(dict(first_threshold_km2=first.replace('p','.'),second_threshold_km2=second.replace('p','.'),
            common_pixels=int(common.sum()),common_area_km2=float(common.sum()*.0009),
            first_median_density=float(np.median(a)),second_median_density=float(np.median(b)),
            spearman_rank_correlation=float(spearmanr(a,b).statistic),
            first_upper_third_cutoff=float(qa),second_upper_third_cutoff=float(qb),
            upper_third_jaccard=float((high_a&high_b).sum()/union),
            fraction_upper_third_membership_changed=float(np.mean(high_a!=high_b))))
    with (BASE/'threshold_sensitivity.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (BASE/'threshold_sensitivity_notes.txt').write_text(
        'Compare 1 km neighbourhood density under three contributing-area thresholds, on common valid density pixels. '
        'Upstream-uncertain neighbourhoods remain excluded. Upper-third cutoffs are local quantiles, ties included; not suitability classes. '
        'Jaccard is intersection/union of upper-third membership, not predictive accuracy. '
        'Rank correlation is descriptive; no independent observations or significance claims. '
        'Density magnitude and ordering depend on threshold. No groundwater direction, weights or validation established.\n',encoding='utf-8')
    for row in rows:print(row)


if __name__=='__main__':main()
