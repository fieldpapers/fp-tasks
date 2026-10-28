#!/usr/bin/env python3

import os
import sys
from io import BytesIO
from optparse import OptionParser

from PIL import Image

from decode import get_paper_size, paper_matches
from geoutils import create_geotiff
from imagemath import imgblobs


class SnapshotError(Exception):
    """
    The image can't be georeferenced (retrying won't help).
    """

    pass


def process_snapshot(input, bounds, paper, orientation, layout):
    """
    Georeference an image (bytes) of a printed atlas page. bounds are the
    page's (north, west, south, east); paper, orientation, and layout are its
    atlas's. Returns GeoTIFF bytes.
    """
    image = Image.open(BytesIO(input))
    image.load()

    # create_geotiff's JPEG compression needs RGB; uploads may be RGBA (e.g. a
    # PNG screenshot) or palette-based.
    if image.mode != 'RGB':
        image = image.convert('RGB')

    (north, west, south, east) = page_bounds(bounds, orientation, layout)
    blobs = imgblobs(image)

    for s2p, _paper, _orientation in paper_matches(blobs, image.size):
        print(_paper, _orientation, '--', s2p, file=sys.stderr)

        if (paper, orientation) != (_paper, _orientation):
            continue

        (paper_width_pt, paper_height_pt) = get_paper_size(paper, orientation)
        geo_args = (paper_width_pt, paper_height_pt, north, west, south, east)

        return create_geotiff(image, s2p.inverse(), *geo_args)

    raise SnapshotError('could not process source image')


def page_bounds(bounds, orientation, layout):
    """
    Bounds of the full printed page, given the bounds of its map. A
    half-page map covers half of the page's registration frame.
    """
    (north, west, south, east) = bounds

    if layout == 'half-page' and orientation == 'landscape':
        east += east - west
        print(
            'Adjusted',
            orientation,
            layout,
            'bounds to %.6f, %.6f, %.6f, %.6f' % (north, west, south, east),
            file=sys.stderr,
        )

    elif layout == 'half-page' and orientation == 'portrait':
        south += south - north
        print(
            'Adjusted',
            orientation,
            layout,
            'bounds to %.6f, %.6f, %.6f, %.6f' % (north, west, south, east),
            file=sys.stderr,
        )

    else:
        print(
            'Kept',
            orientation,
            layout,
            'bounds at %.6f, %.6f, %.6f, %.6f' % (north, west, south, east),
            file=sys.stderr,
        )

    return (north, west, south, east)


if __name__ == '__main__':
    usage = 'usage: %prog [options] < image > geotiff'
    parser = OptionParser(usage)

    parser.set_defaults(layout='full-page')

    papers = 'a3 a4 letter'.split()
    orientations = 'landscape portrait'.split()
    layouts = 'full-page half-page'.split()

    parser.add_option(
        '-s', '--paper-size', dest='paper_size', help='Choice of papers: %s.' % ', '.join(papers), choices=papers
    )
    parser.add_option(
        '-o',
        '--orientation',
        dest='orientation',
        help='Choice of orientations: %s.' % ', '.join(orientations),
        choices=orientations,
    )
    parser.add_option(
        '-l', '--layout', dest='layout', help='Choice of layouts: %s.' % ', '.join(layouts), choices=layouts
    )
    parser.add_option(
        '-b', '--bounds', dest='bounds', help='Page bounds: north, west, south, east.', type='float', nargs=4
    )

    (opts, args) = parser.parse_args()
    if args or not (opts.paper_size and opts.orientation and opts.bounds):
        parser.print_help()
        exit(1)

    try:
        geotiff = process_snapshot(sys.stdin.buffer.read(), opts.bounds, opts.paper_size, opts.orientation, opts.layout)
    except SnapshotError as e:
        print(e, file=sys.stderr)
        # fp-tasks' service maps this status to a 422
        exit(os.EX_DATAERR)

    sys.stdout.buffer.write(geotiff)
