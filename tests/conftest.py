"""
End-to-end tests of the HTTP API, run inside the fp-tasks image (see `make
test`). Images produced by the tests are written to tests/actual/ and compared
with tests/expected/; run pytest with --update-expected to accept changes.
"""

import functools
import io
import random
import re
import shutil
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFilter

from service.app import app

TESTS = Path(__file__).parent
ACTUAL = TESTS / 'actual'
EXPECTED = TESTS / 'expected'


def pytest_addoption(parser):
    parser.addoption('--update-expected', action='store_true', help='overwrite tests/expected/ with actual images')


def tile(z, x, y):
    """
    A deterministic, vaguely map-like 256px PNG tile, labeled with its
    coordinates.
    """
    rng = random.Random(f'{z}/{x}/{y}')
    img = Image.new('RGB', (256, 256), (200 + rng.randrange(40), 210 + rng.randrange(30), 190 + rng.randrange(40)))

    draw = ImageDraw.Draw(img)
    for i in range(0, 256, 64):
        draw.line([(i, 0), (i, 255)], fill='white', width=5)
        draw.line([(0, i), (255, i)], fill='white', width=5)
    draw.line([(0, rng.randrange(256)), (255, rng.randrange(256))], fill=(230, 120, 60), width=7)
    draw.text((8, 8), f'{z}/{x}/{y}', fill=(40, 40, 40))

    buf = io.BytesIO()
    img.save(buf, 'PNG')
    return buf.getvalue()


class Handler(SimpleHTTPRequestHandler):
    """
    Serves generated tiles at /tiles/{z}/{x}/{y}.png, and files in tests/.
    """

    def do_GET(self):
        if m := re.fullmatch(r'/tiles/(\d+)/(\d+)/(\d+)\.png', self.path):
            body = tile(*map(int, m.groups()))
            self.send_response(200)
            self.send_header('Content-Type', 'image/png')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()

    def log_message(self, *args):
        pass


@pytest.fixture(scope='session')
def server():
    """
    Base URL of a local server for tiles and the files in tests/.
    """
    shutil.rmtree(ACTUAL, ignore_errors=True)
    ACTUAL.mkdir()

    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(TESTS)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f'http://127.0.0.1:{server.server_port}/'
    server.shutdown()


@pytest.fixture(scope='session')
def client(server):
    """
    API client. The service stores its results in tests/actual/.
    """
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv('PERSIST', 'local')
        mp.setenv('STATIC_PATH', str(ACTUAL))
        mp.setenv('STATIC_URI_PREFIX', server + 'actual/')
        mp.setenv('API_BASE_URL', 'https://fieldpapers.org/')
        yield TestClient(app)


@pytest.fixture
def compare(request):
    """
    Function that saves an image to tests/actual/<name>.png and checks that it
    matches tests/expected/<name>.png.
    """
    update = request.config.getoption('update_expected')

    def compare(name, img, tolerance):
        actual = ACTUAL / f'{name}.png'
        expected = EXPECTED / f'{name}.png'
        img.convert('RGB').save(actual)

        if update:
            EXPECTED.mkdir(exist_ok=True)
            shutil.copy(actual, expected)
            return

        assert expected.exists(), f'{expected} is missing; run pytest with --update-expected'
        exp = Image.open(expected)
        assert exp.size == img.size, f'{actual} is {img.size}, expected {exp.size}'
        diff = rms(exp, img)
        assert diff < tolerance, f'{actual} differs from {expected} (rms {diff:.1f})'

    return compare


def rms(a, b):
    """
    RMS difference (0-255) of two images in grayscale, blurred so that
    antialiasing and sub-pixel shifts don't count.
    """
    a, b = (numpy.asarray(i.convert('L').filter(ImageFilter.GaussianBlur(2)), float) for i in (a, b))
    return float(numpy.sqrt(((a - b) ** 2).mean()))
