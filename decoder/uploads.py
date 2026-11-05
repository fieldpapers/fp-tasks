"""
Opening uploaded snapshot images, which are untrusted.
"""

from io import BytesIO

from PIL import Image, UnidentifiedImageError

# List of image formats we allow for snapshot uploads. Pillow supports lots
# more than this, but we limit it to reduce the attack surface (images are
# untrusted user inputs).
FORMATS = ['JPEG', 'PNG', 'TIFF']

# 50 megapixels is more than most phone photos or 600dpi scans of letter/A4
# paper. Pillow needs 4 bytes per pixel, so an RGB image this big is about 200MB
# when decoded into memory.
MAX_PIXELS = 50_000_000


class UploadError(Exception):
    pass


def open_upload(data):
    """
    Open an uploaded image (bytes), checking its format and size before
    decoding. Raises UploadError if it isn't an allowed format or is too big.
    """
    try:
        image = Image.open(BytesIO(data), formats=FORMATS)
    except UnidentifiedImageError:
        raise UploadError('not a JPEG, PNG, or TIFF image') from None
    except Image.DecompressionBombError:
        # Pillow's own internal limit (higher than ours)
        raise UploadError('image is too large') from None

    if image.width * image.height > MAX_PIXELS:
        raise UploadError(f'image is too large ({image.width}x{image.height}, max {MAX_PIXELS // 10**6} megapixels)')

    return image
