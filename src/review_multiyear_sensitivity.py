"""Compare provisional water/vegetation exclusions on 2023-2025 evidence.

Run with QGIS Python. No trained classifier, groundwater score or final weights.
"""
import csv
import json
from pathlib import Path

import numpy as np
from osgeo import gdal
from scipy.stats import spearmanr

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/processed'
OUT=DATA/'multiyear_2023_2025/sensitivity'
YEARS=[2023,2024,2025]


def main():
    gdal.UseExceptions()
    OUT.mkdir(parents=True,exist_ok=True)
    ref=gdal.Open(str(DATA/'terrain_pilot/edge_underestimate_flag.tif'))
    gt=ref.GetGeoTransform()
    w,h=ref.RasterXSize,ref.RasterYSize
    bounds=[gt[0],gt[3]-h*30,gt[0]+w*30,gt[3]]
    inside=ref.ReadAsArray()!=ref.GetRasterBand(1).GetNoDataValue()

    def read(path,align=False):
        source=gdal.Open(str(path))
        if align:
            original=source.ReadAsArray()
            valid=original!=source.GetRasterBand(1).GetNoDataValue()
            support=gdal.GetDriverByName('MEM').Create('',source.RasterXSize,source.RasterYSize,1,gdal.GDT_Byte)
            support.SetGeoTransform(source.GetGeoTransform())
            support.SetProjection(source.GetProjection())
            support.GetRasterBand(1).WriteArray(valid.astype('uint8'))
            fraction=gdal.Warp('',support,format='MEM',dstSRS='EPSG:32644',outputBounds=bounds,
                               width=w,height=h,resampleAlg='average',outputType=gdal.GDT_Float32).ReadAsArray()
            source=gdal.Warp('',source,format='MEM',dstSRS='EPSG:32644',outputBounds=bounds,
                             width=w,height=h,resampleAlg='average',dstNodata=-9999)
        assert source.GetGeoTransform()==gt and source.GetProjection()==ref.GetProjection()
        array=source.ReadAsArray().astype(float)
        array[array==source.GetRasterBand(1).GetNoDataValue()]=np.nan
        if align:
            array[fraction<.999]=np.nan
        array[~inside]=np.nan
        return array

    def write(name,array):
        ds=gdal.GetDriverByName('GTiff').Create(str(OUT/(name+'.tif')),w,h,1,gdal.GDT_Float32,
                                               options=['COMPRESS=DEFLATE','TILED=YES'])
        ds.SetGeoTransform(gt)
        ds.SetProjection(ref.GetProjection())
        ds.GetRasterBand(1).SetNoDataValue(-9999)
        ds.GetRasterBand(1).WriteArray(np.where(inside&np.isfinite(array),array,-9999).astype('float32'))
        ds=None

    # Each year's flag uses either season; persistence requires three known years.
    annual_scl,annual_broad,annual_veg=[],[],[]
    for year in YEARS:
        arrays={}
        for season in ['pre','post']:
            for method in ['scl','broad']:
                arrays[season+'_'+method]=read(DATA/f's2_seasons_{year}'/(season+'_'+method+'_water_frequency.tif'),True)
            arrays[season+'_ndvi']=read(DATA/f's2_seasons_{year}'/(season+'_NDVI_median.tif'),True)
        for method,stack in [('scl',annual_scl),('broad',annual_broad)]:
            a,b=arrays['pre_'+method],arrays['post_'+method]
            known=np.isfinite(a)&np.isfinite(b)
            stack.append(np.where(known,((a>=.5)|(b>=.5)).astype(float),np.nan))
        a,b=arrays['pre_ndvi'],arrays['post_ndvi']
        annual_veg.append(np.where(np.isfinite(a)&np.isfinite(b),((a>.3)|(b>.3)).astype(float),np.nan))

    def frequency(stack):
        stack=np.stack(stack)
        count=np.isfinite(stack).sum(axis=0)
        total=np.nansum(stack,axis=0)
        return np.where(count==3,total/3,np.nan)

    scl,broad,vegetation=map(frequency,[annual_scl,annual_broad,annual_veg])
    for name,a in [('scl_water_year_frequency',scl),('broad_water_year_frequency',broad),('vegetation_year_frequency',vegetation)]:
        write(name,a)
    multi=DATA/'multiyear_2023_2025'
    values={'ndmi_change':read(multi/'s2_NDMI_change_median_3years.tif'),
            'ndvi_change':read(multi/'s2_NDVI_change_median_3years.tif'),
            'vv_change_db':read(multi/'s1_vv_change_median_3years.tif'),
            'vh_change_db':read(multi/'s1_vh_change_median_3years.tif')}
    scenarios={
        'all_complete':inside,
        'scl_water_at_least_2_years':inside&np.isfinite(scl)&(scl<2/3),
        'broad_water_at_least_2_years':inside&np.isfinite(broad)&(broad<2/3),
        'scl_and_vegetation_at_least_2_years':inside&np.isfinite(scl)&np.isfinite(vegetation)&(scl<2/3)&(vegetation<2/3)}
    rows=[]
    for scenario,mask in scenarios.items():
        write('mask_'+scenario,np.where(inside,mask.astype(float),np.nan))
        for name,a in values.items():
            good=mask&np.isfinite(a)
            x=a[good]
            rows.append({'scenario':scenario,'indicator':name,'pixels':int(x.size),'area_km2':float(x.size*.0009),
                'median_change':float(np.median(x)) if x.size else None,
                'p25_change':float(np.percentile(x,25)) if x.size else None,
                'p75_change':float(np.percentile(x,75)) if x.size else None,
                'positive_change_fraction':float((x>0).mean()) if x.size else None})
        write('NDMI_change_'+scenario,np.where(mask,values['ndmi_change'],np.nan))
    correlations=[]
    for scenario,mask in scenarios.items():
        for first,second in [('ndvi_change','ndmi_change'),('vv_change_db','ndmi_change'),('vv_change_db','ndvi_change')]:
            good=mask&np.isfinite(values[first])&np.isfinite(values[second])
            a,b=values[first][good],values[second][good]
            informative=a.size>=3 and np.ptp(a)>1e-10 and np.ptp(b)>1e-10
            correlations.append({'scenario':scenario,'first':first,'second':second,'pixels':int(a.size),
                'pearson':float(np.corrcoef(a,b)[0,1]) if informative else None,
                'spearman':float(spearmanr(a,b).statistic) if informative else None})
    for filename,records in [('scenario_statistics.csv',rows),('scenario_correlations.csv',correlations)]:
        with (OUT/filename).open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
    report={'years':YEARS,'water_rule':'Annual flag: seasonal water frequency >=0.5 in either season. Exclude annual flag in >=2 of 3 years. All 3 years require known seasonal frequencies.',
        'vegetation_rule':'Annual NDVI >0.3 in either season, recurring in >=2 of 3 years. Sensitivity assumption only, not a crop/irrigation classifier.',
        'alignment':'30 m terrain grid; optical flags/indices area-averaged with >=99.9% valid source support.',
        'caveats':'Subset statistics change with spatial exclusions; this does not establish causation or independent validation. Water-frequency labels are provisional. Missing flags excluded from exclusion scenarios. No weights or combined score.',
        'statistics':rows,'correlations':correlations}
    (OUT/'sensitivity_manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    lines=['2023-2025 water/vegetation sensitivity review','',report['water_rule'],report['vegetation_rule'],'']
    for row in rows:
        if row['indicator']=='ndmi_change':
            lines.append(f"{row['scenario']}: {row['pixels']} pixels; median NDMI change={row['median_change']}")
    lines.extend(['',report['caveats'],'','Next: review retained-area loss and spatial patterns. Rainfall remains pending. Combined weights remain unset.'])
    (OUT/'review_report.txt').write_text('\n'.join(lines),encoding='utf-8')
    make_project()
    print('\n'.join(lines))


def make_project():
    from qgis.core import (QgsApplication,QgsProject,QgsRasterLayer,QgsReferencedRectangle,
        QgsColorRampShader,QgsRasterShader,QgsSingleBandPseudoColorRenderer)
    from qgis.PyQt.QtGui import QColor
    app=QgsApplication([],False)
    app.initQgis()
    project=QgsProject.instance()
    project.setTitle('2023-2025 provisional water and vegetation sensitivity')
    for scenario in ['all_complete','scl_water_at_least_2_years','broad_water_at_least_2_years','scl_and_vegetation_at_least_2_years']:
        layer=QgsRasterLayer(str(OUT/('NDMI_change_'+scenario+'.tif')),scenario+' NDMI change')
        assert layer.isValid()
        ramp=QgsColorRampShader()
        ramp.setColorRampType(QgsColorRampShader.Interpolated)
        ramp.setColorRampItemList([QgsColorRampShader.ColorRampItem(v,QColor(c),str(v))
            for v,c in [(-.3,'#8c510a'),(0,'#f5f5f5'),(.3,'#01665e')]])
        shader=QgsRasterShader(-.3,.3)
        shader.setRasterShaderFunction(ramp)
        renderer=QgsSingleBandPseudoColorRenderer(layer.dataProvider(),1,shader)
        renderer.setClassificationMin(-.3)
        renderer.setClassificationMax(.3)
        layer.setRenderer(renderer)
        project.addMapLayer(layer)
        project.layerTreeRoot().findLayer(layer.id()).setItemVisibilityChecked(scenario=='all_complete')
        project.setCrs(layer.crs())
        project.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(layer.extent(),layer.crs()))
    assert project.write(str(OUT/'sensitivity_review.qgz'))


if __name__=='__main__':
    main()
