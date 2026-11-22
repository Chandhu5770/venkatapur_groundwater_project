"""Align optical pilot to 30 m and review descriptive correlations/confounding.

Run with QGIS Python. Correlations are spatially autocorrelated diagnostics,
not accuracy/validation; vegetation exclusions do not identify irrigation.
"""
import csv
import json
from pathlib import Path

import numpy as np
from osgeo import gdal
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
TERRAIN = ROOT/'data/processed/terrain_pilot'
OPTICAL = ROOT/'data/processed/s2_seasons_2025'
OUT = ROOT/'data/processed/indicator_review'


def main():
    gdal.UseExceptions()
    OUT.mkdir(parents=True,exist_ok=True)
    ref=gdal.Open(str(TERRAIN/'slope_degrees.tif'))
    gt=ref.GetGeoTransform()
    w,h=ref.RasterXSize,ref.RasterYSize
    bounds=[gt[0],gt[3]-h*30,gt[0]+w*30,gt[3]]
    circle_ds=gdal.Open(str(TERRAIN/'edge_underestimate_flag.tif'))
    circle=circle_ds.ReadAsArray()!=circle_ds.GetRasterBand(1).GetNoDataValue()

    def read(path,align=False):
        ds=gdal.Open(str(path))
        if align:
            ds=gdal.Warp('',ds,format='MEM',dstSRS='EPSG:32644',outputBounds=bounds,
                         width=w,height=h,resampleAlg='average',dstNodata=-9999)
        assert ds.GetGeoTransform()==gt and ds.GetProjection()==ref.GetProjection()
        a=ds.ReadAsArray().astype(float)
        a[a==ds.GetRasterBand(1).GetNoDataValue()]=np.nan
        a[~circle]=np.nan
        return a

    def save(name,a):
        ds=gdal.GetDriverByName('GTiff').Create(str(OUT/(name+'.tif')),w,h,1,gdal.GDT_Float32,
                                               options=['COMPRESS=DEFLATE','TILED=YES'])
        ds.SetGeoTransform(gt)
        ds.SetProjection(ref.GetProjection())
        ds.GetRasterBand(1).SetNoDataValue(-9999)
        ds.GetRasterBand(1).WriteArray(np.where(np.isfinite(a),a,-9999).astype('float32'))
        ds=None

    values={'slope':read(TERRAIN/'slope_degrees.tif'), 'twi':read(TERRAIN/'twi.tif'),
            'drainage_density':read(TERRAIN/'drainage_diagnostics/density_0p5_km_per_km2.tif')}
    water={}
    for season in ['pre','post']:
        for index in ['NDVI','NDMI','MNDWI']:
            a=read(OPTICAL/(season+'_'+index+'_median.tif'),True)
            # Require essentially full source support, so an average cannot bridge coverage gaps.
            source=gdal.Open(str(OPTICAL/(season+'_'+index+'_median.tif')))
            support=source.ReadAsArray()!=source.GetRasterBand(1).GetNoDataValue()
            mem=gdal.GetDriverByName('MEM').Create('',source.RasterXSize,source.RasterYSize,1,gdal.GDT_Byte)
            mem.SetGeoTransform(source.GetGeoTransform())
            mem.SetProjection(source.GetProjection())
            mem.GetRasterBand(1).WriteArray(support.astype('uint8'))
            fraction=gdal.Warp('',mem,format='MEM',dstSRS='EPSG:32644',outputBounds=bounds,
                               width=w,height=h,resampleAlg='average',outputType=gdal.GDT_Float32).ReadAsArray()
            a[fraction<.999]=np.nan
            values[season+'_'+index.lower()]=a
            save(season+'_'+index+'_30m',a)
        for method in ['scl','broad']:
            water[season+'_'+method]=read(OPTICAL/(season+'_'+method+'_water_frequency.tif'),True)
    values['ndmi_change']=values['post_ndmi']-values['pre_ndmi']
    values['ndvi_change']=values['post_ndvi']-values['pre_ndvi']
    scl_known=np.isfinite(water['pre_scl'])&np.isfinite(water['post_scl'])
    broad_known=np.isfinite(water['pre_broad'])&np.isfinite(water['post_broad'])
    scl_flag=(water['pre_scl']>=.5)|(water['post_scl']>=.5)
    broad_flag=(water['pre_broad']>=.5)|(water['post_broad']>=.5)
    vegetation_known=np.isfinite(values['pre_ndvi'])&np.isfinite(values['post_ndvi'])
    vegetation=(values['pre_ndvi']>.3)|(values['post_ndvi']>.3)
    scenarios={'all_available':circle,
               'exclude_scl_frequency_ge_0p5':circle&scl_known&~scl_flag,
               'exclude_broad_frequency_ge_0p5':circle&broad_known&~broad_flag,
               'exclude_scl_and_ndvi_gt_0p3':circle&scl_known&~scl_flag&vegetation_known&~vegetation}
    pairs=[('pre_ndvi','pre_ndmi'),('post_ndvi','post_ndmi'),('ndvi_change','ndmi_change'),
           ('slope','twi'),('slope','pre_ndmi'),('twi','pre_ndmi'),
           ('slope','ndmi_change'),('twi','ndmi_change'),('drainage_density','twi'),
           ('drainage_density','pre_ndmi')]
    radar=ROOT/'data/processed/s1_seasons_2025'
    if (radar/'radar_manifest.json').exists():
        values['radar_vv_change_db']=read(radar/'post_minus_pre_vv_db.tif')
        values['radar_vh_change_db']=read(radar/'post_minus_pre_vh_db.tif')
        pairs.extend([('radar_vv_change_db','ndmi_change'),('radar_vv_change_db','ndvi_change'),
                      ('radar_vh_change_db','ndvi_change'),('radar_vv_change_db','radar_vh_change_db'),
                      ('radar_vv_change_db','twi')])
    rows=[]
    summaries={}
    for scenario,mask in scenarios.items():
        summaries[scenario]={'eligible_pixels_before_pairwise_missingness':int(mask.sum())}
        for first,second in pairs:
            good=mask&np.isfinite(values[first])&np.isfinite(values[second])
            a,b=values[first][good],values[second][good]
            informative=a.size>=3 and np.ptp(a)>1e-10 and np.ptp(b)>1e-10
            rows.append({'scenario':scenario,'first':first,'second':second,'paired_pixels':int(a.size),
                         'pearson':float(np.corrcoef(a,b)[0,1]) if informative else None,
                         'spearman':float(spearmanr(a,b).statistic) if informative else None})
        good=mask&np.isfinite(values['ndmi_change'])
        summaries[scenario]['ndmi_change_pixels']=int(good.sum())
        summaries[scenario]['median_ndmi_change']=float(np.median(values['ndmi_change'][good])) if good.any() else None
        save('scenario_'+scenario,np.where(circle,mask.astype(float),np.nan))
    with (OUT/'correlations.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    report={'scope':'Descriptive evidence review only. No combined weights or groundwater score.',
        'optical_alignment':'Area averaging of already computed seasonal indices onto the terrain 30 m grid; require >=99.9% valid fine-grid support per target cell. Not recomputed from median reflectance.',
        'water_scenarios':'SCL/broad seasonal flag frequency >=0.5 on either season; provisional exclusions, not confirmed persistent water. Missing frequency excluded from exclusion scenarios.',
        'vegetation_scenario':'NDVI >0.3 in either season is a sensitivity assumption only; does not classify crops or irrigation.',
        'correlation_limits':'Pairwise valid pixels differ. Spatial autocorrelation and shared bands undermine independence; no significance tests or validation claims.',
        'scenarios':summaries,'correlations':rows,
        'next':'Review redundancy, unresolved water/crop confounding and spatial patterns. Rainfall and multi-year coverage remain pending; check radar manifest for provider limitations when radar pairs are present. Combined weights stay unset.'}
    (OUT/'review_summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    lines=['Indicator correlation and confounding review - 2025 pilot','',report['scope'],report['correlation_limits'],'']
    for row in rows:
        if row['scenario']=='exclude_scl_frequency_ge_0p5':
            lines.append(f"{row['first']} vs {row['second']}: n={row['paired_pixels']}; Pearson={row['pearson']}; Spearman={row['spearman']}")
    lines.extend(['',json.dumps(summaries,indent=2),'',report['vegetation_scenario'],'',report['next']])
    (OUT/'review_report.txt').write_text('\n'.join(lines),encoding='utf-8')
    print('\n'.join(lines))


if __name__=='__main__':
    main()
