"""Small-area 2025 seasonal pilot. Run with QGIS Python; public COG access.

Select at most two distinct dates per month by whole-tile cloud cover <=40%.
This sample is not a complete seasonal archive or a multi-year assessment.
"""
import hashlib
import json
import math
import warnings
from pathlib import Path
from urllib.parse import urlencode, urljoin
from urllib.request import urlopen

import numpy as np
from osgeo import gdal, ogr, osr

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw/sentinel/s2/seasons_2025'
OUT = ROOT / 'data/processed/s2_seasons_2025'
API = 'https://earth-search.aws.element84.com/v1'
BANDS = {'B03': 'green', 'B04': 'red', 'B08': 'nir', 'B11': 'swir16', 'SCL': 'scl'}
SEASONS = {'pre': ('2025-03-01', '2025-05-31'), 'post': ('2025-10-01', '2025-12-31')}


def fetch(url):
    with urlopen(url, timeout=60) as response:
        return json.load(response)


def main():
    gdal.UseExceptions()
    for key, value in {'GDAL_DISABLE_READDIR_ON_OPEN': 'EMPTY_DIR', 'GDAL_HTTP_TIMEOUT': '60',
                       'GDAL_HTTP_MAX_RETRY': '2'}.items():
        gdal.SetConfigOption(key, value)
    RAW.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    aoi_path = ROOT / 'data/reference/venkatapur_initial_study_area_5km.geojson'
    geometry = json.loads(aoi_path.read_text())['features'][0]['geometry']
    ring = geometry['coordinates'][0]
    src, dst = osr.SpatialReference(), osr.SpatialReference()
    src.ImportFromEPSG(4326)
    dst.ImportFromEPSG(32644)
    for crs in (src, dst):
        crs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    transform = osr.CoordinateTransformation(src, dst)
    points = [transform.TransformPoint(*p) for p in ring]
    # 100 m apron allows the 60 m shadow dilation to include pixels outside the circle.
    bounds = [math.floor(min(p[0] for p in points)/20)*20-100,
              math.floor(min(p[1] for p in points)/20)*20-100,
              math.ceil(max(p[0] for p in points)/20)*20+100,
              math.ceil(max(p[1] for p in points)/20)*20+100]
    width, height = round((bounds[2]-bounds[0])/20), round((bounds[3]-bounds[1])/20)
    gt = (bounds[0], 20, 0, bounds[3], 0, -20)
    shape = (height, width)
    mem = gdal.GetDriverByName('MEM').Create('', width, height, 1, gdal.GDT_Byte)
    mem.SetGeoTransform(gt)
    mem.SetProjection(dst.ExportToWkt())
    vector = ogr.GetDriverByName('Memory').CreateDataSource('')
    layer = vector.CreateLayer('aoi', dst, ogr.wkbPolygon)
    geom = ogr.CreateGeometryFromJson(json.dumps(geometry))
    geom.Transform(transform)
    feature = ogr.Feature(layer.GetLayerDefn())
    feature.SetGeometry(geom)
    layer.CreateFeature(feature)
    gdal.RasterizeLayer(mem, [1], layer, burn_values=[1])
    inside = mem.ReadAsArray() == 1

    def write(name, array):
        path = OUT / (name + '.tif')
        ds = gdal.GetDriverByName('GTiff').Create(str(path), width, height, 1, gdal.GDT_Float32,
                                               options=['COMPRESS=DEFLATE', 'TILED=YES'])
        ds.SetGeoTransform(gt)
        ds.SetProjection(dst.ExportToWkt())
        ds.SetMetadataItem('SCOPE', '2025 sampled seasonal surface evidence; no groundwater score')
        ds.GetRasterBand(1).SetNoDataValue(-9999)
        ds.GetRasterBand(1).WriteArray(np.where(np.isfinite(array), array, -9999).astype('float32'))
        ds = None

    bbox = ','.join(map(str, [min(p[0] for p in ring), min(p[1] for p in ring),
                              max(p[0] for p in ring), max(p[1] for p in ring)]))
    report = {'scope': '2025 sampled seasonal pilot, 20 m; does not meet multi-year requirements',
              'minimum_observations': 3, 'selection': 'Up to two distinct dates per month, tile 44QKF, cloud <=40%; lowest whole-tile cloud first',
              'aoi_sha256': hashlib.sha256(aoi_path.read_bytes()).hexdigest(), 'bounds': bounds,
              'scl_mask': [0, 1, 2, 3, 7, 8, 9, 10, 11], 'shadow_buffer_m': 60,
              'water_handling': 'Water frequencies reported separately; medians retain surface-water pixels. No automatic persistent-water exclusion.',
              'seasons': {}}
    composites = {}
    for season, (start, end) in SEASONS.items():
        cache = RAW / (season + '_catalogue.json')
        if cache.exists():
            items = json.loads(cache.read_text())
        else:
            url = API + '/search?' + urlencode({'collections': 'sentinel-2-c1-l2a', 'bbox': bbox,
                'datetime': start+'T00:00:00Z/'+end+'T23:59:59Z', 'limit': 100})
            items = []
            for _ in range(20):
                data = fetch(url)
                items.extend(data['features'])
                nxt = next((link for link in data.get('links', []) if link['rel'] == 'next'), None)
                if not nxt:
                    break
                if nxt.get('method', 'GET') != 'GET':
                    raise RuntimeError('Unsupported pagination method')
                url = urljoin(url, nxt['href'])
            else:
                raise RuntimeError('Catalogue pagination incomplete')
            cache.write_text(json.dumps(items), encoding='utf-8')
        eligible = [i for i in items if '_T44QKF_' in i['id'] and i['properties'].get('eo:cloud_cover', 101) <= 40]
        chosen = []
        for month in sorted({i['properties']['datetime'][:7] for i in eligible}):
            seen = set()
            for item in sorted([i for i in eligible if i['properties']['datetime'].startswith(month)],
                               key=lambda i: (i['properties']['eo:cloud_cover'], i['id'])):
                date = item['properties']['datetime'][:10]
                if date not in seen:
                    chosen.append(item)
                    seen.add(date)
                if len(seen) == 2:
                    break
        print(season, 'selected', [i['properties']['datetime'][:10] for i in chosen], flush=True)
        if not chosen:
            raise RuntimeError('No candidate dates for ' + season)
        stacks = {name: [] for name in ['NDVI', 'NDMI', 'MNDWI']}
        quality_stack, water_stack, broad_stack = [], [], []
        records = []
        for item in chosen:
            date = item['properties']['datetime'][:10]
            folder = RAW / item['id']
            folder.mkdir(exist_ok=True)
            (folder/'source_stac.json').write_text(json.dumps(item, indent=2), encoding='utf-8')
            arrays, valid, files = {}, np.ones(shape, dtype=bool), []
            for band, key in BANDS.items():
                asset = item['assets'][key]
                path = folder/(band+'.tif')
                if not path.exists():
                    print('Subset', date, band, flush=True)
                    temp = folder/(band+'.partial.tif')
                    ds = gdal.Warp(str(temp), '/vsicurl/'+asset['href'], format='GTiff',
                        dstSRS='EPSG:32644', outputBounds=bounds, xRes=20, yRes=20,
                        resampleAlg='near' if band == 'SCL' else 'average', dstNodata=0,
                        creationOptions=['COMPRESS=DEFLATE', 'TILED=YES'])
                    ds = None
                    temp.replace(path)
                ds = gdal.Open(str(path))
                assert ds.GetGeoTransform() == gt and ds.RasterXSize == width and ds.RasterYSize == height
                assert osr.SpatialReference(wkt=ds.GetProjection()).IsSame(dst)
                a = ds.ReadAsArray()
                meta = asset['raster:bands'][0]
                valid &= a != meta.get('nodata', 0)
                arrays[band] = a if band == 'SCL' else a.astype(float)*meta['scale']+meta['offset']
                files.append({'band': band, 'url': asset['href'], 'scale_offset': meta,
                              'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
            scl = arrays['SCL']
            assert np.isin(scl, range(12)).all()
            cloud = np.pad(np.isin(scl, [2, 3, 7, 8, 9, 10]), 3)
            dilated = np.zeros(shape, dtype=bool)
            for dy in range(-3, 4):
                for dx in range(-3, 4):
                    if dx*dx+dy*dy <= 9:
                        dilated |= cloud[3+dy:3+dy+height, 3+dx:3+dx+width]
            valid &= inside & ~np.isin(scl, report['scl_mask']) & ~dilated
            quality_stack.append(valid)
            values = {}
            for name, first, second in [('NDVI','B08','B04'),('NDMI','B08','B11'),('MNDWI','B03','B11')]:
                a, b = arrays[first], arrays[second]
                good = valid & (a >= 0) & (b >= 0) & ((a+b) > 1e-6)
                value = np.full(shape, np.nan)
                np.divide(a-b, a+b, out=value, where=good)
                assert np.all(np.abs(value[np.isfinite(value)]) <= 1.000001)
                stacks[name].append(value)
                values[name] = value
            water_stack.append(valid & (scl == 6))
            broad_stack.append(valid & ((scl == 6) | (values['MNDWI'] > 0)))
            records.append({'date': date, 'item_id': item['id'], 'cloud_percent_tile': item['properties']['eo:cloud_cover'],
                            'quality_valid_fraction_circle': float(valid[inside].mean()), 'files': files})
        qc = np.sum(quality_stack, axis=0)
        write(season+'_quality_count', np.where(inside, qc, np.nan))
        composites[season] = {}
        coverage = {}
        for name, values in stacks.items():
            stack = np.stack(values)
            count = np.isfinite(stack).sum(axis=0)
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', RuntimeWarning)
                median = np.nanmedian(stack, axis=0)
            median[count < 3] = np.nan
            write(season+'_'+name+'_count', np.where(inside, count, np.nan))
            write(season+'_'+name+'_median', median)
            assert not np.isfinite(median[count < 3]).any()
            composites[season][name] = median
            coverage[name] = {'fraction_circle_at_least_3': float((count[inside] >= 3).mean()),
                              'minimum_count_circle': int(count[inside].min()), 'maximum_count_circle': int(count[inside].max())}
        for label, masks in [('scl_water',water_stack),('broad_water',broad_stack)]:
            freq = np.full(shape, np.nan)
            np.divide(np.sum(masks, axis=0), qc, out=freq, where=inside & (qc >= 3))
            write(season+'_'+label+'_frequency', freq)
        report['seasons'][season] = {'observations': records, 'coverage': coverage}
        (OUT/'seasonal_manifest.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    for name in ['NDVI','NDMI','MNDWI']:
        delta = composites['post'][name]-composites['pre'][name]
        write('post_minus_pre_'+name, delta)
    make_project(OUT)
    report['gdal_version'] = gdal.VersionInfo()
    report['interpretation'] = 'Surface and crop/irrigation evidence. One sampled year; no recharge, groundwater depth, yield or validated potential claim.'
    (OUT/'seasonal_manifest.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    lines = ['2025 sampled seasonal Sentinel-2 pilot', '', report['interpretation'],
             'Pre = March-May; post = October-December. Grid: 20 m, EPSG:32644.',
             'Median pixels require at least 3 valid observations. NoData = -9999.',
             'Reflectance scale/offset applied exactly once from provider metadata.',
             'Water retained in medians; SCL and broad MNDWI water frequencies are separate diagnostics.', '']
    for season, details in report['seasons'].items():
        lines.append(season + ' dates: ' + ', '.join(r['date'] for r in details['observations']))
        for name, coverage in details['coverage'].items():
            lines.append(f"{name}: {100*coverage['fraction_circle_at_least_3']:.2f}% of circle has >=3 observations")
    lines.extend(['', 'Open seasonal_review_2025.qgz; toggle pre/post NDMI using the fixed -1 to +1 scale.',
                  'Count layers show coverage; zero counts are valid values, not low potential.',
                  'post_minus_pre files subtract seasonal medians and include surface water.',
                  'This sampled 2025 pilot does not meet the planned three-paired-year requirement.'])
    (OUT/'README.txt').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({s: d['coverage'] for s,d in report['seasons'].items()}, indent=2), flush=True)


def make_project(output):
    from qgis.core import (QgsApplication, QgsProject, QgsRasterLayer, QgsColorRampShader,
        QgsRasterShader, QgsSingleBandPseudoColorRenderer, QgsReferencedRectangle)
    from qgis.PyQt.QtGui import QColor
    app = QgsApplication([], False)
    app.initQgis()
    project = QgsProject.instance()
    project.setTitle('2025 sampled seasonal surface indicators - minimum 3 observations')
    for season in ['pre','post']:
        for name in ['NDVI','NDMI','MNDWI']:
            layer = QgsRasterLayer(str(output/(season+'_'+name+'_median.tif')), season+' 2025 '+name+' median')
            assert layer.isValid()
            ramp = QgsColorRampShader()
            ramp.setColorRampType(QgsColorRampShader.Interpolated)
            ramp.setColorRampItemList([QgsColorRampShader.ColorRampItem(x,QColor(c),str(x)) for x,c in
                                      [(-1,'#8c510a'),(0,'#f5f5f5'),(1,'#01665e')]])
            shader = QgsRasterShader(-1,1)
            shader.setRasterShaderFunction(ramp)
            renderer = QgsSingleBandPseudoColorRenderer(layer.dataProvider(),1,shader)
            renderer.setClassificationMin(-1)
            renderer.setClassificationMax(1)
            layer.setRenderer(renderer)
            project.addMapLayer(layer)
            project.layerTreeRoot().findLayer(layer.id()).setItemVisibilityChecked(season=='post' and name=='NDMI')
            project.setCrs(layer.crs())
            project.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(layer.extent(),layer.crs()))
        count = QgsRasterLayer(str(output/(season+'_NDMI_count.tif')),season+' NDMI observation count')
        project.addMapLayer(count)
        project.layerTreeRoot().findLayer(count.id()).setItemVisibilityChecked(False)
    assert project.write(str(output/'seasonal_review_2025.qgz'))


if __name__ == '__main__':
    main()
