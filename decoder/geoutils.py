from tempfile import mkstemp
from os import close, unlink
from osgeo import gdal

from matrixmath import Point
from dimensions import ptpin

def calculate_gcps(p2s, paper_width_pt, paper_height_pt, north, west, south, east):
    """
    """
    # x, y in printed points
    right_pt = 0
    left_pt = -paper_width_pt + 1 * ptpin
    lower_pt = 0
    upper_pt = -paper_height_pt + 1.5 * ptpin
    
    ll_pt = Point(left_pt, lower_pt)
    ul_pt = Point(left_pt, upper_pt)
    ur_pt = Point(right_pt, upper_pt)
    lr_pt = Point(right_pt, lower_pt)
    
    # x, y in image pixels
    ul_px, ur_px, lr_px, ll_px = [p2s(pt) for pt in (ul_pt, ur_pt, lr_pt, ll_pt)]
    
    ul_gcp = gdal.GCP(west, north, 0, ul_px.x, ul_px.y)
    ur_gcp = gdal.GCP(east, north, 0, ur_px.x, ur_px.y)
    lr_gcp = gdal.GCP(east, south, 0, lr_px.x, lr_px.y)
    ll_gcp = gdal.GCP(west, south, 0, ll_px.x, ll_px.y)
    
    return [ul_gcp, ur_gcp, lr_gcp, ll_gcp]

def create_geotiff(image, p2s, paper_width_pt, paper_height_pt, north, west, south, east):
    """ Return raw bytes of a GCP-based GeoTIFF for this decoded scan.
    """
    gcps = calculate_gcps(p2s, paper_width_pt, paper_height_pt, north, west, south, east)

    handle, png_filename = mkstemp(prefix='geotiff-', suffix='.png')
    close(handle)
    handle, vrt_filename = mkstemp(prefix='geotiff-', suffix='.vrt')
    close(handle)
    handle, tif_filename = mkstemp(prefix='geotiff-', suffix='.tif')
    close(handle)

    try:
        image.save(png_filename)

        gdal.Translate(
            vrt_filename, # destination
            png_filename,  # source
            format='VRT',
            outputSRS='EPSG:4326',
            GCPs=gcps
        )

        gdal.Warp(
            tif_filename, # destination
            vrt_filename,  # source
            format='GTiff',
            srcSRS='EPSG:4326',
            dstSRS='EPSG:3857',
            tps=True,
            dstNodata='153 153 153',
            creationOptions=['COMPRESS=deflate', 'TILED=yes']
        )

        return open(tif_filename, 'rb').read()

    finally:
        unlink(png_filename)
        unlink(vrt_filename)
        unlink(tif_filename)
