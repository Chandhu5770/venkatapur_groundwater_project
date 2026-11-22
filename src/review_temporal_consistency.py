"""Classify three-year sign consistency, not groundwater confidence; QGIS Python."""
import csv
import os
from pathlib import Path
import numpy as np
from osgeo import gdal

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/processed/multiyear_2023_2025'
OUT=BASE/'surface_patterns'
LABELS={1:'Positive seasonal change in all three years',2:'Negative seasonal change in all three years',
        3:'Mixed signs or at least one exactly zero change'}


def main():
    global _qgis_app
    gdal.UseExceptions();OUT.mkdir(parents=True,exist_ok=True)
    ref=gdal.Open(str(BASE/'s2_NDMI_change_median_3years.tif'))
    def read(path):
        ds=gdal.Open(str(path))
        if (ds.RasterXSize,ds.RasterYSize,ds.GetGeoTransform(),ds.GetProjection())!=(ref.RasterXSize,ref.RasterYSize,ref.GetGeoTransform(),ref.GetProjection()):
            raise RuntimeError('Grid mismatch')
        a=ds.ReadAsArray().astype(float);nd=ds.GetRasterBand(1).GetNoDataValue()
        if nd is not None:a[a==nd]=np.nan
        return a
    water=read(BASE/'sensitivity/mask_scl_water_at_least_2_years.tif')
    data={key:(read(BASE/(key+'_change_median_3years.tif')),
               read(BASE/(key+'_change_sign_agreement.tif')),
               read(BASE/(key+'_paired_year_count.tif'))) for key in ['s2_NDMI','s1_vv','s1_vh']}
    common=water==1
    for median,agreement,count in data.values():common &= np.isfinite(median)&np.isfinite(agreement)&(count==3)
    if not common.any():raise RuntimeError('No common support')
    rows=[];paths=[];patterns={}
    for key,(median,agreement,count) in data.items():
        classes=np.zeros(median.shape,dtype=np.uint8);classes[common]=3
        unanimous=np.isclose(agreement,1,atol=1e-6,rtol=0)&common
        classes[unanimous&(median>0)]=1;classes[unanimous&(median<0)]=2
        patterns[key]=classes
        path=OUT/(key+'_temporal_consistency.tif');paths.append(path)
        ds=gdal.GetDriverByName('GTiff').Create(str(path),ref.RasterXSize,ref.RasterYSize,1,gdal.GDT_Byte,options=['COMPRESS=DEFLATE'])
        ds.SetGeoTransform(ref.GetGeoTransform());ds.SetProjection(ref.GetProjection())
        ds.GetRasterBand(1).SetNoDataValue(0);ds.GetRasterBand(1).WriteArray(classes);ds=None
        for code,label in LABELS.items():
            n=int((classes==code).sum())
            rows.append(dict(indicator=key,code=code,label=label,pixels=n,area_km2=n*.0009,fraction_common=n/int(common.sum())))
        assert sum(int((classes==code).sum()) for code in LABELS)==int(common.sum())
    with (OUT/'temporal_consistency_statistics.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (OUT/'temporal_consistency_notes.txt').write_text(
        'All maps use identical valid support across NDMI/VV/VH and three paired years after recurrent SCL-water exclusion. '
        'Strict zero threshold: tiny nonzero changes count. Three-year unanimity is descriptive persistence, not confidence or validation. '
        'A median sign can hide annual reversals. Recurring crop/irrigation/seasonal effects remain possible. '
        'Class 3 includes mixed signs and exact zeros; it does not mean no surface change. '
        'Three years are a short sampled period, not the planned five-year baseline. No groundwater scores or weights.\n',encoding='utf-8')
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    from qgis.core import QgsApplication,QgsProject,QgsRasterLayer,QgsPalettedRasterRenderer,QgsReferencedRectangle
    from qgis.PyQt.QtGui import QColor
    _qgis_app=QgsApplication([],False);_qgis_app.initQgis();project=QgsProject.instance()
    colors={1:'#008b8b',2:'#a66b36',3:'#bdbdbd'}
    for path in paths:
        layer=QgsRasterLayer(str(path),path.stem)
        if not layer.isValid():raise RuntimeError('Invalid temporal layer')
        layer.setRenderer(QgsPalettedRasterRenderer(layer.dataProvider(),1,[QgsPalettedRasterRenderer.Class(c,QColor(colors[c]),label) for c,label in LABELS.items()]))
        project.addMapLayer(layer);project.layerTreeRoot().findLayer(layer.id()).setItemVisibilityChecked(path==paths[0])
    project.setTitle('Three-year surface change consistency; no groundwater score')
    project.setCrs(layer.crs());project.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(layer.extent(),layer.crs()))
    if not project.write(str(OUT/'temporal_consistency_review.qgz')):raise RuntimeError('Project write failed')
    project.clear()
    for row in rows:print(row)


if __name__=='__main__':main()
