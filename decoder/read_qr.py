#!/usr/bin/env python3
"""
Print the URL in the QR code of an image read from stdin. Exits with
EX_DATAERR if there isn't one.
"""

import os
import sys
from io import BytesIO
from urllib.parse import unquote

import zbar
from PIL import Image


def read_qr(image):
    """
    Return the URL in a grayscale image's QR code, or None.
    """
    # some large, noisy photos only decode when scaled down
    return scan(image) or scan(image.resize((image.width // 2, image.height // 2), Image.LANCZOS))


def scan(image):
    scanner = zbar.ImageScanner()
    scanner.parse_config('disable')
    scanner.parse_config('qrcode.enable')

    zimg = zbar.Image(image.width, image.height, 'Y800', image.tobytes())
    scanner.scan(zimg)
    for symbol in zimg:
        href = unquote(symbol.data)
        if href.startswith('http'):
            return href

    return None


if __name__ == '__main__':
    href = read_qr(Image.open(BytesIO(sys.stdin.buffer.read())).convert('L'))
    if href is None:
        print('no QR code found', file=sys.stderr)
        exit(os.EX_DATAERR)

    print(href)
