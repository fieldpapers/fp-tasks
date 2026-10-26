from math import e

from PIL import Image
from PIL.ImageOps import autocontrast
from PIL.ImageFilter import MinFilter, MaxFilter

from numpy import array, ubyte, convolve

from BlobDetector import detect

class Blob:
    """
    """
    def __init__(self, xmin, ymin, xmax, ymax, size):
        self.xmin = xmin
        self.ymin = ymin
        self.xmax = xmax
        self.ymax = ymax
        self.size = size
        
        self.x = (xmin + xmax) / 2
        self.y = (ymin + ymax) / 2
        self.w = xmax - xmin
        self.h = ymax - ymin
        
        self.bbox = (xmin, ymin, xmax, ymax)

def imgblobs(img):
    """ Extract bboxes of blobs from an image.
    
        Assumes blobs somewhere in the neighborhood of 0.25" or so
        on a scan not much smaller than 8" on its smallest side.
        
        Each blob is a bbox: (xmin, ymin, xmax, ymax)
    """
    thumb = img.copy().convert('L')
    thumb.thumbnail((1500, 1500), Image.LANCZOS)
    
    # needed to get back up to input image size later.
    scale = float(img.size[0]) / float(thumb.size[0])
    
    # largest likely blob size, from scan size, 0.25", and floor of 8" for print.
    maxdim = min(*img.size) * 0.25 / 8.0
    
    # smallest likely blob size, wild-ass-guessed.
    mindim = 8
    
    thumb = autocontrast(thumb)
    thumb = lowpass(thumb, 1)
    thumb = highpass(thumb, 16)
    
    thumb = thumb.point(lambda p: (p < 116) and 0xFF or 0x00)
    thumb = thumb.filter(MinFilter(5)).filter(MaxFilter(5))
    
    blobs = []
    
    for (xmin, ymin, xmax, ymax, pixels) in detect(thumb):
    
        coverage = pixels / float((1 + xmax - xmin) * (1 + ymax - ymin))
        
        if coverage < 0.7:
            # too spidery
            continue
        
        xmin *= scale
        ymin *= scale
        xmax *= scale
        ymax *= scale
        
        blob = Blob(xmin, ymin, xmax, ymax, pixels)
        
        if blob.w < mindim or blob.h < mindim:
            # too small
            continue
        
        if blob.w > maxdim or blob.h > maxdim:
            # too large
            continue
        
        if max(blob.w, blob.h) / min(blob.w, blob.h) > 2:
            # too stretched
            continue
        
        blobs.append(blob)
    
    return blobs

def gaussian(data, radius):
    """ Perform a gaussian blur on a data array representing an image.
    
        Manipulate the data array directly.
    """
    #
    # Build a convolution kernel based on
    # http://en.wikipedia.org/wiki/Gaussian_function#Two-dimensional_Gaussian_function
    #
    kernel = range(-radius, radius + 1)
    kernel = [(d ** 2) / (2 * (radius * .5) ** 2) for d in kernel]
    kernel = [e ** -d for d in kernel]
    kernel = array(kernel, dtype=float) / sum(kernel)
    
    #
    # Convolve in two dimensions.
    #
    for row in range(data.shape[0]):
        data[row,:] = convolve(data[row,:], kernel, 'same')
    
    for col in range(data.shape[1]):
        data[:,col] = convolve(data[:,col], kernel, 'same')

def lowpass(img, radius):
    """ Perform a low-pass with a given radius on the image, return a new image.
    """
    #
    # Convert image to array
    #
    blur = img2arr(img)
    gaussian(blur, radius)
    
    return arr2img(blur)

def highpass(img, radius):
    """ Perform a high-pass with a given radius on the image, return a new image.
    """
    #
    # Convert image to arrays
    #
    orig = img2arr(img)
    blur = orig.copy()
    gaussian(blur, radius)
    
    #
    # Combine blurred with original, see http://www.gimp.org/tutorials/Sketch_Effect/
    #
    high = .5 * orig + .5 * (0xff - blur)
    
    return arr2img(high)

def arr2img(ar):
    """ Convert Numeric array to PIL Image.
    """
    return Image.frombytes('L', (ar.shape[1], ar.shape[0]), ar.astype(ubyte))

def img2arr(im):
    """ Convert PIL Image to Numeric array.
    """
    return array(im, dtype=ubyte)
