"""
Web Mercator map images, stitched from XYZ tiles.
"""

import re
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from math import floor, log, pi, radians, tan

import urllib3
from PIL import Image

TILE_SIZE = 256

http = urllib3.PoolManager(
    maxsize=4,
    headers={'User-Agent': 'Field Papers (http://fieldpapers.org/)'},
    timeout=urllib3.Timeout(connect=5, read=10),
    retries=urllib3.Retry(total=2, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504]))


class Map:
    """
    A map of a bounding box at a zoom level. templates is one or more
    comma-separated tile URL templates with {X}, {Y}, and {Z} placeholders,
    drawn in order (e.g. a base map and an overlay).
    """
    def __init__(self, templates, north, west, south, east, zoom):
        self.templates = re.split(r',(?=https?://)', templates)
        self.north, self.south = north, south
        self.zoom = zoom

        self.left, self.top = world_pixel(north, west, zoom)
        right, bottom = world_pixel(south, east, zoom)
        self.width, self.height = int(right - self.left), int(bottom - self.top)

    def point(self, lat, lon):
        """
        Position (x, y) of a location on the map image, in pixels.
        """
        x, y = world_pixel(lat, lon, self.zoom)
        return x - self.left, y - self.top

    def draw(self):
        """
        Fetch the map's tiles and stitch them into an RGB image. Tiles the
        server doesn't have are left white; any other failure raises.
        """
        img = Image.new('RGB', (self.width, self.height), 'white')

        # columns wrap around the antimeridian; rows past the poles stay blank
        n = 2 ** self.zoom
        cols = range(floor(self.left / TILE_SIZE), floor((self.left + self.width) / TILE_SIZE) + 1)
        rows = range(max(0, floor(self.top / TILE_SIZE)), min(n, floor((self.top + self.height) / TILE_SIZE) + 1))
        tiles = [(template, x, y) for template in self.templates for y in rows for x in cols]

        pool = ThreadPoolExecutor(4)
        try:
            fetched = pool.map(lambda t: fetch(t[0], t[1] % n, t[2], self.zoom), tiles)
            for (_, x, y), tile in zip(tiles, fetched):
                if tile:
                    img.paste(tile, (round(x * TILE_SIZE - self.left), round(y * TILE_SIZE - self.top)), tile)
        finally:
            pool.shutdown(cancel_futures=True)

        return img


def world_pixel(lat, lon, zoom):
    """
    Web Mercator position (x, y) of a location at a zoom level, in pixels
    from the top left of the world.
    """
    size = TILE_SIZE * 2 ** zoom
    return ((lon + 180) / 360 * size,
            (1 - log(tan(pi / 4 + radians(lat) / 2)) / pi) / 2 * size)


def fetch(template, x, y, zoom):
    """
    An RGBA tile image, or None if the server has no tile there.
    """
    url = template.replace('{X}', str(x)).replace('{Y}', str(y)).replace('{Z}', str(zoom))
    rsp = http.request('GET', url)

    if rsp.status in (204, 404):
        return None
    if rsp.status != 200:
        raise RuntimeError(f'{url}: HTTP {rsp.status}')

    return Image.open(BytesIO(rsp.data)).convert('RGBA')
