"""Local two-date optical trial; run with QGIS's python-qgis-ltr.bat.

No groundwater score, seasonal composite, or automatic recharge inference.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
from osgeo import gdal, ogr, osr

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw/sentinel/s2/trial_2025'
OUT = ROOT / 'data/processed/s2_trial_2025'
NODATA = -9999.0
BAD = [0, 1, 2, 3, 7, 8, 9, 10, 11]


def main():
    gdal.UseExceptions()
    manifest = json.loads((RAW / 'download_manifest.json').read_text())
    aoi_path = ROOT / 'data/reference/venkatapur_initial_study_area_5km.geojson'
    assert hashlib.sha256(aoi_path.read_bytes()).hexdigest() == manifest['aoi_sha256']
    ref = gdal.Open(str(RAW / '2025-05-12/B03.tif'))
    shape = (ref.RasterYSize, ref.RasterXSize)
    geo, projection = ref.GetGeoTransform(), ref.GetProjection()
    OUT.mkdir(parents=True, exist_ok=True)

    def write(name, array, description):
        path = OUT / (name + '.tif')
        ds = gdal.GetDriverByName('GTiff').Create(str(path), shape[1], shape[0], 1,
                 gdal.GDT_Float32, options=['COMPRESS=DEFLATE', 'TILED=YES'])
        ds.SetGeoTransform(geo)
        ds.SetProjection(projection)
        ds.SetMetadataItem('INTERPRETATION', 'Two-date surface-evidence trial only; not groundwater or recharge measurement')
        band = ds.GetRasterBand(1)
        band.SetNoDataValue(NODATA)
        band.SetDescription(description)
        band.WriteArray(np.where(np.isfinite(array), array, NODATA).astype('float32'))
        ds = None
        check = gdal.Open(str(path))
        assert check.GetGeoTransform() == geo and check.GetProjection() == projection
        assert check.GetRasterBand(1).GetNoDataValue() == NODATA
        return path

    # Pixel-centre inclusion in the actual planning circle, not its bounding rectangle.
    ring = json.loads(aoi_path.read_text())['features'][0]['geometry']
    geom = ogr.CreateGeometryFromJson(json.dumps(ring))
    src, dst = osr.SpatialReference(), osr.SpatialReference()
    src.ImportFromEPSG(4326)
    dst.ImportFromEPSG(32644)
    for crs in (src, dst):
        crs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    geom.Transform(osr.CoordinateTransformation(src, dst))
    vector = ogr.GetDriverByName('Memory').CreateDataSource('')
    layer = vector.CreateLayer('circle', dst, ogr.wkbPolygon)
    feature = ogr.Feature(layer.GetLayerDefn())
    feature.SetGeometry(geom)
    layer.CreateFeature(feature)
    mask_ds = gdal.GetDriverByName('MEM').Create('', shape[1], shape[0], 1, gdal.GDT_Byte)
    mask_ds.SetGeoTransform(geo)
    mask_ds.SetProjection(projection)
    gdal.RasterizeLayer(mask_ds, [1], layer, burn_values=[1])
    inside = mask_ds.ReadAsArray() == 1
    summary = {'scope': 'Two single-date images, not seasonal composites. No weights or groundwater score.',
               'grid_crs': 'EPSG:32644', 'pixel_size_m': 20,
               'scl_excluded': BAD, 'cloud_shadow_dilation_m': 60,
               'water_flag': 'SCL=6 or MNDWI>0 on either date; preliminary, requires visual review',
               'dates': {}, 'differences': {}}
    results, waters = {}, {}
    for product in manifest['products']:
        date = Path(product['files'][0]['path']).parent.name
        arrays = {}
        valid = inside.copy()
        scl = None
        scaling = {}
        for record in product['files']:
            path = ROOT / record['path']
            assert hashlib.sha256(path.read_bytes()).hexdigest() == record['sha256']
            ds = gdal.Open(str(path))
            assert ds.GetGeoTransform() == geo and ds.GetProjection() == projection
            dn = ds.ReadAsArray()
            metadata = record['raster_bands'][0]
            valid &= dn != metadata['nodata']
            if record['band'] == 'SCL':
                scl = dn
            else:
                # Apply provider-declared scale and offset exactly once; do not clip reflectance.
                scale, offset = metadata['scale'], metadata['offset']
                arrays[record['band']] = dn.astype('float64') * scale + offset
                scaling[record['band']] = {'scale': scale, 'offset': offset}
        bad = np.isin(scl, BAD)
        # Disk-shaped 60 m cloud/shadow buffer on the 20 m grid.
        cloud = np.isin(scl, [2, 3, 7, 8, 9, 10])
        padded = np.pad(cloud, 3)
        dilated = np.zeros(shape, dtype=bool)
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                if dx*dx + dy*dy <= 9:
                    dilated |= padded[3+dy:3+dy+shape[0], 3+dx:3+dx+shape[1]]
        valid &= ~bad & ~dilated
        indices = {}
        for name, first, second in [('NDVI', 'B08', 'B04'), ('NDMI', 'B08', 'B11'), ('MNDWI', 'B03', 'B11')]:
            a, b = arrays[first], arrays[second]
            usable = valid & (a >= 0) & (b >= 0) & ((a+b) > 1e-6)
            value = np.full(shape, np.nan)
            np.divide(a-b, a+b, out=value, where=usable)
            assert np.all(np.abs(value[np.isfinite(value)]) <= 1.000001)
            indices[name] = value
            write(date + '_' + name, value, name + ' (scaled reflectance, quality masked)')
        water = valid & ((scl == 6) | (indices['MNDWI'] > 0))
        waters[date] = water
        write(date + '_water_flag', np.where(valid, water.astype(float), np.nan), 'Preliminary surface-water flag; 0=no flag, 1=flag')
        write(date + '_quality_mask', np.where(inside, valid.astype(float), np.nan), 'Quality eligibility; 0=excluded, 1=eligible, outside circle=NoData')
        for band, array in arrays.items():
            write(date + '_' + band + '_reflectance', np.where(valid, array, np.nan), band + ' surface reflectance; scale/offset already applied')
        summary['dates'][date] = {'item_id': product['item_id'], 'scaling': scaling,
            'eligible_pixels': int(valid.sum()), 'aoi_pixels': int(inside.sum()),
            'preliminary_water_flag_pixels': int(water.sum()),
            'indices': {name: {'valid_pixels': int(np.isfinite(a).sum()),
                              'median': float(np.nanmedian(a))} for name, a in indices.items()}}
        results[date] = indices
    pre, post = '2025-05-12', '2025-12-28'
    water_union = waters[pre] | waters[post]
    for name in ['NDVI', 'NDMI', 'MNDWI']:
        before, after = results[pre][name], results[post][name]
        paired = np.isfinite(before) & np.isfinite(after) & ~water_union
        delta = np.where(paired, after-before, np.nan)
        write('trial_post_minus_pre_' + name, delta, '28 December minus 12 May 2025; water flags on either date excluded; not seasonal change or recharge')
        summary['differences'][name] = {'valid_paired_pixels': int(paired.sum()), 'median': float(np.nanmedian(delta))}
    (OUT / 'processing_summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    (OUT / 'README.txt').write_text(
        'Two-date Sentinel-2 surface-evidence trial, 20 m, EPSG:32644.\n'
        'NDVI=vegetation; NDMI=surface/canopy moisture proxy; MNDWI=water-screening proxy.\n'
        'Reflectance files already include scale/offset: do not scale again. NoData=-9999.\n'
        'Difference rasters exclude preliminary water flags from either date. Review flags visually.\n'
        'Two images do not meet seasonal-composite or multi-year requirements. Crops and irrigation confound changes.\n'
        'No groundwater potential, recharge, yield or drilling-depth inference.\n', encoding='utf-8')
    make_review_project()
    print(json.dumps(summary, indent=2))


def make_review_project():
    from qgis.core import (QgsApplication, QgsProject, QgsRasterLayer, QgsVectorLayer,
                           QgsCoordinateReferenceSystem, QgsColorRampShader,
                           QgsRasterShader, QgsSingleBandPseudoColorRenderer,
                           QgsReferencedRectangle)
    from qgis.PyQt.QtGui import QColor
    app = QgsApplication([], False)
    app.initQgis()
    project = QgsProject.instance()
    crs = QgsCoordinateReferenceSystem('EPSG:32644')
    project.setCrs(crs)
    project.setTitle('Two-date optical surface evidence - no groundwater score')
    for date in ['2025-05-12', '2025-12-28']:
        for name in ['NDVI', 'NDMI', 'MNDWI']:
            layer = QgsRasterLayer(str(OUT / (date + '_' + name + '.tif')), date + ' ' + name)
            assert layer.isValid()
            ramp = QgsColorRampShader()
            ramp.setColorRampType(QgsColorRampShader.Interpolated)
            ramp.setColorRampItemList([
                QgsColorRampShader.ColorRampItem(-1, QColor('#8c510a'), '-1'),
                QgsColorRampShader.ColorRampItem(0, QColor('#f5f5f5'), '0'),
                QgsColorRampShader.ColorRampItem(1, QColor('#01665e'), '+1')])
            shader = QgsRasterShader(-1, 1)
            shader.setRasterShaderFunction(ramp)
            renderer = QgsSingleBandPseudoColorRenderer(layer.dataProvider(), 1, shader)
            renderer.setClassificationMin(-1)
            renderer.setClassificationMax(1)
            layer.setRenderer(renderer)
            project.addMapLayer(layer)
            project.layerTreeRoot().findLayer(layer.id()).setItemVisibilityChecked(date == '2025-12-28' and name == 'NDMI')
    buffer = QgsVectorLayer(str(ROOT / 'data/reference/venkatapur_initial_study_area_5km.geojson'), '5 km planning buffer (not village boundary)', 'ogr')
    buffer.renderer().symbol().symbolLayer(0).setBrushStyle(0)
    project.addMapLayer(buffer)
    centre = QgsVectorLayer(str(ROOT / 'data/reference/venkatapur_village_centre.geojson'), 'User-confirmed reference centre', 'ogr')
    project.addMapLayer(centre)
    extent = project.viewSettings()
    box = buffer.extent()
    from qgis.core import QgsCoordinateTransform
    box = QgsCoordinateTransform(buffer.crs(), crs, project).transformBoundingBox(box)
    box.scale(1.08)
    extent.setDefaultViewExtent(QgsReferencedRectangle(box, crs))
    assert project.write(str(OUT / 'optical_trial_review.qgz'))


if __name__ == '__main__':
    main()
