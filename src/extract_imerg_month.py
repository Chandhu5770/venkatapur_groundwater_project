"""Resumable monthly IMERG uncalibrated native-cell extraction.

Run with the separate Earthdata .venv. One private login per run; no persistence.
--summary-only performs no network access and never prompts for credentials.
"""
import argparse
import calendar
import csv
from datetime import date,datetime,timedelta,timezone
import hashlib
import json
from pathlib import Path
import time

import earthaccess
from requests.exceptions import ConnectionError, Timeout
from extract_imerg_day import ROOT,VARIABLE,extract_day

BASE=ROOT/'data/interim/public_inputs/rainfall/imerg_uncal'
OUT=ROOT/'data/processed/rainfall_context'
CELLS={(78.75,18.75),(78.75,18.85)}


def extract_with_retries(day, session, sleep=time.sleep):
    """Retry transient connections; extract_day reuses saved interval checkpoints."""
    for attempt in range(5):
        try:
            return extract_day(day, session=session)
        except (ConnectionError, Timeout):
            if attempt == 4:
                raise
            delay = 5 * 2**attempt
            # Never print exception text: requests errors can contain private URLs.
            print(f'Connection interrupted; retry {attempt+1}/4 in {delay}s. Saved intervals will be reused.', flush=True)
            sleep(delay)


def validate_day(day):
    folder=BASE/day.isoformat()
    metadata=folder/'extraction_manifest.json'
    csvpath=folder/'half_hour_native_cells.csv'
    if not metadata.exists() or not csvpath.exists(): return None
    m=json.loads(metadata.read_text())
    if not m.get('complete') or m.get('variable')!=VARIABLE or m.get('date')!=day.isoformat():
        raise RuntimeError('Invalid cached day metadata: '+day.isoformat())
    with csvpath.open(newline='',encoding='utf-8') as f: rows=list(csv.DictReader(f))
    start=datetime.combine(day,datetime.min.time(),tzinfo=timezone.utc)
    expected={(start+timedelta(minutes=30*i)).isoformat() for i in range(48)}
    if len(rows)!=96 or len(m['sources'])!=48 or {s['utc_start'] for s in m['sources']}!=expected:
        raise RuntimeError('Cached day has missing or duplicate records: '+day.isoformat())
    if {(round(float(r['longitude']),6),round(float(r['latitude']),6)) for r in rows}!=CELLS:
        raise RuntimeError('Unexpected native grid cells')
    result={}
    for cell in sorted(CELLS):
        selected=[r for r in rows if (round(float(r['longitude']),6),round(float(r['latitude']),6))==cell]
        if len(selected)!=48 or {r['utc_start'] for r in selected}!=expected:
            raise RuntimeError('Missing/duplicate cell timestamps')
        valid=[]
        for r in selected:
            if (r['rate_mm_hr']=='')!=(r['interval_mm']==''):
                raise RuntimeError('Inconsistent missing-data pair')
            if r['rate_mm_hr']!='':
                rate,amount=float(r['rate_mm_hr']),float(r['interval_mm'])
                if not (rate>=0 and amount>=0 and abs(amount-.5*rate)<1e-8):
                    raise RuntimeError('Invalid rate integration')
                valid.append(amount)
        result[cell]={'valid_intervals':len(valid),'observed_mm':sum(valid)}
    return {'cells':result,'csv_sha256':hashlib.sha256(csvpath.read_bytes()).hexdigest()}


def summarize(year,month):
    days=calendar.monthrange(year,month)[1]
    expected=days*48
    totals={cell:{'valid_intervals':0,'observed_mm':0.,'complete_days':0} for cell in CELLS}
    completed=[]
    missing=[]
    for number in range(1,days+1):
        day=date(year,month,number)
        info=validate_day(day)
        if info is None:
            missing.append(day.isoformat())
            continue
        completed.append({'date':day.isoformat(),'csv_sha256':info['csv_sha256']})
        for cell,values in info['cells'].items():
            totals[cell]['valid_intervals']+=values['valid_intervals']
            totals[cell]['observed_mm']+=values['observed_mm']
            totals[cell]['complete_days']+=int(values['valid_intervals']==48)
    rows=[]
    for (lon,lat),values in sorted(totals.items()):
        complete=values['valid_intervals']==expected
        rows.append({'month':f'{year}-{month:02d}','longitude':lon,'latitude':lat,
            'expected_intervals':expected,**values,'coverage_fraction':values['valid_intervals']/expected,
            'monthly_total_mm':values['observed_mm'] if complete else '', 'complete':complete})
    OUT.mkdir(parents=True,exist_ok=True)
    stem=f'imerg_uncal_{year}_{month:02d}'
    temp=OUT/(stem+'.csv.tmp')
    with temp.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    temp.replace(OUT/(stem+'.csv'))
    report={'month':f'{year}-{month:02d}','variable':VARIABLE,'native_resolution_degrees':.1,
        'daily_checkpoints':completed,'missing_days':missing,'cells':rows,
        'interpretation':'Native-cell regional rainfall context. No area-weighted village average, recharge estimate or local spatial score.',
        'missing_data':'Incomplete monthly totals are blank; observed_mm is only the sum of available valid intervals. No extrapolation or zero filling.',
        'credentials_saved':False}
    (OUT/(stem+'.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--year',type=int,default=2025,choices=range(2021,2026))
    parser.add_argument('--month',type=int,default=5,choices=range(1,13))
    parser.add_argument('--summary-only',action='store_true')
    parser.add_argument('--max-new-days',type=int,default=3,help='Safety limit per run; use a larger value explicitly for a full month')
    args=parser.parse_args()
    if args.max_new_days<1: parser.error('--max-new-days must be positive')
    report=summarize(args.year,args.month)
    pending=[date.fromisoformat(s) for s in report['missing_days']]
    if args.summary_only or not pending:
        print('Saved monthly coverage summary. Complete days:',len(report['daily_checkpoints']))
        print('Monthly rainfall totals are blank unless all intervals are valid.')
        return
    planned=pending[:args.max_new_days]
    print(f"{len(report['daily_checkpoints'])} cached days reused; {len(pending)} days pending.")
    print(f'Processing at most {len(planned)} new days this run. No complete global files will be saved.')
    print(f'Based on the trial, roughly {len(planned)*21.7:.0f} MB may transfer; actual size can vary.')
    print('One private Earthdata login; credentials stay in memory.')
    auth=earthaccess.login(strategy='interactive',persist=False)
    if not auth.authenticated: raise RuntimeError('Authentication failed')
    session=earthaccess.get_requests_https_session()
    for day in planned:
        print('Processing',day.isoformat(),flush=True)
        try:
            extract_with_retries(day,session)
            validate_day(day)
        except Exception as error:
            summarize(args.year,args.month)
            raise RuntimeError('Stopped on '+day.isoformat()+' ('+type(error).__name__+'); rerun to resume safely') from None
        report=summarize(args.year,args.month)
        print('Checkpoint saved. Complete extracted days:',len(report['daily_checkpoints']),flush=True)
    print('SUCCESS: rainfall batch complete. Days still pending:',len(report['missing_days']))
    print('Rerun the same command to resume. No credentials saved.')


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        raise SystemExit(str(error) if isinstance(error,RuntimeError) else 'Monthly extraction stopped: '+type(error).__name__) from None
