"""Rebuild cached review outputs with QGIS Python; no downloads or authentication.

Prerequisites: completed seasonal/terrain/rainfall outputs and May context CSVs.
Does not rebuild satellite composites, terrain hydrology or source extraction.
Close QGIS first: open raster layers can prevent overwrites on Windows.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/processed/integrated_evidence_review'
STEPS=['review_may_optical_rainfall.py','review_may_radar_rainfall.py',
       'map_surface_change_patterns.py','review_terrain_surface_patterns.py',
       'plot_terrain_surface_review.py','review_drainage_thresholds.py',
       'review_temporal_consistency.py','explore_terrain_mcda.py',
       'review_optical_confounding.py','build_integrated_evidence_review.py',
       'build_analysis_review_report.py']


def main():
    if os.name=='nt':
        powershell=Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'
        running=subprocess.run([str(powershell),'-NoProfile','-Command',
            "Get-Process -Name 'qgis-bin','qgis-ltr-bin' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty ProcessName; exit 0"],
            capture_output=True,text=True,check=True)
        if any(name in running.stdout.lower() for name in ['qgis-bin','qgis-ltr-bin']):
            raise RuntimeError('Close QGIS before rebuilding: it may hold output rasters open. No review steps started.')
    required=['data/processed/rainfall_context/may_acquisition_rainfall_context.csv',
              'data/processed/rainfall_context/imerg_uncal_2025_05.csv',
              'data/processed/multiyear_2023_2025/sensitivity/mask_scl_water_at_least_2_years.tif']
    for name in required:
        if not (ROOT/name).exists():raise RuntimeError('Missing prerequisite: '+name)
    OUT.mkdir(parents=True,exist_ok=True)
    report={'started_utc':datetime.now(timezone.utc).isoformat(),'scope':'Cached review rebuild only',
            'network_required':False,'steps':[],'complete':False}
    path=OUT/'offline_review_run.json'
    def save():path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    save()
    for number,name in enumerate(STEPS,1):
        source=ROOT/'src'/name
        print(f'[{number}/{len(STEPS)}] {name}',flush=True)
        result=subprocess.run([sys.executable,str(source)],cwd=ROOT,capture_output=True,text=True)
        report['steps'].append({'script':name,'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                                'exit_code':result.returncode})
        (OUT/(name+'.log')).write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
        save()
        if result.returncode:
            # These are offline scripts, but keep parent output short and predictable.
            raise RuntimeError('Review step failed: '+name+'; see its .log in the review folder. Close QGIS before rebuilding raster outputs. No further steps run.')
    products=['venkatapur_evidence_review.qgz','venkatapur_analysis_review.pdf','project_inventory.json']
    report['products']={name:hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in products}
    report['complete']=True;report['finished_utc']=datetime.now(timezone.utc).isoformat();save()
    print('SUCCESS: offline review rebuilt; run manifest and products saved in '+str(OUT))


if __name__=='__main__':main()
