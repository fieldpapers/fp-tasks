#!/usr/bin/env python

import os
import sys

from optparse import OptionParser
from os import close, unlink
from tempfile import mkstemp

from ModestMaps import mapByExtentZoom
from ModestMaps.Geo import Location
from ModestMaps.Providers import TemplatedMercatorProvider
from raven import Client

from cairoutils import get_drawing_context
from compose import add_print_page, paper_info
from dimensions import ptpin


API_BASE = os.getenv('API_BASE_URL', 'http://fieldpapers.org/')


def render_index(paper_size, orientation, layout, atlas_id, bounds, envelope, zoom, provider, cols, rows, text, title):
    page_number = "i"

    # hm2pt_ratio = homogeneous point coordinate conversation ratio
    (page_width_pt, page_height_pt, points_FG, hm2pt_ratio) = paper_info(paper_size, orientation)

    print >> sys.stderr, "Paper: %s/%s" % (paper_size, orientation)
    print >> sys.stderr, "Width (pt): %f" % (page_width_pt)
    print >> sys.stderr, "Height (pt): %f" % (page_height_pt)
    print >> sys.stderr, "hm2pt ratio: %f" % (hm2pt_ratio)

    # margins

    map_xmin_pt = .5 * ptpin                  # left: 1/2 inch
    map_ymin_pt = 1 * ptpin                   # top: 1 inch
    map_xmax_pt = page_width_pt - .5 * ptpin  # right: 1/2 inch
    map_ymax_pt = page_height_pt - .5 * ptpin # bottom: 1/2 inch

    map_bounds_pt = (map_xmin_pt, map_ymin_pt, map_xmax_pt, map_ymax_pt)
    (north, west, south, east) = bounds

    page_href = "%satlases/%s/%s?bbox=%f,%f,%f,%f" % (API_BASE, atlas_id, page_number, west, south, east, north)

    print >> sys.stderr, "page_href: %s" % (page_href)

    page_mmap = mapByExtentZoom(TemplatedMercatorProvider(provider), Location(north, west), Location(south, east), zoom)

    pages = []

    (north, west, south, east) = envelope
    width = (east - west) / cols
    height = (north - south) / rows

    for y in range(rows):
        for x in range(cols):
            pages.append(dict(
                bounds=(north - (y * height),
                        west + (x * width),
                        south + ((rows - y - 1) * height),
                        east - ((cols - x - 1) * width)),
                number="%s%d" % (chr(ord('A') + y), x + 1),
            ))

    (handle, print_filename) = mkstemp(suffix='.pdf')
    close(handle)

    try:
        (print_context, finish_drawing) = get_drawing_context(print_filename, page_width_pt, page_height_pt)

        add_print_page(print_context, page_mmap, page_href, map_bounds_pt, points_FG, hm2pt_ratio, layout, text, None, None, pages, title)

        finish_drawing()

        return open(print_filename).read()

    finally:
        unlink(print_filename)


if __name__ == '__main__':
    usage = 'usage: %prog [options] atlas'
    parser = OptionParser(usage)

    parser.set_defaults(
        paper_size='letter',
        orientation='landscape',
        layout='full-page',
    )

    papers = 'a3 a4 letter'.split()
    orientations = 'landscape portrait'.split()
    layouts = 'full-page half-page'.split()

    parser.add_option('-s', '--paper-size', dest='paper_size',
                      help='Choice of papers: %s.' % ', '.join(papers),
                      choices=papers)
    parser.add_option('-o', '--orientation', dest='orientation',
                      help='Choice of orientations: %s.' % ', '.join(orientations),
                      choices=orientations)
    parser.add_option('-l', '--layout', dest='layout',
                      help='Choice of layouts: %s.' % ', '.join(layouts),
                      choices=layouts)
    parser.add_option('-b', '--bounds', dest='bounds',
                      help='Choice of bounds: north, west, south, east.',
                      type='float', nargs=4)
    parser.add_option('-e', '--envelope', dest='envelope',
                      help='Choice of envelope: north, west, south, east.',
                      type='float', nargs=4)
    parser.add_option('-z', '--zoom', dest='zoom',
                      help='Map zoom level.',
                      type='int')
    parser.add_option('-p', '--provider', dest='provider',
                      help='Map provider in URL template form.')
    parser.add_option('-c', '--cols', dest='cols',
                      help='Number of columns.',
                      type='int')
    parser.add_option('-r', '--rows', dest='rows',
                      help='Number of rows.',
                      type='int')
    parser.add_option('-t', '--text', dest='text', default='',
                      help='Body text.')
    parser.add_option('-T', '--title', dest='title', default='',
                      help='Title.')

    (opts, args) = parser.parse_args()
    if len(args) != 1:
        parser.print_help()
        exit(1)

    client = Client()

    try:
        print render_index(opts.paper_size, opts.orientation, opts.layout, args[0], opts.bounds, opts.envelope, opts.zoom, opts.provider, opts.cols, opts.rows, opts.text, opts.title)
    except Exception, e:
        client.captureException()
        raise
