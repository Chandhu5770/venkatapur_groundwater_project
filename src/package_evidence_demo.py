"""Create and relocation-test a portable derived-evidence QGIS demo ZIP."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/processed/integrated_evidence_review'
OUT=ROOT/'data/processed/share'


def main():
    global _qgis_app
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    from qgis.core import QgsApplication,QgsProject,QgsRasterLayer,QgsDataProvider,Qgis
    _qgis_app=QgsApplication([],False);_qgis_app.initQgis()
    OUT.mkdir(parents=True,exist_ok=True)
    archive=OUT/'venkatapur_evidence_demo.zip'
    with tempfile.TemporaryDirectory(prefix='evidence_demo_',dir=OUT) as temporary:
        work=Path(temporary);bundle=work/'Venkatapur_Evidence_Demo';bundle.mkdir()
        layers_dir=bundle/'layers';layers_dir.mkdir()
        project=QgsProject()
        if not project.read(str(BASE/'venkatapur_evidence_review.qgz')):raise RuntimeError('Project read failed')
        project.setFilePathStorage(Qgis.FilePathType.Relative)
        copied={}
        for layer in project.mapLayers().values():
            source=Path(layer.source().split('|')[0]).resolve()
            if not source.is_file() or not source.is_relative_to(ROOT):raise RuntimeError('Unexpected data source')
            if source.suffix.lower() not in ['.tif','.geojson','.csv']:raise RuntimeError('Unexpected layer format')
            if source not in copied:
                name=hashlib.sha256(str(source.relative_to(ROOT)).encode()).hexdigest()[:10]+'_'+source.name
                copied[source]=layers_dir/name;shutil.copy2(source,copied[source])
            renderer=layer.renderer().clone() if layer.renderer() is not None else None
            provider=layer.providerType();name=layer.name()
            layer.setDataSource(str(copied[source]),name,provider,QgsDataProvider.ProviderOptions())
            if renderer is not None:layer.setRenderer(renderer)
            if not layer.isValid():raise RuntimeError('Packaged layer invalid: '+name)
        project.setTitle('Venkatapur portable evidence demo - exploratory, not validated groundwater potential')
        projectpath=bundle/'OPEN_IN_QGIS.qgz'
        if not project.write(str(projectpath)):raise RuntimeError('Portable project write failed')
        count=len(project.mapLayers());project.clear()
        shutil.copy2(BASE/'venkatapur_analysis_review.pdf',bundle/'ANALYSIS_REVIEW.pdf')
        shutil.copy2(ROOT/'docs/06_scenario_review.md',bundle/'METHODS_AND_LIMITATIONS.md')
        attribution='''Data provenance and scope
Derived optical evidence: Copernicus Sentinel-2 L2A, Earth Search public COG archive, sampled seasons 2023-2025.
Derived radar evidence: Copernicus Sentinel-1, Microsoft Planetary Computer RTC/Catalyst gamma0 processing with PlanetDEM, sampled seasons 2023-2025.
Terrain: Copernicus DEM GLO-30, AWS 2021 public release; DSM, not bare-earth survey. Copernicus DEM licence conditions apply to derived products: https://registry.opendata.aws/copernicus-dem/
Rainfall: NASA GPM IMERG V07 precipitationUncal, May 2025, two native cells. NASA GPM: https://gpm.nasa.gov/data/imerg
Reference centre: user-confirmed coordinate; 5 km planning circle, not an official boundary.
This bundle contains derived pilot outputs, not raw satellite scenes. Source-provider terms and attribution remain applicable. No new blanket redistribution licence is asserted.
No credentials, authentication sessions or raw downloads are included. No online basemap is required.
'''
        (bundle/'DATA_ATTRIBUTION.txt').write_text(attribution,encoding='utf-8')
        instructions=f'''VENKATAPUR EXPLORATORY EVIDENCE DEMONSTRATION

1. Extract the entire ZIP to a folder. Do not open the project inside the ZIP.
2. Open OPEN_IN_QGIS.qgz with QGIS (built and checked using QGIS 3.40.11).
3. Keep the layers folder alongside the project. No login or internet is needed to inspect this bundle.
4. Toggle one raster at a time. Reference centre/buffer may stay visible. CSV layers open through their attribute tables.
5. Read ANALYSIS_REVIEW.pdf and METHODS_AND_LIMITATIONS.md before interpreting results.

Suggested five-minute demonstration:
- Optical group: compare pre/post NDMI with the same colour scale, then NDMI/NDVI changes.
- Temporal consistency: show that a median change can hide reversals between years.
- Terrain scenarios: compare named weight/normalization assumptions; none is selected as final.
- Tables: show complete May rainfall and automated vegetation-confounding results.

There are {count} map/table layers. Colours and terrain scores do not predict groundwater depth, borewell yield or guaranteed water.
The 2023-2025 sampled evidence and May-only rainfall do not complete the original five-year/seasonal baseline.
The 5 km circle is a planning buffer. Irrigation/crop effects and independent hydrogeological validation remain unresolved.
This is a local QGIS demonstration, not a web application. No installation support or real-time data service is included.
'''
        (bundle/'START_HERE.txt').write_text(instructions,encoding='utf-8')
        files=sorted(p for p in bundle.rglob('*') if p.is_file())
        checksums={p.relative_to(bundle).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        (bundle/'CHECKSUMS.json').write_text(json.dumps(checksums,indent=2),encoding='utf-8')
        staged=work/'demo.zip'
        with zipfile.ZipFile(staged,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for path in sorted(bundle.rglob('*')):
                if path.is_file():z.write(path,path.relative_to(work))
        relocated=work/'relocation_test';relocated.mkdir()
        with zipfile.ZipFile(staged) as z:
            if z.testzip() is not None:raise RuntimeError('ZIP integrity failed')
            z.extractall(relocated)
        moved=relocated/bundle.name
        check=QgsProject()
        if not check.read(str(moved/'OPEN_IN_QGIS.qgz')):raise RuntimeError('Relocated project failed')
        if len(check.mapLayers())!=count:raise RuntimeError('Relocated layer count differs')
        for layer in check.mapLayers().values():
            source=Path(layer.source().split('|')[0]).resolve()
            if not layer.isValid() or not source.is_relative_to(moved.resolve()):raise RuntimeError('Nonportable layer: '+layer.name())
            if isinstance(layer,QgsRasterLayer) and not layer.crs().isValid():raise RuntimeError('Invalid raster CRS')
        for name,digest in checksums.items():
            if hashlib.sha256((moved/name).read_bytes()).hexdigest()!=digest:raise RuntimeError('Checksum mismatch')
        check.clear();staged.replace(archive)
        report={'archive':archive.name,'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
                'layers':count,'relocation_all_sources_within_bundle':True,'checksums_verified':True,
                'scope':'Exploratory derived-evidence QGIS demo; not a validated groundwater map'}
        (OUT/'evidence_demo_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2))


if __name__=='__main__':main()
