"""Create a portable, offline QGIS review ZIP and illustrated PDF overview.

Run with QGIS Python after create_pilot_review.py. All artifacts stay under
Git-ignored data/processed/share/. No publication or upload is performed.
"""
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

import numpy as np
from osgeo import gdal

ROOT=Path(__file__).resolve().parents[1]
PROCESSED=ROOT/'data/processed'


def main():
    from qgis.core import (QgsApplication,QgsProject,QgsRasterLayer,QgsVectorLayer,
        QgsReferencedRectangle,Qgis,QgsColorRampShader,QgsRasterShader,QgsSingleBandPseudoColorRenderer)
    from qgis.PyQt.QtGui import QColor
    app=QgsApplication([],False)
    app.initQgis()
    parent=PROCESSED/'share'
    parent.mkdir(exist_ok=True)
    folder=parent/'venkatapur_2025_pilot'
    if folder.exists():
        raise FileExistsError('Package directory already exists; rename it before generating another release')
    folder.mkdir()
    status=json.loads((PROCESSED/'pilot_review/pilot_status.json').read_text())
    project=QgsProject.instance()
    project.setTitle('Venkatapur 2025 exploratory evidence pilot')
    project.setFilePathStorage(Qgis.FilePathType.Relative)
    copied=[]
    for spec in status['layers']:
        relative=Path(spec['path'])
        target=folder/'data'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(PROCESSED/relative,target)
        copied.append(target)
        layer=QgsRasterLayer(str(target),spec['label'])
        assert layer.isValid()
        filename=relative.name
        if 'NDMI_30m' in filename or 'NDVI_30m' in filename:
            stops=[(-1,'#8c510a'),(0,'#f5f5f5'),(1,'#01665e')]
        elif 'gamma0_db_median' in filename:
            stops=[(-30,'#101010'),(-15,'#888888'),(0,'#ffffff')]
        elif 'post_minus_pre_vv' in filename:
            stops=[(-6,'#2166ac'),(0,'#f5f5f5'),(6,'#b2182b')]
        elif 'slope' in filename:
            stops=[(0,'#ffffcc'),(5,'#a1dab4'),(15,'#41b6c4'),(30,'#253494')]
        else:
            stops=None
        if stops:
            ramp=QgsColorRampShader()
            ramp.setColorRampType(QgsColorRampShader.Interpolated)
            ramp.setColorRampItemList([QgsColorRampShader.ColorRampItem(v,QColor(c),str(v)) for v,c in stops])
            shader=QgsRasterShader(stops[0][0],stops[-1][0])
            shader.setRasterShaderFunction(ramp)
            renderer=QgsSingleBandPseudoColorRenderer(layer.dataProvider(),1,shader)
            renderer.setClassificationMin(stops[0][0])
            renderer.setClassificationMax(stops[-1][0])
            layer.setRenderer(renderer)
        project.addMapLayer(layer)
        project.layerTreeRoot().findLayer(layer.id()).setItemVisibilityChecked('post_NDMI_30m' in filename)
        if 'post_NDMI_30m' in filename:
            project.setCrs(layer.crs())
            project.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(layer.extent(),layer.crs()))
    relative=Path('terrain_pilot/drainage_diagnostics/stream_segments.gpkg')
    target=folder/'data'/relative
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(PROCESSED/relative,target)
    streams=QgsVectorLayer(str(target)+'|layername=streams_0p5','Provisional stream segments (0.5 km2 threshold)','ogr')
    assert streams.isValid()
    project.addMapLayer(streams)
    project.layerTreeRoot().findLayer(streams.id()).setItemVisibilityChecked(False)
    reference=folder/'reference'
    reference.mkdir()
    for filename in ['venkatapur_village_centre.geojson','venkatapur_initial_study_area_5km.geojson']:
        shutil.copy2(ROOT/'data/reference'/filename,reference/filename)
    # Include concise provenance and methodology, with no authentication material.
    metadata=folder/'metadata'
    metadata.mkdir()
    for relative in ['s2_seasons_2025/seasonal_manifest.json','s1_seasons_2025/radar_manifest.json',
                     'terrain_pilot/terrain_manifest.json','terrain_pilot/drainage_diagnostics/drainage_manifest.json',
                     'indicator_review/review_summary.json','indicator_review/correlations.csv']:
        shutil.copy2(PROCESSED/relative,metadata/Path(relative).name)
    code=folder/'code'
    code.mkdir()
    for source in (ROOT/'src').glob('*.py'):
        shutil.copy2(source,code/source.name)
    shutil.copy2(ROOT/'docs/04_public_satellite_data_plan.md',metadata/'methodology_plan.md')
    assert project.write(str(folder/'OPEN_IN_QGIS.qgz'))
    guide='''VENKATAPUR 2025 PILOT - REVIEW GUIDE

1. Extract the entire ZIP into a normal folder. Do not open the project inside the ZIP.
2. Install/use QGIS (built and tested with QGIS 3.40.11).
3. Open OPEN_IN_QGIS.qgz. Keep its data and reference folders together when moving it.
4. View one raster at a time. Post-monsoon NDMI is initially visible.
5. Compare pre/post NDMI or NDVI using fixed -1 to +1 scales. Radar uses -30 to 0 dB.
6. Read Pilot_Overview.pdf and metadata/review_summary.json before interpreting patterns.

Pre-monsoon means March-May 2025; post-monsoon means October-December 2025.
Optical uses six sampled dates per season, with >=3 valid observations per pixel.
Radar uses eight matched Sentinel-1A orbit-165 descending dates per season.
Aligned indicators use 30 m UTM zone 44N (EPSG:32644); optical count maps retain 20 m.
NoData is -9999; a count of zero is different from missing data.

These are surface and terrain evidence layers for an exploratory research pilot.
The 5 km circle is a planning buffer; a village administrative boundary is unverified.
Rainfall, multi-year coverage, field assessment and combined scenario sensitivity are pending.
No combined score, groundwater depth, borewell yield or drilling recommendation is provided.
No supervised machine learning is used. Satellites cannot directly detect groundwater.

Testers can check project opening, missing layers, legends, date switching, coverage counts,
and whether limitations are clear. Those checks do not validate aquifer conditions.
Report issues with the layer name, action taken, expected result and actual result.

Source: modified Copernicus Sentinel data (2025), distributed through Earth Search and
Microsoft Planetary Computer. Terrain: Copernicus GLO-30 Public, AWS 2021 release.
Source URLs and processing assumptions are in metadata/. Observe the upstream data terms.
https://registry.opendata.aws/sentinel-2-l2a-cogs/
https://planetarycomputer.microsoft.com/dataset/sentinel-1-rtc
https://registry.opendata.aws/copernicus-dem/

Code is included as a reference snapshot. Reproduction requires the repository structure
and source downloads; this ZIP is designed primarily for offline map review.
'''
    (folder/'START_HERE.txt').write_text(guide,encoding='utf-8')
    make_pdf(folder)
    # Detect accidental credential signatures before including text metadata in a release.
    for path in folder.rglob('*'):
        if path.suffix in ['.json','.txt','.csv','.py','.md']:
            content=path.read_text(encoding='utf-8').lower()
            if path.suffix!='.py':
                assert '?sig=' not in content and '&sig=' not in content
    checksums={str(p.relative_to(folder)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
               for p in folder.rglob('*') if p.is_file()}
    (folder/'checksums.json').write_text(json.dumps(checksums,indent=2),encoding='utf-8')
    archive=parent/(folder.name+'.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for path in folder.rglob('*'):
            if path.is_file():
                z.write(path,str(Path(folder.name)/path.relative_to(folder)))
    print('Package:',archive)
    print('ZIP size MB:',round(archive.stat().st_size/1e6,2))


def make_pdf(folder):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Image,PageBreak
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.pagesizes import A4
    gdal.UseExceptions()
    figure,axes=plt.subplots(2,2,figsize=(9,8),constrained_layout=True)
    for ax,(relative,title,low,high,cmap) in zip(axes.flat,[
        ('indicator_review/pre_NDMI_30m.tif','Pre-monsoon NDMI',-1,1,'BrBG'),
        ('indicator_review/post_NDMI_30m.tif','Post-monsoon NDMI',-1,1,'BrBG'),
        ('s1_seasons_2025/pre_vv_gamma0_db_median.tif','Pre-monsoon VV gamma0 (dB)',-30,0,'gray'),
        ('s1_seasons_2025/post_vv_gamma0_db_median.tif','Post-monsoon VV gamma0 (dB)',-30,0,'gray')]):
        ds=gdal.Open(str(folder/'data'/relative))
        a=ds.ReadAsArray().astype(float)
        a[a==ds.GetRasterBand(1).GetNoDataValue()]=np.nan
        gt=ds.GetGeoTransform()
        extent=[gt[0]/1000,(gt[0]+ds.RasterXSize*30)/1000,
                (gt[3]-ds.RasterYSize*30)/1000,gt[3]/1000]
        im=ax.imshow(a,extent=extent,vmin=low,vmax=high,cmap=cmap)
        ax.set_title(title)
        ax.set_xlabel('UTM easting (km)')
        ax.set_ylabel('UTM northing (km)')
        figure.colorbar(im,ax=ax,shrink=.72)
    figure.suptitle('Venkatapur 2025: seasonal surface evidence\nEPSG:32644 | 30 m | 5 km planning area')
    figure.savefig(folder/'Seasonal_Comparison.png',dpi=180)
    plt.close(figure)
    styles=getSampleStyleSheet()
    story=[]
    def para(text,style='BodyText'):
        story.append(Paragraph(text,styles[style]))
        story.append(Spacer(1,10))
    para('Venkatapur: 2025 satellite screening pilot','Title')
    para('A portable research review package','Heading2')
    para('Study centre: 18.830669 N, 78.750266 E. Korutla, Jagtial, Telangana. The 5 km circle is a planning area, not a verified administrative boundary.')
    para('What has been completed','Heading2')
    para('Sentinel-2: six sampled dates in each season; scaled reflectance, SCL quality masking, a 60 m cloud/shadow buffer and seasonal NDVI/NDMI/MNDWI medians. At least three valid observations are required per pixel. About 97.4% of the original 20 m circle meets this threshold for NDMI. Aligned 30 m layers require essentially full fine-grid support.')
    para('Sentinel-1: eight matched Sentinel-1A descending orbit-165 dates per season. Provider-processed terrain-corrected gamma0 intensity was averaged to 30 m, temporally summarized in linear power and converted to dB. All circle pixels have eight positive observations per season.')
    para('Terrain: Copernicus GLO-30 Public DSM with slope, D8 routing, TWI and provisional drainage. The processing extent was expanded from 30 km to 50 km wide. Remaining upstream-underestimate flags affect 306 of 87,315 circle pixels; hydrology excludes these. Density also excludes 1 km neighbourhoods touching uncertain flow.')
    para('How to open and test','Heading2')
    para('Extract the whole ZIP, open OPEN_IN_QGIS.qgz, and switch layers individually. No internet is needed to review the packaged maps. Compare dates with the same legend. Check coverage counts and read the source manifests. Keep the complete extracted folder together.')
    story.append(PageBreak())
    para('Seasonal comparison','Heading1')
    story.append(Image(str(folder/'Seasonal_Comparison.png'),width=480,height=427))
    para('The optical seasons are sampled March-May and October-December 2025. NDMI describes vegetation/surface moisture response; radar describes backscatter. Water remains included. Colours and brightness do not indicate groundwater availability.')
    story.append(PageBreak())
    para('Interpretation and remaining work','Heading1')
    para('NDVI and NDMI are strongly related: Pearson correlations are approximately 0.89 before the monsoon and 0.84 afterward, with seasonal changes correlated at 0.92 after the SCL-frequency exclusion. Shared spectral bands and vegetation effects contribute. These pixel correlations are descriptive and spatially autocorrelated, not validation.')
    para('Radar VV seasonal change correlates approximately 0.31 with NDMI change and 0.35 with NDVI change. This adds surface evidence but does not isolate soil moisture, irrigation or recharge. Roughness, vegetation and acquisition geometry also affect backscatter.')
    para('Rainfall remains pending: tested NASA archive content requests required authentication. No rainfall layer or rainfall-based score is included. Multi-year coverage, local hydrogeological assessment and combined scenario sensitivity are also pending. Final combined weights remain unset.')
    para('Limits on use','Heading2')
    para('Satellites cannot directly detect groundwater, guarantee water, predict borewell yield or drilling depth. This pilot does not contain a validated groundwater-potential map. Field hydrogeology and appropriate geophysical checks are needed before drilling decisions.')
    para('Sources and processing','Heading2')
    para('Contains modified Copernicus Sentinel data (2025). Optical source: Element 84 Earth Search Sentinel-2 Collection 1 L2A. Radar source: Microsoft Planetary Computer Sentinel-1 RTC, processed by Catalyst using PlanetDEM. Terrain: Copernicus GLO-30 Public AWS 2021 release, a surface model including vegetation and structures. Individual product IDs, source URLs, thresholds and limitations are in metadata/.')
    para('This PDF summarizes the accompanying reproducible code and maps; it is not an independent field assessment. Generated outputs are kept outside Git in the project repository.')
    SimpleDocTemplate(str(folder/'Pilot_Overview.pdf'),pagesize=A4,rightMargin=42,leftMargin=42,topMargin=40,bottomMargin=40).build(story)


if __name__=='__main__':
    main()
