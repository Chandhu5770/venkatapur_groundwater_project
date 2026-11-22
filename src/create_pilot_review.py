"""Assemble existing 2025 pilot evidence in one QGIS project; no scoring."""
import json
from pathlib import Path
from qgis.core import (QgsApplication,QgsProject,QgsRasterLayer,QgsVectorLayer,
                       QgsReferencedRectangle)

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/processed/pilot_review'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    app=QgsApplication([],False)
    app.initQgis()
    project=QgsProject.instance()
    project.setTitle('Venkatapur 2025 evidence review - exploratory pilot')
    manifest={'scope':'Single-year sampled optical, matched radar, and provisional terrain evidence; no combined weights or score.',
              'rainfall':'Pending authenticated access to documented IMERG uncalibrated field. No rainfall raster acquired.',
              'multi_year':'Pending: current outputs do not meet the three-paired-year requirement.',
              'layers':[]}
    specifications={
        'Terrain': [('terrain_pilot/slope_degrees.tif','Slope (degrees)'),
                    ('terrain_pilot/twi.tif','Terrain wetness index'),
                    ('terrain_pilot/edge_underestimate_flag.tif','Flow uncertainty flag'),
                    ('terrain_pilot/drainage_diagnostics/density_0p5_km_per_km2.tif','Drainage density (km/km2)')],
        'Optical aligned to 30 m': [('indicator_review/pre_NDMI_30m.tif','Pre-monsoon NDMI'),
                                   ('indicator_review/post_NDMI_30m.tif','Post-monsoon NDMI'),
                                   ('indicator_review/pre_NDVI_30m.tif','Pre-monsoon NDVI'),
                                   ('indicator_review/post_NDVI_30m.tif','Post-monsoon NDVI')],
        'Radar 30 m': [('s1_seasons_2025/pre_vv_gamma0_db_median.tif','Pre-monsoon VV gamma0 (dB)'),
                      ('s1_seasons_2025/post_vv_gamma0_db_median.tif','Post-monsoon VV gamma0 (dB)'),
                      ('s1_seasons_2025/post_minus_pre_vv_db.tif','VV post-minus-pre (dB)'),
                      ('s1_seasons_2025/pre_vv_count.tif','Pre-monsoon radar count')],
        'Optical coverage 20 m': [('s2_seasons_2025/pre_NDMI_count.tif','Pre-monsoon optical count (20 m)'),
                                 ('s2_seasons_2025/post_NDMI_count.tif','Post-monsoon optical count (20 m)')]}
    for group_name,specs in specifications.items():
        group=project.layerTreeRoot().addGroup(group_name)
        for relative,label in specs:
            path=ROOT/'data/processed'/relative
            layer=QgsRasterLayer(str(path),label)
            assert layer.isValid(),str(path)
            project.addMapLayer(layer,False)
            node=group.addLayer(layer)
            node.setItemVisibilityChecked(relative=='terrain_pilot/slope_degrees.tif')
            if relative=='terrain_pilot/slope_degrees.tif':
                project.setCrs(layer.crs())
                project.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(layer.extent(),layer.crs()))
            manifest['layers'].append({'path':relative,'label':label})
    streams=QgsVectorLayer(str(ROOT/'data/processed/terrain_pilot/drainage_diagnostics/stream_segments.gpkg')+'|layername=streams_0p5','Provisional stream segments (0.5 km2 threshold)','ogr')
    assert streams.isValid()
    project.addMapLayer(streams)
    project.layerTreeRoot().findLayer(streams.id()).setItemVisibilityChecked(False)
    assert project.write(str(OUT/'venkatapur_pilot_review.qgz'))
    (OUT/'pilot_status.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    (OUT/'README.txt').write_text(
        '2025 pilot evidence review. Open venkatapur_pilot_review.qgz and view one raster at a time.\n'
        'This assembled project uses default raster stretches for inspection. For fair date comparison use the individual optical/radar projects with their fixed scales.\n'
        'Optical aligned layers and terrain/radar use 30 m; optical count layers retain 20 m.\n'
        'Rainfall is pending access: anonymous NASA PPS requests returned 401; GES DISC content request also returned 401.\n'
        'Target rainfall: IMERG V07 half-hourly uncalibrated field, metadata/version to verify after authorized access.\n'
        'The uncalibrated field omits final monthly gauge adjustment; IMERG still uses ancillary models/calibration.\n'
        'Retain rainfall native 0.1-degree support. Rates in mm/hour require duration integration and missing-interval checks.\n'
        'Do not substitute calibrated rainfall or treat missing data as zero. Never share passwords/tokens in chat or Git.\n'
        'Multi-year coverage, field review and exploratory scenario sensitivity remain pending. No combined score is produced.\n',encoding='utf-8')
    print('Created',OUT/'venkatapur_pilot_review.qgz')


if __name__=='__main__':
    main()
