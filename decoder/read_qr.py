#!/usr/bin/env python3
"""
Print the URL in the QR code of an image read from stdin. Exits with
EX_DATAERR if there isn't one, or the image isn't an allowed format
"""

import os
import sys
from urllib.parse import unquote

import zxingcpp
from PIL import Image

from uploads import MAX_PIXELS, UploadError, open_upload

# Small, blurry photos (e.g. from a phone at arm's length) sometimes only
# decode when scaled up; large, noisy ones when scaled down.
SCALES = (1, 2, 0.5)


def read_qr(image):
    """
    Return the URL in an image's QR code, or None.
    """
    for scale in SCALES:
        size = (round(image.width * scale), round(image.height * scale))
        if size[0] * size[1] > MAX_PIXELS:
            continue
        for result in zxingcpp.read_barcodes(image.resize(size, Image.LANCZOS), formats=zxingcpp.BarcodeFormat.QRCode):
            href = unquote(result.text)
            if href.startswith('http'):
                return href

    return None


if __name__ == '__main__':
    try:
        image = open_upload(sys.stdin.buffer.read()).convert('L')
    except UploadError as e:
        print(e, file=sys.stderr)
        sys.exit(os.EX_DATAERR)

    href = read_qr(image)
    if href is None:
        print('no QR code found', file=sys.stderr)
        sys.exit(os.EX_DATAERR)

    print(href)
