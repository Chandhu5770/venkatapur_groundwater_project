"""Public MPC Sentinel-1 RTC 2025 pilot, same orbit/pass/platform and 30 m grid.

Run with QGIS Python. Temporary SAS URLs stay in memory and are not persisted.
"""
import hashlib
import argparse
import json
from pathlib import Path
from urllib.parse import urlencode,urljoin,urlparse
from urllib.request import urlopen
from urllib.error import HTTPError
import warnings
import time

import numpy as np
from osgeo import gdal

ROOT=Path(__file__).resolve().parents[1]
YEAR=2025
RAW=ROOT/f'data/raw/sentinel/s1/seasons_{YEAR}'
OUT=ROOT/f'data/processed/s1_seasons_{YEAR}'
HOST='https://planetarycomputer.microsoft.com'


def fetch(url):
    for attempt in range(4):
        try:
            with urlopen(url,timeout=60) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code not in [429,500,502,503,504] or attempt==3:
                raise
            time.sleep(min(20,5*(attempt+1)))


def main():
    gdal.UseExceptions()
    gdal.SetConfigOption('GDAL_DISABLE_READDIR_ON_OPEN','EMPTY_DIR')
    gdal.SetConfigOption('GDAL_HTTP_TIMEOUT','60')
    gdal.SetConfigOption('GDAL_HTTP_MAX_RETRY','2')
    RAW.mkdir(parents=True,exist_ok=True)
    OUT.mkdir(parents=True,exist_ok=True)
    ref=gdal.Open(str(ROOT/'data/processed/terrain_pilot/edge_underestimate_flag.tif'))
    gt=ref.GetGeoTransform()
    w,h=ref.RasterXSize,ref.RasterYSize
    bounds=[gt[0],gt[3]-h*30,gt[0]+w*30,gt[3]]
    inside=ref.ReadAsArray()!=ref.GetRasterBand(1).GetNoDataValue()

    def write(name,a):
        ds=gdal.GetDriverByName('GTiff').Create(str(OUT/(name+'.tif')),w,h,1,gdal.GDT_Float32,
                                               options=['COMPRESS=DEFLATE','TILED=YES'])
        ds.SetGeoTransform(gt)
        ds.SetProjection(ref.GetProjection())
        ds.GetRasterBand(1).SetNoDataValue(-9999)
        ds.GetRasterBand(1).WriteArray(np.where(inside&np.isfinite(a),a,-9999).astype('float32'))
        ds=None

    report={'source':'Microsoft Planetary Computer Sentinel-1 RTC, Catalyst processing, terrain-corrected gamma0 intensity',
        'selection':'Sentinel-1A, IW, VV+VH, relative orbit 165, descending; one slice per UTC date',
        'minimum_observations':3,'grid':'EPSG:32644, 30 m; matches terrain pilot',
        'processing':'Average source linear intensity to 30 m; seasonal median in linear intensity, then 10*log10. Positive pixels only.',
        'year':YEAR,
        'limitations':'Single-year pilot. Provider processing used PlanetDEM; orbit-source metadata retained. No additional speckle filtering, incidence-angle normalization or explicit layover mask. Shadow/invalid values masked when provided as NoData or nonpositive. Water/crop confounding remains; no suitability direction or combined score assigned.',
        'seasons':{}}
    results={}
    tokens={}
    for season,start,end in [('pre',f'{YEAR}-03-01',f'{YEAR}-05-31'),('post',f'{YEAR}-10-01',f'{YEAR}-12-31')]:
        cache=RAW/(season+'_catalogue.json')
        if cache.exists():
            items=json.loads(cache.read_text())
        else:
            url=HOST+'/api/stac/v1/search?'+urlencode({'collections':'sentinel-1-rtc',
                'bbox':'78.702826,18.785498,78.797705,18.875841',
                'datetime':start+'T00:00:00Z/'+end+'T23:59:59Z','limit':100})
            items=[]
            for _ in range(20):
                data=fetch(url)
                items.extend(data['features'])
                nxt=next((l for l in data.get('links',[]) if l['rel']=='next'),None)
                if not nxt:
                    break
                if nxt.get('method','GET')!='GET':
                    raise RuntimeError('Unsupported pagination')
                url=urljoin(url,nxt['href'])
            else:
                raise RuntimeError('Incomplete pagination')
            cache.write_text(json.dumps(items),encoding='utf-8')
        chosen={}
        for item in sorted(items,key=lambda i:i['id']):
            p=item['properties']
            if p.get('platform','').lower()!='sentinel-1a' or p.get('sat:relative_orbit')!=165 or p.get('sat:orbit_state')!='descending':
                continue
            if not {'VV','VH'}.issubset(p.get('sar:polarizations',[])):
                continue
            # The previously inspected slice 15 covers the complete planning circle.
            if str(p.get('s1:slice_number'))!='15':
                continue
            chosen.setdefault(p['datetime'][:10],item)
        if len(chosen)<3:
            raise RuntimeError('Fewer than three matched candidate dates in '+season)
        print(season,'matched dates:',list(chosen),flush=True)
        stacks={'vv':[],'vh':[]}
        records=[]
        for date,item in sorted(chosen.items()):
            folder=RAW/item['id']
            folder.mkdir(exist_ok=True)
            (folder/'source_stac.json').write_text(json.dumps(item,indent=2),encoding='utf-8')
            record={'date':date,'id':item['id'],'orbit_source':item['properties'].get('s1:orbit_source'),'files':[]}
            for pol in ['vv','vh']:
                asset=item['assets'][pol]
                path=folder/(pol+'_30m.tif')
                if not path.exists():
                    print('Radar subset',date,pol,flush=True)
                    # SAS is anonymous temporary public access; never write it to metadata or logs.
                    parsed=urlparse(asset['href'])
                    account=parsed.hostname.split('.')[0]
                    container=parsed.path.strip('/').split('/')[0]
                    token_key=(account,container)
                    if token_key not in tokens:
                        tokens[token_key]=fetch(HOST+'/api/sas/v1/token/'+account+'/'+container)['token']
                    signed=asset['href']+'?'+tokens[token_key].lstrip('?')
                    temp=folder/(pol+'.partial.tif')
                    gdal.PushErrorHandler('CPLQuietErrorHandler')
                    try:
                        ds=gdal.Warp(str(temp),'/vsicurl/'+signed,format='GTiff',
                            dstSRS='EPSG:32644',outputBounds=bounds,width=w,height=h,
                            resampleAlg='average',dstNodata=-9999,outputType=gdal.GDT_Float32,
                            creationOptions=['COMPRESS=DEFLATE','TILED=YES'])
                        ds=None
                    except Exception:
                        raise RuntimeError('Radar window read failed for '+date+' '+pol) from None
                    finally:
                        gdal.PopErrorHandler()
                    temp.replace(path)
                ds=gdal.Open(str(path))
                assert ds.GetGeoTransform()==gt and ds.GetProjection()==ref.GetProjection()
                a=ds.ReadAsArray().astype(float)
                a[(a<=0)|~inside]=np.nan
                stacks[pol].append(a)
                record['files'].append({'polarization':pol,'source_url':asset['href'],
                    'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                    'valid_fraction_circle':float(np.isfinite(a[inside]).mean())})
            records.append(record)
        results[season]={}
        coverage={}
        for pol,arrays in stacks.items():
            stack=np.stack(arrays)
            counts=np.isfinite(stack).sum(axis=0)
            with warnings.catch_warnings():
                warnings.simplefilter('ignore',RuntimeWarning)
                med=np.nanmedian(stack,axis=0)
            med[counts<3]=np.nan
            db=10*np.log10(med)
            write(season+'_'+pol+'_count',counts)
            write(season+'_'+pol+'_gamma0_linear_median',med)
            write(season+'_'+pol+'_gamma0_db_median',db)
            results[season][pol]=db
            coverage[pol]={'fraction_circle_at_least_3':float((counts[inside]>=3).mean()),
                'min_count_circle':int(counts[inside].min()),'max_count_circle':int(counts[inside].max())}
        write(season+'_vv_minus_vh_db',results[season]['vv']-results[season]['vh'])
        report['seasons'][season]={'observations':records,'coverage':coverage}
        (OUT/'radar_manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    for pol in ['vv','vh']:
        write('post_minus_pre_'+pol+'_db',results['post'][pol]-results['pre'][pol])
    make_project()
    (OUT/'README.txt').write_text(
        f'{YEAR} Sentinel-1A RTC pilot: orbit 165 descending, 30 m EPSG:32644.\n'
        'gamma0_linear_median files are linear backscatter; gamma0_db_median files are already 10*log10 converted.\n'
        'Counts require >=3 observations per pixel. NoData=-9999.\n'
        'post_minus_pre files are differences in dB, not absolute moisture or groundwater.\n'
        'vv_minus_vh_db is the dB representation of a ratio of separate seasonal linear medians.\n'
        'Provider metadata/methodology and limitations are in radar_manifest.json.\n'
        'Water remains included. Crop, roughness and viewing geometry can affect returns.\n',encoding='utf-8')
    print(json.dumps({s:v['coverage'] for s,v in report['seasons'].items()},indent=2),flush=True)


def make_project():
    from qgis.core import (QgsApplication,QgsProject,QgsRasterLayer,QgsReferencedRectangle,
        QgsColorRampShader,QgsRasterShader,QgsSingleBandPseudoColorRenderer)
    from qgis.PyQt.QtGui import QColor
    app=QgsApplication([],False)
    app.initQgis()
    project=QgsProject.instance()
    project.setTitle(f'{YEAR} Sentinel-1 RTC seasonal surface evidence')
    for season in ['pre','post']:
        for pol in ['vv','vh']:
            layer=QgsRasterLayer(str(OUT/(season+'_'+pol+'_gamma0_db_median.tif')),season+' '+pol.upper()+' gamma0 dB')
            assert layer.isValid()
            ramp=QgsColorRampShader()
            ramp.setColorRampType(QgsColorRampShader.Interpolated)
            ramp.setColorRampItemList([QgsColorRampShader.ColorRampItem(v,QColor(c),str(v)+' dB')
                                      for v,c in [(-30,'#101010'),(-15,'#888888'),(0,'#ffffff')]])
            shader=QgsRasterShader(-30,0)
            shader.setRasterShaderFunction(ramp)
            renderer=QgsSingleBandPseudoColorRenderer(layer.dataProvider(),1,shader)
            renderer.setClassificationMin(-30)
            renderer.setClassificationMax(0)
            layer.setRenderer(renderer)
            project.addMapLayer(layer)
            project.layerTreeRoot().findLayer(layer.id()).setItemVisibilityChecked(season=='post' and pol=='vv')
            project.setCrs(layer.crs())
            project.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(layer.extent(),layer.crs()))
        count=QgsRasterLayer(str(OUT/(season+'_vv_count.tif')),season+' VV valid observation count')
        project.addMapLayer(count)
        project.layerTreeRoot().findLayer(count.id()).setItemVisibilityChecked(False)
    assert project.write(str(OUT/f'radar_review_{YEAR}.qgz'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--year',type=int,default=2025,choices=range(2021,2026))
    YEAR=parser.parse_args().year
    RAW=ROOT/f'data/raw/sentinel/s1/seasons_{YEAR}'
    OUT=ROOT/f'data/processed/s1_seasons_{YEAR}'
    main()
