"""Download species-labelled, licensed Wikimedia Commons photographs, optionally.

Usage (with ordinary internet access):
    python scripts/cache_commons_photos.py

Requires httpx from requirements.txt. No credentials, AI generation, or cloud upload.
Review the linked file-description pages for authors and license obligations.
"""
from __future__ import annotations
import sys
from pathlib import Path
from urllib.parse import quote, urlparse
import httpx

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from server.app import PHOTO_LIBRARY

TARGET=ROOT/'web'/'assets'/'photographs'
TARGET.mkdir(parents=True,exist_ok=True)
HEADERS={'User-Agent':'VerdantAtlasEducation/2.1 (Wikimedia photo source attribution; non-bulk download)'}

with httpx.Client(timeout=30,follow_redirects=True,headers=HEADERS) as client:
    for name,(filename,author,license_name,science) in PHOTO_LIBRARY.items():
        dest=TARGET/f'{name}.jpg'
        if dest.is_file() and dest.stat().st_size>1024:
            print('cached',name);continue
        url=f'https://commons.wikimedia.org/wiki/Special:FilePath/{quote(filename,safe="")}?width=960'
        try:
            with client.stream('GET',url) as response:
                response.raise_for_status()
                domain=urlparse(str(response.url)).hostname or ''
                if domain not in {'upload.wikimedia.org','commons.wikimedia.org'}:
                    raise RuntimeError(f'Unexpected image host: {domain}')
                content_type=response.headers.get('content-type','')
                if 'image/jpeg' not in content_type:
                    raise RuntimeError(f'Expected JPEG; got {content_type}')
                total=0
                with dest.open('wb') as file:
                    for part in response.iter_bytes():
                        total+=len(part)
                        if total>10_000_000:raise RuntimeError('Image exceeds size safety limit')
                        file.write(part)
            with dest.open('rb') as file:
                if file.read(3)!=b'\xff\xd8\xff':raise RuntimeError('Not a real JPEG')
            print('downloaded',name,total,'bytes',license_name,'by',author)
        except (httpx.HTTPError,RuntimeError,IOError) as error:
            dest.unlink(missing_ok=True)
            print('FAILED',name,str(error))
print('Done. Image metadata and per-image attribution remain in server/app.py.')
