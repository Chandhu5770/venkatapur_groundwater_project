"""Assemble cached evidence into a grouped QGIS project; no scores/downloads."""
import json
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/processed'
OUT=DATA/'integrated_evidence_review'


def main():
    global _qgis_app
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    from qgis.core import (QgsApplication,QgsProject,QgsRasterLayer,QgsVectorLayer,QgsColorRampShader,
        QgsRasterShader,QgsSingleBandPseudoColorRenderer,QgsReferencedRectangle,QgsFillSymbol,QgsMarkerSymbol,Qgis)
    from qgis.PyQt.QtGui import QColor
    _qgis_app=QgsApplication([],False);_qgis_app.initQgis();project=QgsProject.instance()
    project.setTitle('Venkatapur evidence review: no validated groundwater score')
    OUT.mkdir(parents=True,exist_ok=True)
    project.setFilePathStorage(Qgis.FilePathType.Relative)
    root=project.layerTreeRoot();inventory=[]
    def add(layer,group,visible=False):
        if not layer.isValid():raise RuntimeError('Invalid layer: '+layer.name())
        if isinstance(layer,QgsRasterLayer) and not layer.crs().isValid():
            raise RuntimeError('Raster has no valid CRS: '+layer.name())
        project.addMapLayer(layer,False);node=group.addLayer(layer);node.setItemVisibilityChecked(visible)
        metadata=layer.metadata()
        metadata.setAbstract('Exploratory evidence only. See docs/06_scenario_review.md. No groundwater yield, depth or drilling prediction.')
        layer.setMetadata(metadata)
        inventory.append({'name':layer.name(),'provider':layer.providerType()})
    def raster(path,label,group,low,high,visible=False):
        layer=QgsRasterLayer(str(path),label)
        if not layer.isValid():raise RuntimeError('Missing raster: '+str(path))
        ramp=QgsColorRampShader();ramp.setColorRampType(QgsColorRampShader.Interpolated)
        ramp.setColorRampItemList([QgsColorRampShader.ColorRampItem(v,QColor(c),str(v)) for v,c in
            [(low,'#8c510a'),((low+high)/2,'#f5f5f5'),(high,'#01665e')]])
        shader=QgsRasterShader(low,high);shader.setRasterShaderFunction(ramp)
        renderer=QgsSingleBandPseudoColorRenderer(layer.dataProvider(),1,shader)
        renderer.setClassificationMin(low);renderer.setClassificationMax(high);layer.setRenderer(renderer)
        add(layer,group,visible);return layer
    reference=root.addGroup('1 Reference: planning area, not village boundary')
    centre=QgsVectorLayer(str(ROOT/'data/reference/venkatapur_village_centre.geojson'),'User-confirmed reference centre','ogr')
    centre.renderer().setSymbol(QgsMarkerSymbol.createSimple({'name':'circle','color':'#f6c344','outline_color':'black','size':'2.5'}))
    add(centre,reference,True)
    boundary=QgsVectorLayer(str(ROOT/'data/reference/venkatapur_initial_study_area_5km.geojson'),'5 km planning buffer','ogr')
    boundary.renderer().setSymbol(QgsFillSymbol.createSimple({'color':'transparent','outline_color':'#222222','outline_width':'0.4','style':'no'}))
    add(boundary,reference,True)
    terrain=root.addGroup('2 Terrain setting: no suitability assigned')
    raster(DATA/'terrain_pilot/slope_degrees.tif','Slope (degrees)',terrain,0,10)
    raster(DATA/'terrain_pilot/twi.tif','TWI: excluded upstream-edge estimates remain blank',terrain,4,14)
    for key in ['0p25','0p5','1p0']:
        raster(DATA/f'terrain_pilot/drainage_diagnostics/density_{key}_km_per_km2.tif',f'Density threshold {key} km2 (km/km2)',terrain,0,3)
    optical=root.addGroup('3 Optical 2023-2025: levels and within-year changes')
    default=None
    for name in ['NDMI','NDVI']:
        for season in ['pre','post']:
            layer=raster(DATA/f'multiyear_2023_2025/s2_{name}_{season}_median_3years.tif',f'{season} {name}: three-year seasonal median',optical,-1,1,name=='NDMI' and season=='pre')
            if name=='NDMI' and season=='pre':default=layer
        raster(DATA/f'multiyear_2023_2025/s2_{name}_change_median_3years.tif',f'{name}: median within-year post-minus-pre',optical,-.3,.3)
    radar=root.addGroup('4 Radar 2023-2025: no default suitability direction')
    for pol in ['vv','vh']:
        raster(DATA/f'multiyear_2023_2025/s1_{pol}_change_median_3years.tif',f'{pol.upper()} median within-year change (dB)',radar,-3,3)
    for label,path in [('5 Surface pattern sensitivity',DATA/'multiyear_2023_2025/surface_patterns/surface_patterns_review.qgz'),
                       ('6 Three-year sign consistency',DATA/'multiyear_2023_2025/surface_patterns/temporal_consistency_review.qgz'),
                       ('7 Hypothetical terrain scenarios: no groundwater classes',DATA/'terrain_scenarios/terrain_scenarios_review.qgz')]:
        source=QgsProject()
        if not source.read(str(path)):raise RuntimeError('Cannot read '+str(path))
        group=root.addGroup(label)
        for node in source.layerTreeRoot().findLayers():add(node.layer().clone(),group)
        source.clear();group.setExpanded(False)
    tables=root.addGroup('8 Tables: right-click and open attribute table')
    for relative in ['rainfall_context/daily_rainfall_2025_05.csv','rainfall_context/may_acquisition_rainfall_context.csv',
                     'rainfall_context/may_paired_optical_statistics.csv','rainfall_context/may_paired_radar_statistics.csv',
                     'multiyear_2023_2025/surface_patterns/terrain_strata_statistics.csv',
                     'terrain_pilot/drainage_diagnostics/threshold_sensitivity.csv',
                     'terrain_scenarios/scenario_summary.csv','terrain_scenarios/weight_sensitivity.csv',
                     'multiyear_2023_2025/surface_patterns/optical_confounding_statistics.csv']:
        add(QgsVectorLayer(str(DATA/relative),Path(relative).stem,'ogr'),tables)
    project.setCrs(default.crs());project.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(default.extent(),default.crs()))
    path=OUT/'venkatapur_evidence_review.qgz'
    if not project.write(str(path)):raise RuntimeError('Project write failed')
    check=QgsProject()
    if not check.read(str(path)):raise RuntimeError('Project reload failed')
    if len(check.mapLayers())!=len(inventory) or not all(l.isValid() for l in check.mapLayers().values()):
        raise RuntimeError('Reloaded layer validation failed')
    (OUT/'project_inventory.json').write_text(json.dumps({'layer_count':len(inventory),'crs':'EPSG:32644',
        'reload_all_layers_valid':True,'layers':inventory,'scope':'2023-2025 surface/terrain evidence; May 2025 rainfall context only; no combined score'},indent=2),encoding='utf-8')
    (OUT/'START_HERE.txt').write_text(
        'Open venkatapur_evidence_review.qgz with QGIS. Keep original folder structure; project uses relative paths. '
        'Toggle one raster at a time to avoid upper layers hiding lower layers. Reference centre and buffer can stay visible. '
        'Optical pre/post levels use identical -1 to +1 display scales; changes use a separate scale. '
        'Colored categories describe surface patterns, not groundwater potential. Gray consistency pixels can contain mixed annual signs. '
        'Open CSV layers using their attribute tables. Rainfall has native coarse support; it is not mapped to 30 m or averaged over the village. '
        'Read docs/06_scenario_review.md before interpreting. This is not a portable standalone bundle: sibling processed folders are required. '
        'No online basemap, credentials, downloads, combined weights or validated groundwater map.\n',encoding='utf-8')
    count=len(inventory);check.clear();project.clear()
    print(f'Created and reloaded project: {count} valid layers; EPSG:32644. {path}')


if __name__=='__main__':main()
