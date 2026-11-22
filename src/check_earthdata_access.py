"""Private terminal login and a tiny IMERG file-access check.

Use .venv/Scripts/python.exe. Credentials are kept in memory (persist=False).
--catalogue-only checks public metadata without prompting for credentials.
"""
import argparse
import json
import logging
from pathlib import Path
from urllib.parse import urlparse

import earthaccess

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalogue-only',action='store_true')
    args=parser.parse_args()
    logging.getLogger('earthaccess').setLevel(logging.ERROR)
    print('Searching one IMERG V07 half-hourly granule for 12 May 2025...')
    results=earthaccess.search_data(short_name='GPM_3IMERGHH',version='07',
        temporal=('2025-05-12T00:00:00Z','2025-05-12T00:29:59Z'),
        bounding_box=(78.702826,18.785498,78.797705,18.875841),count=1)
    if not results:
        raise SystemExit('No matching granule found. No credentials were requested.')
    print('Public catalogue search passed.')
    if args.catalogue_only:
        return
    print('Enter credentials only in this terminal. Password input is hidden.')
    print('Credentials will not be saved to a file. Browser login is separate.')
    try:
        auth=earthaccess.login(strategy='interactive',persist=False)
    except Exception as error:
        raise SystemExit('Login failed ('+type(error).__name__+'). Do not paste credentials into chat.') from None
    if not auth.authenticated:
        raise SystemExit('Login was not authenticated. Nothing downloaded.')
    links=results[0].data_links(access='external')
    links=[link for link in links if link.lower().startswith('https://') and '.hdf5' in link.lower()]
    if not links:
        raise SystemExit('Authenticated, but no expected HTTPS HDF5 link was found.')
    session=earthaccess.get_requests_https_session()
    try:
        with session.get(links[0],headers={'Range':'bytes=0-7'},stream=True,timeout=60) as response:
            status=response.status_code
            if status not in [200,206]:
                output=ROOT/'data/interim/rainfall_access_check'
                output.mkdir(parents=True,exist_ok=True)
                diagnostic={'authenticated':True,'http_status':status,
                    'final_host':urlparse(response.url).hostname,
                    'credentials_persisted':False,'scope':'Access denied; no rainfall downloaded.'}
                (output/'authenticated_test.json').write_text(json.dumps(diagnostic,indent=2),encoding='utf-8')
                if status==403:
                    print('The download link uses the current Earthdata Cloud archive.')
                    print('Check Earthdata profile > Applications / Authorized Apps for NASA GESDISC DATA ARCHIVE.')
                    print('Open the public data link in your browser to see any required authorization/terms:')
                    print(links[0].split('?')[0])
                raise SystemExit(f'Login succeeded; data server returned HTTP {status}. No rainfall file downloaded.')
            header=response.raw.read(8)
    except SystemExit:
        raise
    except Exception as error:
        raise SystemExit('Data-access test failed ('+type(error).__name__+'). Credentials were not saved.') from None
    passed=header==b'\x89HDF\r\n\x1a\n'
    output=ROOT/'data/interim/rainfall_access_check'
    output.mkdir(parents=True,exist_ok=True)
    report={'authenticated':True,'http_status':status,'hdf5_signature_valid':passed,
            'bytes_read':len(header),'credentials_persisted':False,
            'dataset':'GPM_3IMERGHH version 07','scope':'Access check only; no rainfall values or full files downloaded.'}
    (output/'authenticated_test.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    if not passed:
        raise SystemExit('Response was not the expected HDF5 header; access is not confirmed.')
    print('SUCCESS: authenticated rainfall access verified; only 8 bytes read.')
    print('No credentials or tokens saved. You can share this SUCCESS message.')
    print('Full rainfall extraction will require another login because this session is not persisted.')


if __name__=='__main__':
    main()
