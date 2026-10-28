import json
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from osgeo import gdal
from PIL import Image

from service.app import provider_template

gdal.UseExceptions()

TESTS = Path(__file__).parent
ACTUAL = TESTS / 'actual'

# Max RMS difference (0-255) from the expected images
RENDER_TOLERANCE = 4
GEOREFERENCE_TOLERANCE = 8

# bboxes and zooms from real atlases, so that their shapes match what fp-web
# generates
PAGES = {
    'letter-portrait': dict(
        paper_size='letter',
        orientation='portrait',
        layout='full-page',
        zoom=18,
        bbox=[-83.68451356887817, 9.979343323877206, -83.67997527122498, 9.985112588268525],
        title='Letter portrait',
    ),
    'letter-portrait-half': dict(
        paper_size='letter',
        orientation='portrait',
        layout='half-page',
        zoom=18,
        bbox=[-83.68451356887817, 9.982227956072866, -83.67997527122498, 9.985112588268525],
        title='Letter portrait half-page',
        text='Notes for the field team (bring pencils).\nCheck the footpath along the river.',
    ),
    'a4-landscape': dict(
        paper_size='a4',
        orientation='landscape',
        layout='full-page',
        zoom=17,
        bbox=[-83.66563081741333, 9.360616726827006, -83.65232706069946, 9.369889915391266],
        title='Café São Paulo (A4 landscape)',
    ),
    'a3-portrait': dict(
        paper_size='a3',
        orientation='portrait',
        layout='full-page',
        zoom=17,
        bbox=[12.464075088500977, 42.4953570487247, 12.478022575378418, 42.50988112107605],
        title='A3 portrait',
    ),
}

INDEX = dict(
    paper_size='letter',
    orientation='landscape',
    layout='full-page',
    zoom=16,
    bbox=[-83.6682915687561, 9.35505281368845, -83.63636255264282, 9.375453828529821],
    atlas_bbox=[-83.66563081741333, 9.360616726827006, -83.6390233039856, 9.369889915391266],
    cols=2,
    rows=1,
    title='Letter landscape index',
)

SNAPSHOTS = json.loads((TESTS / 'snapshots.json').read_text())


@pytest.fixture(scope='module')
def provider(server):
    return server + 'tiles/{z}/{x}/{y}.png'


@pytest.fixture(scope='module')
def render(client, provider):
    """
    Function that renders a page (once per module); returns the PDF's URL.
    """
    urls = {}

    def render(name):
        if name not in urls:
            if name == 'index':
                rsp = client.post('/render_index', json=dict(INDEX, slug='index', page_number='i', provider=provider))
            else:
                rsp = client.post('/render_page', json=page_payload(name, provider))
            assert rsp.status_code == 200, rsp.text
            urls[name] = rsp.json()['pdf_url']
        return urls[name]

    return render


def page_payload(name, provider):
    return dict(PAGES[name], slug=slug(name), page_number='A1', provider=provider)


def slug(name):
    return re.sub(r'[^A-Za-z0-9]', '', name)


def local(url):
    """
    Path in tests/ of a URL on the test server.
    """
    return TESTS / urlparse(url).path.lstrip('/')


def rasterize(pdf, dpi):
    """
    Rasterize each page of a PDF with Ghostscript.
    """
    with tempfile.TemporaryDirectory() as tmp:
        # supersampled, since Ghostscript point-samples downscaled images
        args = [f'-r{dpi * 2}', '-dDownScaleFactor=2', f'-sOutputFile={tmp}/%d.png', str(pdf)]
        subprocess.run(['gs', '-q', '-sDEVICE=png16m', *args], check=True)
        pages = sorted(Path(tmp).glob('*.png'), key=lambda p: int(p.stem))
        return [Image.open(p).convert('RGB') for p in pages]


def warp(tif, bbox, width=800):
    """
    The part of a GeoTIFF within a bbox, in web mercator, with masked pixels
    drawn grey (as in tests/expected/).
    """
    ds = gdal.Warp(
        '',
        str(tif),
        format='MEM',
        dstSRS='EPSG:3857',
        outputBounds=bbox,
        outputBoundsSRS='EPSG:4326',
        width=width,
        height=0,
        dstAlpha=True,
    )
    img = Image.fromarray(ds.ReadAsArray().transpose(1, 2, 0), 'RGBA')
    return Image.alpha_composite(Image.new('RGBA', img.size, (153, 153, 153, 255)), img)


def assert_cog(tif):
    """
    Check that a georeferenced GeoTIFF is a JPEG-compressed COG with overviews
    and a mask.
    """
    info = gdal.Info(str(tif), format='json')
    structure = info['metadata']['IMAGE_STRUCTURE']
    assert structure['LAYOUT'] == 'COG'
    assert 'JPEG' in structure['COMPRESSION']
    assert len(info['bands']) == 3
    for band in info['bands']:
        assert band['overviews']
        assert band['mask']['flags'] == ['PER_DATASET']


def href(slug, page_number, bbox):
    return f'https://fieldpapers.org/atlases/{slug}/{page_number}?bbox=' + ','.join(f'{v:f}' for v in bbox)


@pytest.mark.parametrize('name', PAGES)
def test_render_page(name, render, compare):
    url = render(name)
    assert url.endswith(f'actual/atlases/{slug(name)}/{slug(name)}-A1.pdf')

    [page] = rasterize(local(url), 72)
    compare(name, page, RENDER_TOLERANCE)


def test_render_index(render, compare):
    url = render('index')
    assert url.endswith('actual/atlases/index/index-index.pdf')

    [page] = rasterize(local(url), 72)
    compare('index', page, RENDER_TOLERANCE)


def test_merge_pages(client, render):
    rsp = client.post('/merge_pages', json=dict(slug='index', pdf_urls=[render('index'), render('letter-portrait')]))
    assert rsp.status_code == 200, rsp.text
    url = rsp.json()['pdf_url']
    assert url.endswith('actual/atlases/index/atlas-index.pdf')

    pages = rasterize(local(url), 10)
    assert [p.width > p.height for p in pages] == [True, False]


@pytest.mark.parametrize('name', PAGES)
def test_round_trip(name, client, server, render, compare):
    """
    Georeference a clean rasterization of a rendered page.
    """
    page = PAGES[name]
    [scan] = rasterize(local(render(name)), 200)
    scan.save(ACTUAL / f'{name}-scan.png')
    image_url = f'{server}actual/{name}-scan.png'

    rsp = client.post('/decode_qr', json=dict(image_url=image_url))
    assert rsp.status_code == 200, rsp.text
    assert rsp.json() == {'href': href(slug(name), 'A1', page['bbox'])}

    rsp = client.post('/georeference', json=dict(page, slug=slug(name), image_url=image_url))
    assert rsp.status_code == 200, rsp.text
    tif = local(rsp.json()['geotiff_url'])
    assert_cog(tif)
    compare(f'{name}-georeferenced', warp(tif, page['bbox']), GEOREFERENCE_TOLERANCE)


@pytest.mark.parametrize('snapshot', SNAPSHOTS, ids=[s['file'] for s in SNAPSHOTS])
def test_snapshot(snapshot, client, server, compare):
    """
    Georeference a photo or scan of a printed page.
    """
    name = Path(snapshot['file']).stem
    image_url = f'{server}snapshots/{snapshot["file"]}'

    rsp = client.post('/decode_qr', json=dict(image_url=image_url))
    assert rsp.status_code == 200, rsp.text
    assert rsp.json() == {'href': snapshot['href']}

    bbox = [float(v) for v in parse_qs(urlparse(snapshot['href']).query)['bbox'][0].split(',')]
    payload = dict(
        slug=slug(name),
        image_url=image_url,
        bbox=bbox,
        paper_size=snapshot['paper_size'],
        orientation=snapshot['orientation'],
        layout=snapshot['layout'],
    )
    rsp = client.post('/georeference', json=payload)
    assert rsp.status_code == 200, rsp.text
    tif = local(rsp.json()['geotiff_url'])
    assert_cog(tif)
    compare(f'snapshot-{name}', warp(tif, bbox), GEOREFERENCE_TOLERANCE)


def test_invalid_payload(client, provider):
    rsp = client.post('/render_page', json=dict(page_payload('letter-portrait', provider), slug='../x'))
    assert rsp.status_code == 422


def test_unreachable_tiles(client):
    rsp = client.post('/render_page', json=page_payload('letter-portrait', 'http://127.0.0.1:9/{z}/{x}/{y}.png'))
    assert rsp.status_code == 500


def test_no_qr_code(client, provider):
    rsp = client.post('/decode_qr', json=dict(image_url=provider.format(z=1, x=0, y=0)))
    assert rsp.status_code == 422


def test_no_registration_marks(client, provider):
    image_url = provider.format(z=1, x=0, y=0)
    rsp = client.post('/georeference', json=dict(PAGES['letter-portrait'], slug='blank', image_url=image_url))
    assert rsp.status_code == 422
    assert 'could not process source image' in rsp.json()['detail']


def test_provider_template():
    assert (
        provider_template('https://{s}.tile.example.com/{z}/{x}/{y}@2x.png,')
        == 'https://a.tile.example.com/{Z}/{X}/{Y}.png'
    )
    assert (
        provider_template('https://{S}.example.com/{z}/{x}/{y}.png,https://tile.stamen.com/utm/{Z}/{X}/{Y}.png')
        == 'https://a.example.com/{Z}/{X}/{Y}.png,https://tile.stamen.com/utm/{Z}/{X}/{Y}.png'
    )
