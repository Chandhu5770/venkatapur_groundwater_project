"""Authenticated one-day native-cell IMERG uncalibrated rainfall extraction.

This first extraction verifies the variable and completeness before longer runs.
Only bounded HTTP ranges are read; global files and credentials are not saved.
"""
import argparse
import csv
from datetime import date,datetime,timedelta,timezone
import io
import json
from pathlib import Path
import re

import earthaccess
import h5py
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
VARIABLE='Grid/Intermediate/precipitationUncal'


class RangeReader(io.RawIOBase):
    """Seekable small-block reader with an 8 MB per-file transfer ceiling."""
    def __init__(self,session,url):
        self.session,self.url,self.position=session,url,0
        self.cache={}
        self.transferred=0
        with session.get(url,headers={'Range':'bytes=0-7'},stream=True,timeout=60) as r:
            if r.status_code!=206 or 'Content-Range' not in r.headers:
                raise RuntimeError('Archive did not provide byte-range access; full-file download refused')
            self.size=int(r.headers['Content-Range'].split('/')[-1])
    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.position
    def seek(self,offset,whence=0):
        self.position=offset if whence==0 else self.position+offset if whence==1 else self.size+offset
        if self.position<0: raise ValueError('Negative seek')
        return self.position
    def read(self,size=-1):
        if size<0: raise RuntimeError('Unbounded read refused')
        end=min(self.size,self.position+size)
        chunks=[]
        while self.position<end:
            block=self.position//65536
            if block not in self.cache:
                start=block*65536
                stop=min(self.size-1,start+65535)
                if self.transferred+(stop-start+1)>8*1024*1024:
                    raise RuntimeError('Per-file transfer ceiling reached; stop and review chunk layout')
                with self.session.get(self.url,headers={'Range':f'bytes={start}-{stop}'},stream=True,timeout=60) as r:
                    if r.status_code!=206: raise RuntimeError('Range request denied')
                    data=r.raw.read(stop-start+1)
                    if len(data)!=stop-start+1: raise RuntimeError('Incomplete range response')
                self.cache[block]=data
                self.transferred+=len(data)
            data=self.cache[block]
            offset=self.position%65536
            n=min(end-self.position,len(data)-offset)
            if n<=0: raise RuntimeError('Empty range block')
            chunks.append(data[offset:offset+n])
            self.position+=n
        return b''.join(chunks)
    def readinto(self,buffer):
        data=self.read(len(buffer)); buffer[:len(data)]=data; return len(data)


def extract_day(day, session=None):
    """Extract/resume one UTC day, reusing only validated interval checkpoints."""
    start=datetime.combine(day,datetime.min.time(),tzinfo=timezone.utc)
    end=start+timedelta(days=1)
    granules=earthaccess.search_data(short_name='GPM_3IMERGHH',version='07',
        temporal=(start.isoformat(),(end-timedelta(seconds=1)).isoformat()),count=100)
    if len(granules)!=48:
        raise SystemExit(f'Expected 48 half-hour granules, found {len(granules)}. Extraction stopped.')
    if session is None:
        print('Enter credentials only at these prompts; they will not be saved.')
        auth=earthaccess.login(strategy='interactive',persist=False)
        if not auth.authenticated: raise RuntimeError('Authentication failed')
        session=earthaccess.get_requests_https_session()
    folder=ROOT/'data/interim/public_inputs/rainfall/imerg_uncal'/day.isoformat()
    folder.mkdir(parents=True,exist_ok=True)
    records=[]
    manifest={'date':day.isoformat(),'dataset':'GPM_3IMERGHH V07','variable':VARIABLE,
        'interpretation':'Native grid-cell rainfall context; no village average or recharge inference. Not monthly gauge-adjusted; ancillary calibration/models remain.',
        'sources':[],'expected_intervals':48}
    checkpoint=folder/'interval_checkpoint.json'
    csvpath=folder/'half_hour_native_cells.csv'
    if checkpoint.exists() and csvpath.exists():
        previous=json.loads(checkpoint.read_text())
        if previous.get('date')!=day.isoformat() or previous.get('variable')!=VARIABLE:
            raise RuntimeError('Checkpoint does not match requested data')
        with csvpath.open(newline='',encoding='utf-8') as f:
            cached=list(csv.DictReader(f))
        expected_cells={(78.75,18.75),(78.75,18.85)}
        for source in previous.get('sources',[]):
            rows=[r for r in cached if r['utc_start']==source['utc_start']]
            keys={(round(float(r['longitude']),6),round(float(r['latitude']),6)) for r in rows}
            if len(rows)==2 and keys==expected_cells:
                for row in rows:
                    for field in ['longitude','latitude','rate_mm_hr','interval_mm']:
                        row[field]=float(row[field]) if row[field]!='' else ''
                    if row['rate_mm_hr']!='' and (row['rate_mm_hr']<0 or abs(row['interval_mm']-.5*row['rate_mm_hr'])>1e-8):
                        raise RuntimeError('Corrupt cached rainfall value')
                records.extend(rows)
                manifest['sources'].append(source)
    completed={source['utc_start'] for source in manifest['sources']}
    for number,granule in enumerate(granules,1):
        links=[u for u in granule.data_links(access='external') if '.hdf5' in u.lower() and u.startswith('https://')]
        if not links: raise RuntimeError('No HDF5 data link')
        url=links[0]
        match=re.search(r'IMERG\.(\d{8})-S(\d{6})-E',url)
        if not match: raise RuntimeError('Unrecognized granule timestamp')
        timestamp=datetime.strptime(''.join(match.groups()),'%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
        if not start<=timestamp<end: raise RuntimeError('Granule outside requested UTC day')
        if timestamp.isoformat() in completed:
            print(f'{number}/48 intervals: cached',flush=True)
            continue
        remote=RangeReader(session,url)
        with h5py.File(remote,'r') as handle:
            if VARIABLE not in handle: raise RuntimeError('Uncalibrated field absent; calibrated precipitation will not be substituted')
            field=handle[VARIABLE]
            units=field.attrs.get('units','')
            if isinstance(units,bytes): units=units.decode()
            if str(units).lower().replace(' ','') not in ['mm/hr','mm/hour','mmh-1']:
                raise RuntimeError('Unexpected rainfall units; inspect metadata before aggregation')
            if 'scale_factor' in field.attrs and float(field.attrs['scale_factor'])!=1:
                raise RuntimeError('Nontrivial scaling requires review')
            if 'add_offset' in field.attrs and float(field.attrs['add_offset'])!=0:
                raise RuntimeError('Nonzero offset requires review')
            lon=handle['Grid/lon'][:].ravel(); lat=handle['Grid/lat'][:].ravel()
            ix=np.where((lon+.05>78.702826)&(lon-.05<78.797705))[0]
            iy=np.where((lat+.05>18.785498)&(lat-.05<18.875841))[0]
            if not len(ix) or not len(iy): raise RuntimeError('No intersecting native cells')
            slices=[]
            for length in field.shape:
                if length==len(lon): slices.append(slice(int(ix.min()),int(ix.max())+1))
                elif length==len(lat): slices.append(slice(int(iy.min()),int(iy.max())+1))
                elif length==1: slices.append(0)
                else: raise RuntimeError('Unexpected dimension')
            values=field[tuple(slices)]
            spatial=[n for n in field.shape if n!=1]
            if spatial==[len(lat),len(lon)]: values=values.T
            if values.shape!=(len(ix),len(iy)): raise RuntimeError('Ambiguous axis order')
            for x,i in enumerate(ix):
                for y,j in enumerate(iy):
                    rate=float(values[x,y]); valid=np.isfinite(rate) and rate>=0
                    records.append({'utc_start':timestamp.isoformat(),'longitude':float(lon[i]),'latitude':float(lat[j]),
                        'rate_mm_hr':rate if valid else '', 'interval_mm':rate*.5 if valid else ''})
        manifest['sources'].append({'url':url.split('?')[0],'bytes_transferred':remote.transferred,'utc_start':timestamp.isoformat()})
        # Checkpoint values only, never the authenticated session or its headers.
        temp=folder/'half_hour_native_cells.csv.tmp'
        with temp.open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=list(records[0])); writer.writeheader(); writer.writerows(records)
        temp.replace(csvpath)
        temp=folder/'interval_checkpoint.json.tmp'
        temp.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        temp.replace(checkpoint)
        print(f'{number}/48 intervals extracted',flush=True)
    times={r['utc_start'] for r in records}
    expected={(start+timedelta(minutes=30*i)).isoformat() for i in range(48)}
    if times!=expected: raise RuntimeError('Duplicate or missing half-hour times; no complete-day total produced')
    totals=[]
    for lon,lat in sorted({(r['longitude'],r['latitude']) for r in records}):
        rows=[r for r in records if r['longitude']==lon and r['latitude']==lat]
        valid=[r for r in rows if r['interval_mm']!='']
        totals.append({'longitude':lon,'latitude':lat,'valid_intervals':len(valid),
                       'daily_mm':sum(r['interval_mm'] for r in valid) if len(valid)==48 else None})
    manifest['complete']=True
    manifest['native_cell_totals']=totals
    (folder/'extraction_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return folder


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date',type=date.fromisoformat,default=date(2025,5,12))
    args=parser.parse_args()
    folder=extract_day(args.date)
    print('SUCCESS: one-day native-cell rainfall extracted:',folder)
    print('Share this SUCCESS line only. Credentials were kept in memory.')


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        raise SystemExit('Extraction stopped: '+type(error).__name__+'. No credentials saved; partial numeric checkpoints may exist.') from None
