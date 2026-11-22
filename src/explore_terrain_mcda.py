"""Named exploratory terrain-setting scenarios, never groundwater predictions."""
import csv
import json
import os
from itertools import combinations
from pathlib import Path
import numpy as np
from osgeo import gdal
from scipy.stats import rankdata, spearmanr

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/processed'
OUT=DATA/'terrain_scenarios'
SCENARIOS={'slope_emphasis':(.75,.25),'balanced_terrain':(.5,.5),'convergence_emphasis':(.25,.75),
           'slope_only':(1.,0.),'twi_only':(0.,1.)}


def clipped_scale(values):
    low,high=np.quantile(values,[.02,.98])
    if high<=low:raise RuntimeError('Insufficient spread for alternative normalization')
    return np.clip((values-low)/(high-low),0,1),float(low),float(high)


def main():
    global _qgis_app
    gdal.UseExceptions();OUT.mkdir(parents=True,exist_ok=True)
    ref=gdal.Open(str(DATA/'terrain_pilot/slope_degrees.tif'))
    def read(path):
        ds=gdal.Open(str(path))
        if (ds.RasterXSize,ds.RasterYSize,ds.GetGeoTransform(),ds.GetProjection())!=(ref.RasterXSize,ref.RasterYSize,ref.GetGeoTransform(),ref.GetProjection()):
            raise RuntimeError('Grid mismatch')
        a=ds.ReadAsArray().astype(float);nd=ds.GetRasterBand(1).GetNoDataValue()
        if nd is not None:a[a==nd]=np.nan
        return a
    slope=read(DATA/'terrain_pilot/slope_degrees.tif');twi=read(DATA/'terrain_pilot/twi.tif')
    edge=read(DATA/'terrain_pilot/edge_underestimate_flag.tif')
    mask=read(DATA/'multiyear_2023_2025/sensitivity/mask_scl_water_at_least_2_years.tif')
    valid=np.isfinite(slope)&np.isfinite(twi)&(edge==0)&(mask==1)
    n=int(valid.sum())
    if n<2:raise RuntimeError('Insufficient common support')
    # Average tied ranks; ranks are relative to this support, not physical thresholds.
    low_slope=1-(rankdata(slope[valid],method='average')-1)/(n-1)
    convergence=(rankdata(twi[valid],method='average')-1)/(n-1)
    scaled_slope,slope_low,slope_high=clipped_scale(slope[valid])
    scaled_twi,twi_low,twi_high=clipped_scale(twi[valid])
    normalizations={'percentile_rank':(low_slope,convergence),
                    'clipped_linear':(1-scaled_slope,scaled_twi)}
    scores={};summary=[];high={}
    def write(name,values):
        a=np.full(valid.shape,-9999,dtype='float32');a[valid]=values
        ds=gdal.GetDriverByName('GTiff').Create(str(OUT/(name+'.tif')),ref.RasterXSize,ref.RasterYSize,1,gdal.GDT_Float32,options=['COMPRESS=DEFLATE'])
        ds.SetGeoTransform(ref.GetGeoTransform());ds.SetProjection(ref.GetProjection())
        ds.GetRasterBand(1).SetNoDataValue(-9999);ds.GetRasterBand(1).WriteArray(a);ds=None
    specifications={}
    for normalization,(first,second) in normalizations.items():
      for scenario,(ws,wt) in SCENARIOS.items():
        name=scenario if normalization=='percentile_rank' else scenario+'_clipped_linear'
        specifications[name]={'normalization':normalization,'slope_weight':ws,'twi_weight':wt}
        score=ws*first+wt*second
        if not (np.isfinite(score).all() and (score>=0).all() and (score<=1).all()):raise RuntimeError('Invalid scores')
        scores[name]=score;high[name]=score>=np.quantile(score,.8)
        write(name,score)
        summary.append(dict(scenario=name,normalization=normalization,slope_weight=ws,twi_weight=wt,valid_pixels=n,
                            valid_area_km2=n*.0009,median_score=float(np.median(score)),upper_fifth_pixels=int(high[name].sum())))
    comparisons=[]
    for a,b in combinations(scores,2):
        comparisons.append(dict(first=a,second=b,spearman_rank_correlation=float(spearmanr(scores[a],scores[b]).statistic),
            upper_fifth_jaccard=float((high[a]&high[b]).sum()/(high[a]|high[b]).sum()),
            fraction_membership_changed=float(np.mean(high[a]!=high[b]))))
    for filename,rows in [('scenario_summary.csv',summary),('weight_sensitivity.csv',comparisons)]:
        with (OUT/filename).open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    membership=sum(high[name].astype(int) for name in ['slope_emphasis','balanced_terrain','convergence_emphasis'])
    write('upper_fifth_scenario_count',membership)
    notes='''Exploratory terrain-setting MCDA only. No scenario is a validated groundwater-potential map.
Three named hypothetical weights compare slope emphasis, equal terrain weights and convergence emphasis, plus slope-only and TWI-only omission checks. None is selected as final or default.
Lower slope and higher TWI are conditional runoff/convergence hypotheses. They do not establish aquifer storage, infiltration capacity or borewell success.
Both inputs share a DSM and are correlated, so this is not two independent confirmations. TWI already incorporates slope.
Normalize each input using average-tied percentile ranks on identical common support. Score = stated slope weight * inverse slope rank + stated TWI weight * TWI rank.
Alternative clipped-linear normalization scales physical values between their local 2nd and 98th percentiles and clips outside that range; slope is inverted. These clipping choices are arbitrary sensitivity assumptions, not calibrated physical thresholds.
Support excludes upstream-edge estimates, missing terrain, recurrent SCL-water and unavailable optical mask support. This optical-dependent domain is a limitation; it is not a terrain completeness map.
Upper fifth means >= local 80th percentile, ties included; not an absolute favorable class. Scenario count is sensitivity, not confidence or probability.
upper_fifth_scenario_count refers only to the original three percentile-rank weight scenarios, not the expanded ten-scenario set.
Scores are local, relative and domain-dependent; no comparison to other areas or direct groundwater interpretation. No geology, recharge, rainfall spatial score, NDMI or radar included.
Rainfall remains May-only regional context. Surface evidence retains its separate unresolved directions. Final combined weights remain unset.
'''
    (OUT/'README.txt').write_text(notes,encoding='utf-8')
    (OUT/'scenario_manifest.json').write_text(json.dumps({'scenarios':specifications,'pixels':n,
        'clipped_linear_limits':{'slope_degrees':[slope_low,slope_high],'twi':[twi_low,twi_high]},
        'slope_twi_spearman':float(spearmanr(slope[valid],twi[valid]).statistic),
        'interpretation':notes,'final_combined_weights_set':False},indent=2),encoding='utf-8')
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    from qgis.core import QgsApplication,QgsProject,QgsRasterLayer,QgsColorRampShader,QgsRasterShader,QgsSingleBandPseudoColorRenderer,QgsReferencedRectangle
    from qgis.PyQt.QtGui import QColor
    _qgis_app=QgsApplication([],False);_qgis_app.initQgis();project=QgsProject.instance()
    project.setTitle('Exploratory terrain-setting scenarios; not groundwater potential')
    for name in scores:
        layer=QgsRasterLayer(str(OUT/(name+'.tif')),name+' - terrain setting only')
        if not layer.isValid():raise RuntimeError('Invalid scenario layer')
        ramp=QgsColorRampShader();ramp.setColorRampType(QgsColorRampShader.Interpolated)
        ramp.setColorRampItemList([QgsColorRampShader.ColorRampItem(v,QColor(c),str(v)) for v,c in [(0,'#f7fbff'),(.5,'#6baed6'),(1,'#08306b')]])
        shader=QgsRasterShader(0,1);shader.setRasterShaderFunction(ramp)
        renderer=QgsSingleBandPseudoColorRenderer(layer.dataProvider(),1,shader);renderer.setClassificationMin(0);renderer.setClassificationMax(1)
        layer.setRenderer(renderer);project.addMapLayer(layer)
        project.layerTreeRoot().findLayer(layer.id()).setItemVisibilityChecked(name=='slope_emphasis')
    project.setCrs(layer.crs());project.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(layer.extent(),layer.crs()))
    path=OUT/'terrain_scenarios_review.qgz'
    if not project.write(str(path)):raise RuntimeError('Project write failed')
    project.clear()
    for row in comparisons:print(row)
    print('Valid common pixels:',n,'; final combined weights remain unset.')


if __name__=='__main__':main()
