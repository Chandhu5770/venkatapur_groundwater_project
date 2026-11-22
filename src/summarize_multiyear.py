"""Summarize 2023-2025 sampled seasonal evidence, requiring three paired years.

Run with QGIS Python after both sensor workflows for all three years.
"""
import json
import warnings
from pathlib import Path

import numpy as np
from osgeo import gdal

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/processed'
OUT=DATA/'multiyear_2023_2025'
YEARS=[2023,2024,2025]


def main():
    gdal.UseExceptions()
    OUT.mkdir(exist_ok=True)
    ref=gdal.Open(str(DATA/'terrain_pilot/edge_underestimate_flag.tif'))
    gt=ref.GetGeoTransform()
    w,h=ref.RasterXSize,ref.RasterYSize
    bounds=[gt[0],gt[3]-h*30,gt[0]+w*30,gt[3]]
    inside=ref.ReadAsArray()!=ref.GetRasterBand(1).GetNoDataValue()
    report={'years':YEARS,'scope':'Three-year sampled evidence, 2023-2025; not the full planned 2021-2025 baseline.',
        'minimum_valid_observations_per_season':3,'minimum_paired_years':3,
        'change':'Within-year post-minus-pre, then median across paired years. Radar changes are dB differences.',
        'optical_alignment':'Area average each annual seasonal index to 30 m; require >=99.9% fine-grid validity.',
        'limitations':'Single orbit radar, sampled optical dates, unresolved water/crop/geometry confounding. Rainfall and field assessment remain pending. No groundwater score or validation.',
        'indicators':{}}

    def read(path):
        source=gdal.Open(str(path))
        original=source.ReadAsArray()
        nodata=source.GetRasterBand(1).GetNoDataValue()
        if source.GetGeoTransform()!=gt or source.RasterXSize!=w or source.RasterYSize!=h:
            support=gdal.GetDriverByName('MEM').Create('',source.RasterXSize,source.RasterYSize,1,gdal.GDT_Byte)
            support.SetGeoTransform(source.GetGeoTransform())
            support.SetProjection(source.GetProjection())
            support.GetRasterBand(1).WriteArray((original!=nodata).astype('uint8'))
            fraction=gdal.Warp('',support,format='MEM',dstSRS='EPSG:32644',outputBounds=bounds,
                width=w,height=h,resampleAlg='average',outputType=gdal.GDT_Float32).ReadAsArray()
            source=gdal.Warp('',source,format='MEM',dstSRS='EPSG:32644',outputBounds=bounds,
                width=w,height=h,resampleAlg='average',dstNodata=-9999)
            a=source.ReadAsArray().astype(float)
            a[(fraction<.999)|(a==-9999)]=np.nan
        else:
            a=original.astype(float)
            a[a==nodata]=np.nan
        a[~inside]=np.nan
        return a

    def write(name,a):
        ds=gdal.GetDriverByName('GTiff').Create(str(OUT/(name+'.tif')),w,h,1,gdal.GDT_Float32,
                                               options=['COMPRESS=DEFLATE','TILED=YES'])
        ds.SetGeoTransform(gt)
        ds.SetProjection(ref.GetProjection())
        ds.GetRasterBand(1).SetNoDataValue(-9999)
        ds.GetRasterBand(1).WriteArray(np.where(inside&np.isfinite(a),a,-9999).astype('float32'))
        ds=None

    for sensor,names in [('s2',['NDVI','NDMI','MNDWI']),('s1',['vv','vh'])]:
        for name in names:
            annual={season:[] for season in ['pre','post']}
            for year in YEARS:
                for season in annual:
                    filename=season+'_'+name+('_median.tif' if sensor=='s2' else '_gamma0_db_median.tif')
                    annual[season].append(read(DATA/f'{sensor}_seasons_{year}'/filename))
            key=sensor+'_'+name
            pre,post=np.stack(annual['pre']),np.stack(annual['post'])
            changes=post-pre
            paired=np.isfinite(changes).sum(axis=0)
            complete=paired>=3
            with warnings.catch_warnings():
                warnings.simplefilter('ignore',RuntimeWarning)
                change=np.nanmedian(changes,axis=0)
                iqr=np.nanpercentile(changes,75,axis=0)-np.nanpercentile(changes,25,axis=0)
                for season,stack in [('pre',pre),('post',post)]:
                    count=np.isfinite(stack).sum(axis=0)
                    median=np.nanmedian(stack,axis=0)
                    median[count<3]=np.nan
                    write(key+'_'+season+'_median_3years',median)
                    write(key+'_'+season+'_year_count',count)
            change[~complete]=np.nan
            iqr[~complete]=np.nan
            positive=(changes>0).sum(axis=0)
            negative=(changes<0).sum(axis=0)
            agreement=np.where(complete,np.maximum(positive,negative)/3,np.nan)
            write(key+'_paired_year_count',paired)
            write(key+'_change_median_3years',change)
            write(key+'_change_iqr',iqr)
            write(key+'_change_sign_agreement',agreement)
            assert not np.isfinite(change[paired<3]).any()
            report['indicators'][key]={'fraction_circle_with_3_paired_years':float(complete[inside].mean()),
                'median_change_on_complete_pixels':float(np.nanmedian(change)) if complete.any() else None,
                'source_paths':[f'data/processed/{sensor}_seasons_{y}' for y in YEARS],
                'sign_agreement':'Fraction of three paired changes sharing the more common nonzero sign; descriptive temporal consistency only, not confidence.'}
            print(key,report['indicators'][key]['fraction_circle_with_3_paired_years'],flush=True)
    (OUT/'multiyear_manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    lines=['2023-2025 sampled seasonal evidence review','',report['scope'],
           'Grid: EPSG:32644, 30 m. NoData=-9999. Required paired years=3.',
           report['change'],report['limitations'],'']
    for key,details in report['indicators'].items():
        lines.append(f"{key}: {100*details['fraction_circle_with_3_paired_years']:.2f}% of planning circle has 3 paired years; median change={details['median_change_on_complete_pixels']}")
    lines.extend(['','S2 index changes are unitless; S1 changes are dB.',
                  'Change IQR describes variation between the three annual seasonal changes.',
                  'Sign agreement is descriptive temporal consistency, not probability or confidence.',
                  'Water remains included; compare water/vegetation scenarios before interpretation.',
                  'Open multiyear_review.qgz and view paired-year counts before change maps.'])
    (OUT/'README.txt').write_text('\n'.join(lines),encoding='utf-8')
    make_project()


def make_project():
    from qgis.core import (QgsApplication,QgsProject,QgsRasterLayer,QgsReferencedRectangle,
        QgsColorRampShader,QgsRasterShader,QgsSingleBandPseudoColorRenderer)
    from qgis.PyQt.QtGui import QColor
    app=QgsApplication([],False)
    app.initQgis()
    project=QgsProject.instance()
    project.setTitle('2023-2025 sampled seasonal evidence - three paired years required')
    for name,low,high in [('s2_NDMI_pre_median_3years',-1,1),('s2_NDMI_post_median_3years',-1,1),
                         ('s2_NDMI_change_median_3years',-.3,.3),('s2_NDMI_paired_year_count',0,3),
                         ('s1_vv_change_median_3years',-6,6),('s1_vv_paired_year_count',0,3)]:
        layer=QgsRasterLayer(str(OUT/(name+'.tif')),name)
        assert layer.isValid()
        ramp=QgsColorRampShader()
        ramp.setColorRampType(QgsColorRampShader.Interpolated)
        ramp.setColorRampItemList([QgsColorRampShader.ColorRampItem(v,QColor(c),str(v))
            for v,c in [(low,'#8c510a'),((low+high)/2,'#f5f5f5'),(high,'#01665e')]])
        shader=QgsRasterShader(low,high)
        shader.setRasterShaderFunction(ramp)
        renderer=QgsSingleBandPseudoColorRenderer(layer.dataProvider(),1,shader)
        renderer.setClassificationMin(low)
        renderer.setClassificationMax(high)
        layer.setRenderer(renderer)
        project.addMapLayer(layer)
        project.layerTreeRoot().findLayer(layer.id()).setItemVisibilityChecked(name=='s2_NDMI_change_median_3years')
        project.setCrs(layer.crs())
        project.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(layer.extent(),layer.crs()))
    assert project.write(str(OUT/'multiyear_review.qgz'))


if __name__=='__main__':
    main()
