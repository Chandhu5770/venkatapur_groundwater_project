"""30 m terrain pilot using public Copernicus GLO-30 and GRASS D8 routing.

Run with QGIS Python. --worker is an internal GRASS subprocess entry point.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
from osgeo import gdal, ogr, osr

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'data/interim/terrain_pilot'
OUT = ROOT / 'data/processed/terrain_pilot'
GRASS = Path('C:/Program Files/QGIS 3.40.11/apps/grass/grass84')


def grass_worker(work):
    sys.path.insert(0, str(GRASS/'etc/python'))
    import grass.script as gs
    import grass.script.setup as setup
    # GRASS 8.4 queries debug level before create_location's temporary GISRC is used.
    # Establish the default explicitly when starting outside an existing session.
    gs.core._debug_level = 0
    if not (work/'grass/utm44/PERMANENT').exists():
        (work/'grass').mkdir(exist_ok=True)
        gs.create_location(str(work/'grass'), 'utm44', epsg=32644)
    with setup.init(str(work/'grass/utm44/PERMANENT'), grass_path=str(GRASS)):
        gs.run_command('r.in.gdal', input=str(work/'dem_30m.tif'), output='dem', overwrite=True, quiet=True)
        gs.run_command('g.region', raster='dem')
        # Keep negative accumulation to retain the provider's edge-underestimate signal.
        gs.run_command('r.watershed', flags='s', elevation='dem', accumulation='acc',
                       drainage='direction', memory=512, overwrite=True, quiet=True)
        for name in ['acc', 'direction']:
            gs.run_command('r.out.gdal', flags='c', input=name, output=str(work/(name+'.tif')),
                           format='GTiff', type='Float64', nodata=-1e30,
                           createopt='COMPRESS=DEFLATE', overwrite=True, quiet=True)


def main():
    gdal.UseExceptions()
    gdal.SetConfigOption('GDAL_DISABLE_READDIR_ON_OPEN', 'EMPTY_DIR')
    gdal.SetConfigOption('GDAL_HTTP_TIMEOUT', '60')
    gdal.SetConfigOption('GDAL_HTTP_MAX_RETRY', '2')
    WORK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    source_dir = ROOT/'data/interim/public_inputs/dem/copernicus_glo30'
    source_dir.mkdir(parents=True, exist_ok=True)
    aoi_path = ROOT/'data/reference/venkatapur_initial_study_area_5km.geojson'
    geometry = json.loads(aoi_path.read_text())['features'][0]['geometry']
    src, dst = osr.SpatialReference(), osr.SpatialReference()
    src.ImportFromEPSG(4326)
    dst.ImportFromEPSG(32644)
    for crs in [src, dst]:
        crs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    forward = osr.CoordinateTransformation(src, dst)
    backward = osr.CoordinateTransformation(dst, src)
    centre = forward.TransformPoint(78.75026556626672, 18.83066925215722)
    geom = ogr.CreateGeometryFromJson(json.dumps(geometry))
    geom.Transform(forward)
    vector = ogr.GetDriverByName('Memory').CreateDataSource('')
    layer = vector.CreateLayer('circle', dst, ogr.wkbPolygon)
    feature = ogr.Feature(layer.GetLayerDefn())
    feature.SetGeometry(geom)
    layer.CreateFeature(feature)
    env = os.environ.copy()
    env['GISBASE'] = str(GRASS)
    env['PATH'] = os.pathsep.join([str(GRASS/'bin'), str(GRASS/'scripts'), str(GRASS/'lib'), env['PATH']])
    env['GRASS_PYTHON'] = sys.executable
    env['GRASS_PROJSHARE'] = 'C:/Program Files/QGIS 3.40.11/share/proj'
    attempts, sources = [], {}
    for radius in [15000, 25000]:
        bounds = [math.floor((centre[0]-radius)/30)*30, math.floor((centre[1]-radius)/30)*30,
                  math.ceil((centre[0]+radius)/30)*30, math.ceil((centre[1]+radius)/30)*30]
        corners = [backward.TransformPoint(x,y) for x in [bounds[0],bounds[2]] for y in [bounds[1],bounds[3]]]
        urls = []
        for lat in range(math.floor(min(p[1] for p in corners)), math.floor(max(p[1] for p in corners))+1):
            for lon in range(math.floor(min(p[0] for p in corners)), math.floor(max(p[0] for p in corners))+1):
                tile = f'Copernicus_DSM_COG_10_N{lat:02d}_00_E{lon:03d}_00_DEM'
                url = f'https://copernicus-dem-30m.s3.amazonaws.com/{tile}/{tile}.tif'
                urls.append('/vsicurl/'+url)
                sources[tile] = url
        print('Preparing DEM extent', radius, 'm radius;', len(urls), 'source tiles', flush=True)
        local = source_dir/f'copdem_subset_{radius}m.tif'
        if not local.exists():
            vrt = gdal.BuildVRT('', urls)
            if vrt is None:
                raise RuntimeError('No public DEM source could be opened')
            ds = gdal.Warp(str(local), vrt, dstSRS='EPSG:32644', outputBounds=bounds,
                xRes=30, yRes=30, resampleAlg='bilinear', dstNodata=-9999,
                outputType=gdal.GDT_Float32, creationOptions=['COMPRESS=DEFLATE','TILED=YES'])
            ds = None
        # Release the previous iteration's dataset before replacing the working DEM on Windows.
        ref = None
        ds = gdal.Translate(str(WORK/'dem_30m.tif'), str(local))
        ds = None
        subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker', str(WORK)], env=env, check=True)
        ref = gdal.Open(str(WORK/'dem_30m.tif'))
        mem = gdal.GetDriverByName('MEM').Create('', ref.RasterXSize, ref.RasterYSize, 1, gdal.GDT_Byte)
        mem.SetGeoTransform(ref.GetGeoTransform())
        mem.SetProjection(ref.GetProjection())
        gdal.RasterizeLayer(mem,[1],layer,burn_values=[1])
        inside = mem.ReadAsArray()==1
        acc_ds = gdal.Open(str(WORK/'acc.tif'))
        acc = acc_ds.ReadAsArray()
        acc[acc == acc_ds.GetRasterBand(1).GetNoDataValue()] = np.nan
        acc_ds = None
        assert acc.shape == inside.shape
        under = acc < 0
        attempts.append({'radius_m':radius,'bounds':bounds,'aoi_edge_underestimate_pixels':int((inside & under).sum())})
        print('Upstream boundary check:', attempts[-1], flush=True)
        if not (inside & under).any():
            break
    gdal.DEMProcessing(str(WORK/'slope.tif'), str(WORK/'dem_30m.tif'), 'slope', computeEdges=False)
    gdal.DEMProcessing(str(WORK/'hillshade.tif'), str(WORK/'dem_30m.tif'), 'hillshade', computeEdges=False)
    gt = ref.GetGeoTransform()
    ys, xs = np.where(inside)
    y0,y1,x0,x1 = map(int, (ys.min(),ys.max()+1,xs.min(),xs.max()+1))
    clipmask = inside[y0:y1,x0:x1]
    clipgt = (gt[0]+x0*30,30,0,gt[3]-y0*30,0,-30)

    def write(name,array,valid=None):
        a = array[y0:y1,x0:x1].astype(float)
        good = clipmask & np.isfinite(a) & (a != -9999)
        if valid is not None:
            good &= valid[y0:y1,x0:x1]
        output = gdal.GetDriverByName('GTiff').Create(str(OUT/(name+'.tif')),x1-x0,y1-y0,1,gdal.GDT_Float32,
                                                    options=['COMPRESS=DEFLATE','TILED=YES'])
        output.SetGeoTransform(clipgt)
        output.SetProjection(ref.GetProjection())
        output.GetRasterBand(1).SetNoDataValue(-9999)
        output.GetRasterBand(1).WriteArray(np.where(good,a,-9999).astype('float32'))
        output = None

    dem = ref.ReadAsArray()
    assert not (dem[inside]==-9999).any()
    slope = gdal.Open(str(WORK/'slope.tif')).ReadAsArray()
    valid = (acc>0) & (slope>=0) & (slope<=90)
    write('elevation_m',dem)
    write('slope_degrees',slope)
    write('hillshade',gdal.Open(str(WORK/'hillshade.tif')).ReadAsArray())
    write('edge_underestimate_flag',under.astype(float))
    write('contributing_area_km2',np.abs(acc)*900/1e6,valid)
    write('flow_direction_d8',gdal.Open(str(WORK/'direction.tif')).ReadAsArray(),valid)
    twi = np.full(acc.shape,np.nan)
    # GRASS counts include each cell's own unit contribution; contour width = 30 m.
    twi[valid] = np.log((acc[valid]*900/30)/np.tan(np.radians(np.maximum(slope[valid],.1))))
    write('twi',twi,valid)
    for threshold in [.25,.5,1.0]:
        streams = (np.abs(acc)*900 >= threshold*1e6) & valid
        write('drainage_'+str(threshold).replace('.','p')+'_km2',streams.astype(float),valid)
    # Distance to the 0.5 km2 stream grid on the full processing extent before clipping.
    streams = ((np.abs(acc)*900 >= .5e6) & valid).astype('uint8')
    s = gdal.GetDriverByName('MEM').Create('',ref.RasterXSize,ref.RasterYSize,1,gdal.GDT_Byte)
    s.SetGeoTransform(gt)
    s.SetProjection(ref.GetProjection())
    s.GetRasterBand(1).WriteArray(streams)
    distance = gdal.GetDriverByName('MEM').Create('',ref.RasterXSize,ref.RasterYSize,1,gdal.GDT_Float32)
    gdal.ComputeProximity(s.GetRasterBand(1),distance.GetRasterBand(1),['VALUES=1','DISTUNITS=GEO'])
    write('distance_to_drainage_m',distance.ReadAsArray(),valid)
    manifest = {'source':'Copernicus GLO-30 Public, AWS 2021 release; DSM includes buildings and vegetation',
        'source_change':'Public-access alternative to planned SRTM; do not describe this as SRTM.',
        'source_urls':sources,'licence':'https://registry.opendata.aws/copernicus-dem/',
        'processing':'GDAL bilinear warp to EPSG:32644, fixed 30 m lattice; GRASS r.watershed -s D8, no -a flag.',
        'depressions':'GRASS least-cost routing handles depressions; no blanket filling/breaching or tank removal. No surveyed depression mask available.',
        'slope':'GDAL Horn slope in degrees; TWI uses floor 0.1 degrees, contributing area / 30 m contour width.',
        'accumulation':'GRASS unit contribution includes current cell; 900 m2 per cell. Negative estimates are flagged and excluded from hydrology outputs.',
        'attempts':attempts,'grid_transform':clipgt,'shape':[int(y1-y0),int(x1-x0)],
        'aoi_pixels':int(inside.sum()),'hydrology_valid_pixels':int((inside & valid).sum()),
        'slope_range_degrees':[float(slope[inside].min()),float(slope[inside].max())],
        'dem_range_m':[float(dem[inside].min()),float(dem[inside].max())],
        'dem_subset_sha256':hashlib.sha256(local.read_bytes()).hexdigest(),
        'limits':'Provisional terrain context. Streams require imagery review; reservoirs and DSM artifacts can alter paths. No aquifer, recharge, yield, depth or groundwater-potential inference. No water mask applied to terrain; review open water before later combination.',
        'gdal_version':gdal.VersionInfo()}
    (OUT/'terrain_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    (OUT/'README.txt').write_text(
        'Venkatapur terrain pilot: EPSG:32644, 30 m.\n'
        'Source is Copernicus GLO-30 Public DSM (AWS 2021 release), not SRTM.\n'
        'Slope is in degrees; elevation and drainage distance are metres; contributing area is km2.\n'
        'TWI = ln((contributing area m2 / 30 m) / tan(max(slope,0.1 degrees))).\n'
        'Stream rasters: 1=extracted drainage, 0=below threshold; thresholds 0.25, 0.5 and 1 km2.\n'
        'Negative GRASS accumulation flags likely upstream underestimation. These cells are NoData in hydrology outputs.\n'
        'See terrain_manifest.json for extent tests and counts. Larger extents are not proof of complete catchments.\n'
        'Routing crosses depressions using GRASS least-cost logic; tanks and DSM artifacts need imagery review.\n'
        'Distances may be affected by omitted uncertain stream segments. Drainage density/vector streams remain pending.\n'
        'Seasonal optical layers in the review project retain their native 20 m pilot grid.\n'
        'Water remains unmasked in terrain. No weighted overlay or groundwater score is produced.\n',encoding='utf-8')
    make_project()
    print(json.dumps(manifest,indent=2),flush=True)


def make_project():
    from qgis.core import (QgsApplication,QgsProject,QgsRasterLayer,QgsReferencedRectangle,
                          QgsColorRampShader,QgsRasterShader,QgsSingleBandPseudoColorRenderer)
    from qgis.PyQt.QtGui import QColor
    app=QgsApplication([],False)
    app.initQgis()
    project=QgsProject.instance()
    project.setTitle('Venkatapur 30 m terrain pilot - provisional hydrology')
    for name in ['elevation_m','hillshade','slope_degrees','twi','contributing_area_km2','drainage_0p5_km2','edge_underestimate_flag']:
        layer=QgsRasterLayer(str(OUT/(name+'.tif')),name)
        assert layer.isValid()
        if name=='slope_degrees':
            ramp=QgsColorRampShader()
            ramp.setColorRampType(QgsColorRampShader.Interpolated)
            ramp.setColorRampItemList([QgsColorRampShader.ColorRampItem(v,QColor(c),str(v)+' degrees')
                for v,c in [(0,'#ffffcc'),(5,'#a1dab4'),(15,'#41b6c4'),(30,'#253494')]])
            shader=QgsRasterShader(0,30)
            shader.setRasterShaderFunction(ramp)
            renderer=QgsSingleBandPseudoColorRenderer(layer.dataProvider(),1,shader)
            renderer.setClassificationMin(0)
            renderer.setClassificationMax(30)
            layer.setRenderer(renderer)
        project.addMapLayer(layer)
        project.layerTreeRoot().findLayer(layer.id()).setItemVisibilityChecked(name=='slope_degrees')
        project.setCrs(layer.crs())
        project.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(layer.extent(),layer.crs()))
    for season in ['pre','post']:
        path=ROOT/'data/processed/s2_seasons_2025'/(season+'_NDMI_median.tif')
        if path.exists():
            layer=QgsRasterLayer(str(path),season+' 2025 NDMI (20 m optical pilot)')
            assert layer.isValid()
            project.addMapLayer(layer)
            project.layerTreeRoot().findLayer(layer.id()).setItemVisibilityChecked(False)
    assert project.write(str(OUT/'terrain_review.qgz'))


if __name__=='__main__':
    if '--worker' in sys.argv:
        grass_worker(Path(sys.argv[-1]))
    else:
        main()
