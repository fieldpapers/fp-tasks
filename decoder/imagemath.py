from PIL import Image
from PIL.ImageOps import autocontrast

from numpy import asarray, bincount, float64
from scipy.ndimage import find_objects, gaussian_filter, label, maximum_filter, minimum_filter

class Blob:
    """ A dark dot: center in image pixels, size (area) in thumbnail pixels.
    """
    def __init__(self, x, y, size):
        self.x = x
        self.y = y
        self.size = size

def imgblobs(img):
    """ Find dark dots in an image, such as printed registration marks.

        Assumes blobs somewhere in the neighborhood of 0.25" or so
        on a scan not much smaller than 8" on its smallest side.
    """
    mask = blob_mask(img)
    labels, _ = label(mask)
    sizes = bincount(labels.ravel())

    # thumbnail to image pixels
    xscale = img.width / mask.shape[1]
    yscale = img.height / mask.shape[0]

    # largest likely blob size, from scan size, 0.25", and floor of 8" for print.
    maxdim = min(*img.size) * 0.25 / 8.0

    # smallest likely blob size, wild-ass-guessed.
    mindim = 8

    blobs = []

    for (i, (ys, xs)) in enumerate(find_objects(labels)):
        size = int(sizes[i + 1])

        if size / ((xs.stop - xs.start) * (ys.stop - ys.start)) < 0.7:
            # too spidery
            continue

        w = (xs.stop - xs.start) * xscale
        h = (ys.stop - ys.start) * yscale

        if w < mindim or h < mindim:
            # too small
            continue

        if w > maxdim or h > maxdim:
            # too large
            continue

        if max(w, h) / min(w, h) > 2:
            # too stretched
            continue

        blobs.append(Blob((xs.start + xs.stop) / 2 * xscale, (ys.start + ys.stop) / 2 * yscale, size))

    return blobs

def blob_mask(img):
    """ Thumbnail of an image as a boolean array, true in dark, blob-like areas.
    """
    thumb = img.convert('L')
    thumb.thumbnail((1500, 1500), Image.LANCZOS)

    gray = asarray(autocontrast(thumb), float64)
    gray = gaussian_filter(gray, 0.5, truncate=2.0, mode='constant')

    # high-pass, see http://www.gimp.org/tutorials/Sketch_Effect/
    gray = .5 * gray + .5 * (0xff - gaussian_filter(gray, 8, truncate=2.0, mode='constant'))

    mask = gray < 116
    return maximum_filter(minimum_filter(mask, 5, mode='nearest'), 5, mode='nearest')
