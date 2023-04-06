from tempfile import mkstemp
from os import unlink
from math import hypot
from osgeo import osr, gdal

try:
    from PIL import Image
except ImportError:
    import Image

from ModestMaps.Geo import Location
from ModestMaps.Core import Coordinate
from ModestMaps.OpenStreetMap import Provider as OpenStreetMapProvider

from matrixmath import triangle2triangle
from imagemath import extract_image
from matrixmath import Point
from dimensions import ptpin

epsg900913 = '+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +wktext +no_defs +over'

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

def calculate_geotransform(gcps, full_width, fuller_width, buffer):
    """ Return a geotransform tuple that puts the GCPs into a chosen image size.
    """
    xs, ys = [gcp.GCPX for gcp in gcps], [gcp.GCPY for gcp in gcps]
    xmin, ymin, xmax, ymax = min(xs), min(ys), max(xs), max(ys)

    xspan = xmax - xmin
    yspan = ymin - ymax # reversed because north points up
    
    # calculate the width and height in map units
    
    aspect = xspan / yspan
    
    if aspect > 1.2:
        full_width = fuller_width
    
    width = full_width - buffer * 2
    height = abs(width / aspect)
    
    # calculate the offset and stride in map units - that's the geotransform
    
    xstride = xspan / width
    ystride = yspan / height
    
    xoff = xmin - xstride * buffer
    yoff = ymax - ystride * buffer # ymax because north points up
    
    xform = (xoff, xstride, 0, yoff, 0, ystride)
    
    # finalize the image size in image pixels and image bounds in map units
    
    full_height = int(height + buffer * 2)
    bounds = (xoff, yoff + full_height * ystride, xoff + full_width * xstride, yoff)
    
    return xform, bounds, (full_width, full_height)

def create_geotiff(image, p2s, paper_width_pt, paper_height_pt, north, west, south, east):
    """ Return raw bytes of a GCP-based GeoTIFF for this decoded scan.
    """
    #
    # Prepare geographic context - projection and ground control points.
    #
    gcps = calculate_gcps(p2s, paper_width_pt, paper_height_pt, north, west, south, east)
    merc = osr.SpatialReference()
    merc.ImportFromProj4(epsg900913)
    
    handle, png_filename = mkstemp(prefix='geotiff-', suffix='.png')
    handle, vrt_filename = mkstemp(prefix='geotiff-', suffix='.vrt')
    handle, tif1_filename = mkstemp(prefix='geotiff-', suffix='.tif')
    handle, tif2_filename = mkstemp(prefix='geotiff-', suffix='.tif')
    handle, jpg_filename = mkstemp(prefix='geotiff-', suffix='.jpg')
    
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
            tif1_filename, # destination
            vrt_filename,  # source
            format='GTiff',
            srcSRS='EPSG:4326',
            dstSRS='EPSG:3857',
            tps=True,
            dstNodata='153 153 153',
            creationOptions=['COMPRESS=deflate', 'TILED=yes']
        )
        
        #
        # Read the raw bytes of the GeoTIFF for return.
        #
        geotiff_bytes = open(tif1_filename, 'rb').read()
        
        #
        # Do another one, smaller this time for the projected JPEG.
        #
        xform, img_bounds, img_size = calculate_geotransform(gcps, 760, 960, 100)

        gdal.Warp(
            tif2_filename, # destination
            vrt_filename,  # source
            format='GTiff',
            tps=True,
            dstNodata='153 153 153',
            outputBounds=img_bounds,
            width=img_size[0],
            height=img_size[1]
        )
        
        geojpeg_img = Image.open(tif2_filename)
        geojpeg_img.save(jpg_filename)
        
    except Exception as e:
        raise
    
    finally:
        unlink(png_filename)
        unlink(vrt_filename)
        unlink(tif1_filename)
        unlink(tif2_filename)
        unlink(jpg_filename)
    
    #
    # Project image bounds to geographic coordinates
    #
    latlon = osr.SpatialReference()
    latlon.ImportFromEPSG(4326)
    
    proj = osr.CreateCoordinateTransformation(merc, latlon)
    
    x1, y1, x2, y2 = img_bounds
    lon1, lat1, z1 = proj.TransformPoint(x1, y1)
    lon2, lat2, z2 = proj.TransformPoint(x2, y2)
    img_bounds = min(lat1, lat2), min(lon1, lon2), max(lat1, lat2), max(lon1, lon2)
    
    return geotiff_bytes, geojpeg_img, img_bounds

def list_tiles_for_bounds(image, s2p, paper_width_pt, paper_height_pt, north, west, south, east):
    """ Return a list of coordinates and scan-to-coord functions for a full set of zoom levels.
    
        Internal work is done by list_tiles_for_bounds_zoom().
    """
    osm = OpenStreetMapProvider()
    coords = []
    
    for zoom in range(19):
        #
        # Coordinates of three print corners
        #
        
        ul = osm.locationCoordinate(Location(north, west)).zoomTo(zoom)
        ur = osm.locationCoordinate(Location(north, east)).zoomTo(zoom)
        lr = osm.locationCoordinate(Location(south, east)).zoomTo(zoom)
        
        #
        # Matching points in print and coordinate spaces
        #
        
        ul_pt = Point(1 * ptpin - paper_width_pt, 1.5 * ptpin - paper_height_pt)
        ul_co = Point(ul.column, ul.row)
    
        ur_pt = Point(0, 1.5 * ptpin - paper_height_pt)
        ur_co = Point(ur.column, ur.row)
    
        lr_pt = Point(0, 0)
        lr_co = Point(lr.column, lr.row)
        
        scan_dim = hypot(image.size[0], image.size[1])
        zoom_dim = hypot((lr_co.x - ul_co.x) * 256, (lr_co.y - ul_co.y) * 256)
        
        if zoom_dim/scan_dim < .05:
            # too zoomed-out
            continue
        
        if zoom_dim/scan_dim > 3.:
            # too zoomed-in
            break
        
        #
        # scan2coord by way of scan2print and print2coord
        #

        p2c = triangle2triangle(ul_pt, ul_co, ur_pt, ur_co, lr_pt, lr_co)
        s2c = s2p.multiply(p2c)
        
        coords += list_tiles_for_bounds_zoom(image, s2c, zoom)
    
    return coords
    
def list_tiles_for_bounds_zoom(image, scan2coord, zoom):
    """ Return a list of coordinates and scan-to-coord functions for a given zoom level.
    """
    coords = []
    
    ul = scan2coord(Point(0, 0))
    ur = scan2coord(Point(image.size[0], 0))
    lr = scan2coord(Point(*image.size))
    ll = scan2coord(Point(0, image.size[1]))
    
    minrow = min(ul.y, ur.y, lr.y, ll.y)
    maxrow = max(ul.y, ur.y, lr.y, ll.y)
    mincol = min(ul.x, ur.x, lr.x, ll.x)
    maxcol = max(ul.x, ur.x, lr.x, ll.x)
    
    for row in range(int(minrow), int(maxrow) + 1):
        for col in range(int(mincol), int(maxcol) + 1):
            coord = Coordinate(row, col, zoom)
            coords.append((coord, scan2coord))
    
    return coords
    
def extract_tile_for_coord(image, coord, scan2coord):
    """ Return an image for a given coordinate.
    """
    coord_bbox = coord.column, coord.row, coord.column + 1, coord.row + 1
    tile_img = extract_image(scan2coord, coord_bbox, image, (256, 256), 256/8)
    
    return tile_img
