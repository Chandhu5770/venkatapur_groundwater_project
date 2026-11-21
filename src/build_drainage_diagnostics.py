"""D8 segment vectors and approximate 1 km moving-window drainage density.

Run with QGIS Python after build_terrain_pilot.py. No new downloads.
"""
import json
from pathlib import Path

import numpy as np
from osgeo import gdal, ogr, osr
from scipy.signal import fftconvolve

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'data/processed/terrain_pilot'
WORK = ROOT/'data/interim/terrain_pilot'
OUT = BASE/'drainage_diagnostics'
# GRASS: 1=NE, 2=N, 3=NW, 4=W, 5=SW, 6=S, 7=SE, 8=E.
OFFSETS = {1:(-1,1),2:(-1,0),3:(-1,-1),4:(0,-1),5:(1,-1),6:(1,0),7:(1,1),8:(0,1)}


def main():
    gdal.UseExceptions()
    OUT.mkdir(parents=True,exist_ok=True)
    ref=gdal.Open(str(WORK/'acc.tif'))
    acc=ref.ReadAsArray()
    direction=gdal.Open(str(WORK/'direction.tif')).ReadAsArray()
    gt=ref.GetGeoTransform()
    valid=np.isfinite(acc)&(acc>0)
    uncertain=(acc<0)|(acc==ref.GetRasterBand(1).GetNoDataValue())
    clipped=gdal.Open(str(BASE/'edge_underestimate_flag.tif'))
    cg=clipped.GetGeoTransform()
    x0=round((cg[0]-gt[0])/30)
    y0=round((gt[3]-cg[3])/30)
    h,w=clipped.RasterYSize,clipped.RasterXSize
    inside=clipped.ReadAsArray()!=clipped.GetRasterBand(1).GetNoDataValue()
    yy,xx=np.mgrid[-34:35,-34:35]
    kernel=((xx*30)**2+(yy*30)**2<=1000**2).astype(float)
    area=kernel.sum()*900/1e6
    uncertain_near=fftconvolve(uncertain.astype(float),kernel,mode='same')>.5
    support=fftconvolve(np.ones(acc.shape),kernel,mode='same')>=kernel.sum()-.5
    good=inside & ~uncertain_near[y0:y0+h,x0:x0+w] & support[y0:y0+h,x0:x0+w]
    srs=osr.SpatialReference(wkt=ref.GetProjection())
    geom=ogr.CreateGeometryFromJson(json.dumps(json.loads((ROOT/'data/reference/venkatapur_initial_study_area_5km.geojson').read_text())['features'][0]['geometry']))
    geographic=osr.SpatialReference()
    geographic.ImportFromEPSG(4326)
    for crs in [geographic,srs]:
        crs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    geom.Transform(osr.CoordinateTransformation(geographic,srs))
    gpkg=OUT/'stream_segments.gpkg'
    if gpkg.exists():
        raise FileExistsError('Review or rename existing stream_segments.gpkg before regenerating vectors')
    vector=ogr.GetDriverByName('GPKG').CreateDataSource(str(gpkg))
    report={'method':'Directed cell-centre segments following GRASS D8; each segment half-length allocated to each endpoint cell. Circular 1 km cell-centre neighbourhood convolution; approximate raster support, not exact vector-circle intersections.',
        'units':'stream km per km2','neighbourhood_radius_m':1000,'discrete_neighbourhood_area_km2':area,
        'uncertainty':'Density is NoData if any likely underestimated/missing flow cell falls within 1 km. Flags exported separately.',
        'source':'Existing Copernicus GLO-30/GRASS terrain pilot; no new source data',
        'direction_reference':'https://grass.osgeo.org/grass84/manuals/r.watershed.html',
        'thresholds':{}}

    def write(name,a,mask):
        ds=gdal.GetDriverByName('GTiff').Create(str(OUT/(name+'.tif')),w,h,1,gdal.GDT_Float32,options=['COMPRESS=DEFLATE','TILED=YES'])
        ds.SetGeoTransform(cg)
        ds.SetProjection(ref.GetProjection())
        ds.GetRasterBand(1).SetNoDataValue(-9999)
        ds.GetRasterBand(1).WriteArray(np.where(mask,a,-9999).astype('float32'))
        ds=None

    write('density_uncertainty_flag',(~good).astype(float),inside)
    for threshold in [.25,.5,1.0]:
        key=str(threshold).replace('.','p')
        layer=vector.CreateLayer('streams_'+key,srs,ogr.wkbMultiLineString)
        layer.CreateField(ogr.FieldDefn('length_m',ogr.OFTReal))
        stream=valid & (acc*900>=threshold*1e6)
        lengths=np.zeros(acc.shape)
        count,total=0,0.0
        vector.StartTransaction()
        for code,(dy,dx) in OFFSETS.items():
            rows,cols=np.where(stream & (direction==code))
            nr,nc=rows+dy,cols+dx
            keep=(nr>=0)&(nr<acc.shape[0])&(nc>=0)&(nc<acc.shape[1])
            rows,cols,nr,nc=rows[keep],cols[keep],nr[keep],nc[keep]
            keep=stream[nr,nc]
            rows,cols,nr,nc=rows[keep],cols[keep],nr[keep],nc[keep]
            distance=30*np.hypot(dy,dx)
            np.add.at(lengths,(rows,cols),distance/2)
            np.add.at(lengths,(nr,nc),distance/2)
            # Only intersect segments near the circle; density uses the full buffered network.
            near=(rows>=y0-1)&(rows<=y0+h)&(cols>=x0-1)&(cols<=x0+w)
            for r,c,r2,c2 in zip(rows[near],cols[near],nr[near],nc[near]):
                line=ogr.Geometry(ogr.wkbLineString)
                line.AddPoint_2D(gt[0]+(c+.5)*30,gt[3]-(r+.5)*30)
                line.AddPoint_2D(gt[0]+(c2+.5)*30,gt[3]-(r2+.5)*30)
                if not line.Intersects(geom):
                    continue
                clipped_line=line.Intersection(geom)
                if clipped_line.Length()<=0:
                    continue
                multi=ogr.ForceToMultiLineString(clipped_line)
                feature=ogr.Feature(layer.GetLayerDefn())
                feature.SetGeometry(multi)
                feature.SetField('length_m',multi.Length())
                layer.CreateFeature(feature)
                total+=multi.Length()
                count+=1
        vector.CommitTransaction()
        density=np.maximum(fftconvolve(lengths,kernel,mode='same'),0)/1000/area
        density=density[y0:y0+h,x0:x0+w]
        write('density_'+key+'_km_per_km2',density,good)
        report['thresholds'][str(threshold)]={'segments_in_circle':count,'length_km_in_circle':total/1000,
            'density_valid_pixels':int(good.sum()),'density_median':float(np.median(density[good]))}
        print(threshold,report['thresholds'][str(threshold)],flush=True)
    vector=None
    report['limitations']='DEM-derived drainage diagnostics require imagery/field review. No measured streams, aquifer properties or groundwater suitability direction established.'
    (OUT/'drainage_manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    make_project()


def make_project():
    from qgis.core import QgsApplication,QgsProject,QgsRasterLayer,QgsVectorLayer,QgsReferencedRectangle
    app=QgsApplication([],False)
    app.initQgis()
    project=QgsProject.instance()
    project.setTitle('Provisional drainage segments and density - 30 m')
    density=QgsRasterLayer(str(OUT/'density_0p5_km_per_km2.tif'),'1 km drainage density (km/km2), threshold 0.5 km2')
    assert density.isValid()
    project.addMapLayer(density)
    project.setCrs(density.crs())
    project.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(density.extent(),density.crs()))
    streams=QgsVectorLayer(str(OUT/'stream_segments.gpkg')+'|layername=streams_0p5','D8 stream segments, threshold 0.5 km2','ogr')
    assert streams.isValid()
    from qgis.PyQt.QtGui import QColor
    streams.renderer().symbol().setColor(QColor('#1565c0'))
    project.addMapLayer(streams)
    flag=QgsRasterLayer(str(OUT/'density_uncertainty_flag.tif'),'Density uncertainty: 1=excluded')
    project.addMapLayer(flag)
    project.layerTreeRoot().findLayer(flag.id()).setItemVisibilityChecked(False)
    assert project.write(str(OUT/'drainage_review.qgz'))


if __name__=='__main__':
    main()
