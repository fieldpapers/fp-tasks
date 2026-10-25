"""
HTTP smoke tests.

Results are stored locally (PERSIST=local) in a directory served over HTTP,
so that merge_pages can fetch the rendered pages.
"""

import functools
import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from helpers import TESTS, fetch, geotiff_corners, rasterize
from service.app import app, provider_template
from test_render import CASES

SAMPLE = json.loads((TESTS / 'snapshots.json').read_text())[0]


class StaticHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture(scope='module')
def static(tmp_path_factory):
    """
    (directory, URL prefix) where the service stores its results.
    """
    root = tmp_path_factory.mktemp('static')
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(StaticHandler, directory=str(root)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield root, f'http://127.0.0.1:{server.server_port}/'
    server.shutdown()


@pytest.fixture(scope='module')
def client(static):
    root, prefix = static
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv('PERSIST', 'local')
        mp.setenv('STATIC_PATH', str(root))
        mp.setenv('STATIC_URI_PREFIX', prefix)
        yield TestClient(app)


@pytest.fixture(scope='module')
def provider(tile_provider):
    """
    The fixture tile server's URL template in fp-web's (Leaflet) form.
    """
    return tile_provider.replace('{Z}', '{z}').replace('{X}', '{x}').replace('{Y}', '{y}')


def page_payload(name, provider):
    case = CASES[name]
    n, w, s, e = case['bounds']
    return dict(slug=case['slug'], page_number=case['page'], bbox=[w, s, e, n], zoom=case['zoom'],
                provider=provider, paper_size=case['paper'], orientation=case['orientation'],
                layout=case['layout'], text=case.get('text', ''), title=case['title'])


@pytest.fixture(scope='module')
def image_url(static):
    """
    URL of the sample snapshot's image. It's served locally from the test
    cache so that the service doesn't need AWS credentials to fetch it.
    """
    root, prefix = static
    (root / 'sample.jpg').write_bytes(fetch(SAMPLE['image_url']).read_bytes())
    return prefix + 'sample.jpg'


def sample_payload(image_url, **overrides):
    n, w, s, e = SAMPLE['bounds']
    return {**dict(slug=SAMPLE['slug'], image_url=image_url, bbox=[w, s, e, n],
                   paper_size=SAMPLE['paper'], orientation=SAMPLE['orientation'], layout=SAMPLE['layout']),
            **overrides}


def test_provider_template():
    assert provider_template('https://{s}.tile.example.com/{z}/{x}/{y}@2x.png,') == \
        'https://a.tile.example.com/{Z}/{X}/{Y}.png'
    assert provider_template('https://{S}.example.com/{z}/{x}/{y}.png,https://tile.stamen.com/utm/{Z}/{X}/{Y}.png') == \
        'https://a.example.com/{Z}/{X}/{Y}.png,https://tile.stamen.com/utm/{Z}/{X}/{Y}.png'


def test_health(client):
    assert client.get('/health').status_code == 200


def test_render_and_merge(client, static, provider, output_dir):
    root, prefix = static

    rsp = client.post('/render_page', json=page_payload('letter-portrait', provider))
    assert rsp.status_code == 200, rsp.text
    page_url = rsp.json()['pdf_url']
    assert page_url == prefix + 'atlases/15tlj042/15tlj042-A1.pdf'

    case = CASES['letter-landscape-index']
    n, w, s, e = case['envelope']
    rsp = client.post('/render_index', json=dict(page_payload('letter-landscape-index', provider),
                                                 atlas_bbox=[w, s, e, n], cols=case['cols'], rows=case['rows']))
    assert rsp.status_code == 200, rsp.text
    index_url = rsp.json()['pdf_url']
    assert index_url == prefix + 'atlases/1cr93fpr/1cr93fpr-index.pdf'

    rsp = client.post('/merge_pages', json=dict(slug='1cr93fpr', pdf_urls=[index_url, page_url]))
    assert rsp.status_code == 200, rsp.text
    assert rsp.json()['pdf_url'] == prefix + 'atlases/1cr93fpr/atlas-1cr93fpr.pdf'

    pages = rasterize(root / 'atlases/1cr93fpr/atlas-1cr93fpr.pdf', 20, output_dir / 'service-merged')
    assert [p.width > p.height for p in pages] == [True, False]


def test_invalid_payload(client, provider):
    rsp = client.post('/render_page', json=dict(page_payload('letter-portrait', provider), slug='../x'))
    assert rsp.status_code == 422


def test_decode_qr(client, image_url):
    rsp = client.post('/decode_qr', json=dict(image_url=image_url))
    assert rsp.status_code == 200, rsp.text
    assert rsp.json() == {'href': SAMPLE['href']}


def test_decode_qr_without_code(client, tile_provider):
    rsp = client.post('/decode_qr', json=dict(image_url=tile_provider.format(Z=1, X=0, Y=0)))
    assert rsp.status_code == 422


def test_georeference(client, static, image_url):
    root, prefix = static

    rsp = client.post('/georeference', json=sample_payload(image_url))
    assert rsp.status_code == 200, rsp.text
    key = f'snapshots/{SAMPLE["slug"]}/field-paper-{SAMPLE["slug"]}.tiff'
    assert rsp.json() == {'geotiff_url': prefix + key}
    assert len(geotiff_corners(root / key)) == 4


def test_georeference_without_marks(client, static):
    root, prefix = static
    Image.new('RGB', (1200, 900), 'white').save(root / 'blank.jpg')

    rsp = client.post('/georeference', json=sample_payload(prefix + 'blank.jpg'))
    assert rsp.status_code == 422
    assert 'could not process source image' in rsp.json()['detail']
