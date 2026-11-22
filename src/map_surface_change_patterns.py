"""Descriptive sign-pattern maps; QGIS Python, cached inputs only."""
import csv
import os
from pathlib import Path
import numpy as np
from osgeo import gdal

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/processed/multiyear_2023_2025'
OUT=BASE/'surface_patterns'
LABELS={1:'NDMI positive; radar positive',2:'NDMI negative; radar negative',
        3:'NDMI positive; radar negative',4:'NDMI negative; radar positive',
        5:'At least one change within exploratory near-zero band'}


def classify(optical, radar, epsilon_optical, epsilon_radar):
    result=np.full(optical.shape,5,dtype=np.uint8)
    for code,a,b in [(1,1,1),(2,-1,-1),(3,1,-1),(4,-1,1)]:
        result[(optical*a>epsilon_optical)&(radar*b>epsilon_radar)]=code
    return result


def main():
    global _qgis_app
    gdal.UseExceptions(); OUT.mkdir(parents=True,exist_ok=True)
    ref=gdal.Open(str(BASE/'s2_NDMI_change_median_3years.tif'))
    def read(path):
        ds=gdal.Open(str(path))
        if (ds.RasterXSize,ds.RasterYSize,ds.GetGeoTransform(),ds.GetProjection())!=(ref.RasterXSize,ref.RasterYSize,ref.GetGeoTransform(),ref.GetProjection()):
            raise RuntimeError('Grid mismatch')
        a=ds.ReadAsArray().astype(float); nodata=ds.GetRasterBand(1).GetNoDataValue()
        if nodata is not None: a[a==nodata]=np.nan
        return a
    ndmi=read(BASE/'s2_NDMI_change_median_3years.tif')
    rows=[]; paths=[]
    for pol in ['vv','vh']:
        radar=read(BASE/f's1_{pol}_change_median_3years.tif')
        for scenario in ['all_complete','scl_water_at_least_2_years','broad_water_at_least_2_years']:
            mask=read(BASE/'sensitivity'/f'mask_{scenario}.tif')
            valid=np.isfinite(ndmi)&np.isfinite(radar)&(mask==1)
            if not valid.any(): raise RuntimeError('Empty common support')
            for name,eo,er in [('strict_sign',0.,0.),('near_zero_sensitivity',.02,.5)]:
                classes=classify(ndmi,radar,eo,er); classes[~valid]=0
                path=OUT/f'pattern_{pol}_{scenario}_{name}.tif'
                temporary=path.with_suffix('.partial.tif')
                ds=gdal.GetDriverByName('GTiff').Create(str(temporary),ref.RasterXSize,ref.RasterYSize,1,gdal.GDT_Byte,options=['COMPRESS=DEFLATE'])
                ds.SetGeoTransform(ref.GetGeoTransform());ds.SetProjection(ref.GetProjection())
                ds.GetRasterBand(1).SetNoDataValue(0);ds.GetRasterBand(1).WriteArray(classes);ds=None
                temporary.replace(path)
                paths.append(path)
                for code,label in LABELS.items():
                    n=int((classes==code).sum())
                    rows.append(dict(polarization=pol,mask_scenario=scenario,threshold_scenario=name,
                        ndmi_epsilon=eo,radar_epsilon_db=er,code=code,label=label,pixels=n,
                        area_km2=n*.0009,fraction_common_support=n/int(valid.sum()),common_pixels=int(valid.sum())))
                assert sum(int((classes==code).sum()) for code in LABELS)==int(valid.sum())
    with (OUT/'pattern_areas.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (OUT/'README.txt').write_text('Surface-change sign patterns, 2023-2025 within-year post-minus-pre median changes. Not groundwater suitability or validation. Same-sign changes do not establish common cause. VV/VH are separate comparisons, not independent confirmations. Strict sign includes arbitrarily small changes; exact zero is class 5. Near-zero bands (NDMI +/-0.02, radar +/-0.5 dB) are arbitrary sensitivity assumptions, not measurement uncertainty or calibrated thresholds. Compare maps on their stated common support; masks change the population. Three valid paired years required by source rasters. No weights, combined score, rainfall causality or drilling inference.\n',encoding='utf-8')
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    from qgis.core import QgsApplication,QgsProject,QgsRasterLayer,QgsPalettedRasterRenderer,QgsReferencedRectangle
    from qgis.PyQt.QtGui import QColor
    _qgis_app=QgsApplication([],False);_qgis_app.initQgis();project=QgsProject.instance()
    colors={1:'#008b8b',2:'#a66b36',3:'#756bb1',4:'#d95f82',5:'#d9d9d9'}
    for path in paths:
        layer=QgsRasterLayer(str(path),path.stem)
        if not layer.isValid(): raise RuntimeError('Invalid map')
        classes=[QgsPalettedRasterRenderer.Class(code,QColor(colors[code]),label) for code,label in LABELS.items()]
        layer.setRenderer(QgsPalettedRasterRenderer(layer.dataProvider(),1,classes));project.addMapLayer(layer)
        project.layerTreeRoot().findLayer(layer.id()).setItemVisibilityChecked(path==paths[0])
    project.setCrs(layer.crs());project.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(layer.extent(),layer.crs()))
    if not project.write(str(OUT/'surface_patterns_review.qgz')): raise RuntimeError('Project write failed')
    # Let process teardown release QGIS; explicit exitQgis can invalidate live SIP wrappers.
    project.clear()
    print(f'Saved {len(paths)} descriptive maps and {len(rows)} area rows to {OUT}')


if __name__=='__main__':main()
