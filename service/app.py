"""
HTTP service for fp-web: renders atlas pages to PDF and georeferences
snapshots, running the decoder/ scripts in subprocesses. Each request does its
work synchronously and returns the URL of the uploaded result.

fp-web owns retries. A 422 means the input can't be processed and retrying
won't help; any other error may succeed on retry.
"""

import logging
import os
import re
import signal
import subprocess
import sys
import tempfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path
from typing import Annotated, List, Literal, Tuple
from urllib.parse import unquote, urlparse

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

DECODER = Path(__file__).resolve().parent.parent / 'decoder'

log = logging.getLogger('fp-tasks')
app = FastAPI()

# Atlas and snapshot slugs and page numbers, which become part of S3 keys
Name = Annotated[str, Field(pattern=r'^[A-Za-z0-9]+$')]

# west, south, east, north
BBox = Tuple[float, float, float, float]


class Page(BaseModel):
    slug: Name
    page_number: Name
    bbox: BBox
    zoom: int
    provider: str
    paper_size: Literal['letter', 'a4', 'a3']
    orientation: Literal['portrait', 'landscape']
    layout: Literal['full-page', 'half-page']
    text: str = ''
    title: str = ''


class Index(Page):
    atlas_bbox: BBox
    cols: int
    rows: int


class Merge(BaseModel):
    slug: Name
    pdf_urls: List[str]


class Upload(BaseModel):
    image_url: str


class Georeference(BaseModel):
    slug: Name
    image_url: str
    bbox: BBox
    paper_size: Literal['letter', 'a4', 'a3']
    orientation: Literal['portrait', 'landscape']
    layout: Literal['full-page', 'half-page']


@app.get('/health')
def health():
    return {}


@app.post('/render_page')
def render_page(page: Page):
    pdf = run([sys.executable, 'create_page.py', *page_args(page), '-n', page.page_number, page.slug], timeout=60)
    return {'pdf_url': persist(f'atlases/{page.slug}/{page.slug}-{page.page_number}.pdf', pdf, 'application/pdf')}


@app.post('/render_index')
def render_index(page: Index):
    w, s, e, n = page.atlas_bbox
    args = [*page_args(page), '-e', n, w, s, e, '-c', page.cols, '-r', page.rows, page.slug]
    pdf = run([sys.executable, 'create_index.py', *args], timeout=60)
    return {'pdf_url': persist(f'atlases/{page.slug}/{page.slug}-index.pdf', pdf, 'application/pdf')}


@app.post('/merge_pages')
def merge_pages(merge: Merge):
    with tempfile.TemporaryDirectory() as tmp, ThreadPoolExecutor(8) as pool:
        files = []
        for i, data in enumerate(pool.map(download, merge.pdf_urls)):
            files.append(Path(tmp) / f'page-{i}.pdf')
            files[-1].write_bytes(data)

        pdf = run(['gs', '-q', '-sDEVICE=pdfwrite', '-o', '-', *files], timeout=120)

    return {'pdf_url': persist(f'atlases/{merge.slug}/atlas-{merge.slug}.pdf', pdf, 'application/pdf')}


@app.post('/decode_qr')
def decode_qr(upload: Upload):
    return {'href': read_qr(download(upload.image_url))}


@app.post('/georeference')
def georeference(snapshot: Georeference):
    tif = process_snapshot(download(snapshot.image_url), snapshot.bbox,
                           snapshot.paper_size, snapshot.orientation, snapshot.layout)
    return {'geotiff_url': persist(f'snapshots/{snapshot.slug}/field-paper-{snapshot.slug}.tiff', tif, 'image/tiff')}


@app.exception_handler(subprocess.CalledProcessError)
def process_failed(request, e):
    # decoder scripts exit with EX_DATAERR when the input can't be processed
    status = 422 if e.returncode == os.EX_DATAERR else 500
    message = f'{" ".join(e.cmd[:2])} exited with {e.returncode}: {e.stderr.decode(errors="replace")[-2000:]}'
    log.warning(message)
    return JSONResponse({'detail': message}, status)


@app.exception_handler(subprocess.TimeoutExpired)
def process_timed_out(request, e):
    message = f'{" ".join(e.cmd[:2])} timed out after {e.timeout}s'
    log.warning(message)
    return JSONResponse({'detail': message}, 500)


def page_args(page):
    w, s, e, n = page.bbox
    return ['-s', page.paper_size, '-l', page.layout, '-o', page.orientation,
            '-b', n, w, s, e, '-z', page.zoom, '-p', provider_template(page.provider),
            '-t', page.text, '-T', page.title]


def provider_template(provider):
    """
    Convert fp-web's provider (a Leaflet-style tile URL template, optionally
    followed by a comma and an overlay template) to the ModestMaps form.
    """
    provider = re.sub(r'\{s\}', 'a', provider, count=1, flags=re.IGNORECASE)
    provider = re.sub(r'\{\w\}', lambda m: m.group(0).upper(), provider)
    return re.sub(r',$', '', provider.replace('@2x', '', 1))


def read_qr(image):
    """
    Return the URL in an image's QR code.
    """
    return run([sys.executable, 'read_qr.py'], image, timeout=60).decode().strip()


def process_snapshot(image, bbox, paper_size, orientation, layout):
    """
    Georeference an image of an atlas page with the given bbox; returns a
    GeoTIFF.
    """
    w, s, e, n = bbox
    args = ['-b', n, w, s, e, '-s', paper_size, '-o', orientation, '-l', layout]
    return run([sys.executable, 'process_snapshot.py', *args], image, timeout=120)


def run(args, input=None, timeout=60):
    """
    Run a command in decoder/, in its own process group so that a timeout
    kills any children it spawned too. Returns its stdout.
    """
    args = [str(a) for a in args]
    proc = subprocess.Popen(args, cwd=DECODER, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, start_new_session=True)
    try:
        out, err = proc.communicate(input, timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        raise

    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, args, out, err)

    return out


def download(url):
    """
    Fetch a URL. S3 URLs are fetched with credentials, since uploaded snapshot
    images are not public.
    """
    uri = urlparse(url)

    if re.search(r's3.*\.amazonaws\.com', uri.hostname):
        if re.match(r'.+\.s3.*\.amazonaws\.com', uri.hostname):
            bucket, key = uri.hostname.split('.')[0], unquote(uri.path)[1:]
        else:
            bucket, key = unquote(uri.path)[1:].split('/', 1)
        return s3().get_object(Bucket=bucket, Key=key)['Body'].read()

    with urllib.request.urlopen(url, timeout=60) as rsp:
        return rsp.read()


def persist(key, body, content_type):
    """
    Store a file in S3 (or locally, when PERSIST=local); returns its URL.
    """
    if os.environ.get('PERSIST') == 'local':
        path = Path(os.environ['STATIC_PATH']) / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        return os.environ['STATIC_URI_PREFIX'].rstrip('/') + '/' + key

    bucket = os.environ['S3_BUCKET_NAME']
    s3().put_object(Bucket=bucket, Key=key, Body=body, ACL='public-read',
                    CacheControl='public,max-age=31536000', ContentType=content_type)

    # path-style, as bucket names may contain dots
    region = s3().meta.region_name
    host = 's3.amazonaws.com' if region == 'us-east-1' else f's3.{region}.amazonaws.com'
    return f'https://{host}/{bucket}/{key}'


@lru_cache(maxsize=None)
def s3():
    import boto3
    return boto3.client('s3')
