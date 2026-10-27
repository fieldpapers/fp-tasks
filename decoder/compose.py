#!/usr/bin/env python3

import subprocess
import sys
from io import BytesIO
from math import pi
from os.path import dirname
from os.path import join as pathjoin

from cairo import FONT_SLANT_NORMAL, FONT_WEIGHT_BOLD, Context, ImageSurface, PDFSurface

from dimensions import point_A, point_B, point_C, point_D, point_E, ptpin
from svgutils import draw_box, draw_circle, flow_text, place_image

# found by fontconfig (Debian's fonts-liberation)
FONT = 'Liberation Sans'


def get_qrcode_image(print_href):
    """Render a QR code to an ImageSurface."""
    qr_code = BytesIO(
        subprocess.run(
            ['qrencode', '-m', '0', '-s', '19', '-o', '-', print_href], stdout=subprocess.PIPE, check=True
        ).stdout
    )

    return ImageSurface.create_from_png(qr_code)


def get_mmap_image(mmap):
    """Render a Map to an ImageSurface."""
    png = BytesIO()
    mmap.draw().save(png, 'PNG')
    png.seek(0)

    return ImageSurface.create_from_png(png)


def paper_info(paper_size, orientation):
    """Return page width, height, differentiating points and aspect ration."""
    dim = __import__('dimensions')

    paper_size = {'letter': 'ltr', 'a4': 'a4', 'a3': 'a3'}[paper_size.lower()]
    width, height = getattr(dim, 'paper_size_%(orientation)s_%(paper_size)s' % locals())
    point_F = getattr(dim, 'point_F_%(orientation)s_%(paper_size)s' % locals())
    point_G = getattr(dim, 'point_G_%(orientation)s_%(paper_size)s' % locals())
    ratio = getattr(dim, 'ratio_%(orientation)s_%(paper_size)s' % locals())

    return width, height, (point_F, point_G), ratio


def add_page_text(ctx, text, x, y, width, height):
    ctx.save()
    ctx.translate(x, y)
    ctx.move_to(0, 12)

    ctx.set_source_rgb(0, 0, 0)
    ctx.select_font_face(FONT)
    ctx.set_font_size(10)

    flow_text(ctx, width, 12, text)

    ctx.restore()


def get_map_scale(mmap, map_height_pt):
    vertical_degrees = mmap.north - mmap.south
    vertical_meters = 6378137 * pi * 2 * vertical_degrees / 360
    pts_per_meter = map_height_pt / vertical_meters

    # a selection of reasonable scale values to show
    meterses = (
        list(range(50, 300, 50))
        + list(range(300, 1000, 100))
        + list(range(1000, 10000, 1000))
        + list(range(10000, 100000, 10000))
        + list(range(100000, 1000000, 100000))
        + list(range(1000000, 10000000, 1000000))
    )

    for meters in meterses:
        points = meters * pts_per_meter

        if points > 100:
            # stop at an inch and a half or so
            break

    if meters > 1000:
        distance = '%d' % (meters / 1000.0)
        units = 'kilometers'
    elif meters == 1000:
        distance = '%d' % (meters / 1000.0)
        units = 'kilometer'
    else:
        distance = '%d' % meters
        units = 'meters'

    return points, distance, units


def add_scale_bar(ctx, mmap, map_height_pt):
    size, distance, units = get_map_scale(mmap, map_height_pt)

    ctx.save()
    ctx.translate(60, map_height_pt - 20)

    draw_box(ctx, -50, -10, size + 10 + 45, 20)
    ctx.set_source_rgb(1, 1, 1)
    ctx.fill()

    #
    # true north
    #

    draw_circle(ctx, -40, 0, 6.7)
    ctx.set_source_rgb(0, 0, 0)
    ctx.fill()

    ctx.move_to(-40, -6.7)
    ctx.line_to(-38.75, -2.2)
    ctx.line_to(-41.25, -2.2)
    ctx.line_to(-40, -6.5)
    ctx.set_source_rgb(1, 1, 1)
    ctx.fill()

    ctx.set_source_rgb(0, 0, 0)
    ctx.set_font_size(5.8)

    ctx.move_to(-25.1, -2.1)
    ctx.show_text('TRUE')
    ctx.move_to(-27.6, 4.9)
    ctx.show_text('NORTH')

    #
    # scale bar
    #

    ctx.move_to(0, 2)
    ctx.line_to(0, 5)
    ctx.line_to(size, 5)
    ctx.line_to(size, 2)

    ctx.set_source_rgb(0, 0, 0)
    ctx.set_line_width(0.5)
    ctx.set_dash([])
    ctx.stroke()

    ctx.set_font_size(9)
    zero_width = ctx.text_extents('0').width
    distance_width = ctx.text_extents(distance).width

    ctx.move_to(0, 0)
    ctx.show_text('0')

    ctx.move_to(size - distance_width, 0)
    ctx.show_text(distance)

    ctx.set_font_size(7)
    units_width = ctx.text_extents(units).width

    ctx.move_to(zero_width + (size - zero_width - distance_width) / 2 - units_width / 2, 0)
    ctx.show_text(units.upper())

    ctx.restore()


def print_pdf(page_width_pt, page_height_pt, *args):
    """Render a page with add_print_page(); returns the PDF as bytes."""
    pdf = BytesIO()
    surface = PDFSurface(pdf, page_width_pt, page_height_pt)
    add_print_page(Context(surface), *args)
    surface.finish()

    return pdf.getvalue()


def add_print_page(ctx, mmap, href, well_bounds_pt, points_FG, hm2pt_ratio, layout, text, indexees, title):
    print('Adding print page:', href, file=sys.stderr)

    well_xmin_pt, well_ymin_pt, well_xmax_pt, well_ymax_pt = well_bounds_pt
    well_width_pt, well_height_pt = well_xmax_pt - well_xmin_pt, well_ymax_pt - well_ymin_pt
    well_aspect_ratio = well_width_pt / well_height_pt

    #
    # Offset drawing area to top-left of map area
    #
    ctx.translate(well_xmin_pt, well_ymin_pt)

    #
    # Build up map area
    #
    img = get_mmap_image(mmap)

    if layout == 'half-page' and well_aspect_ratio > 1:
        map_width_pt, map_height_pt = well_width_pt / 2, well_height_pt
        add_page_text(ctx, text, map_width_pt + 24, 24, map_width_pt - 48, map_height_pt - 48)

    elif layout == 'half-page' and well_aspect_ratio < 1:
        map_width_pt, map_height_pt = well_width_pt, well_height_pt / 2
        add_page_text(ctx, text, 32, map_height_pt + 16, map_width_pt - 64, map_height_pt - 32)

    else:
        map_width_pt, map_height_pt = well_width_pt, well_height_pt

    place_image(ctx, img, 0, 0, map_width_pt, map_height_pt)

    #
    # Perhaps some boxes?
    #
    page_numbers = []

    for page in indexees:
        north, west, south, east = page['bounds']

        (x1, y1), (x2, y2) = mmap.point(north, west), mmap.point(south, east)

        x1, x2 = map_width_pt * x1 / mmap.width, map_width_pt * x2 / mmap.width
        y1, y2 = map_height_pt * y1 / mmap.height, map_height_pt * y2 / mmap.height

        draw_box(ctx, x1, y1, x2 - x1, y2 - y1)
        ctx.set_source_rgb(0, 0, 0)
        ctx.set_line_width(1)
        ctx.set_dash([])
        ctx.stroke()

        page_numbers.append((x1, y1, x2, y2, page['number']))

    #
    # Calculate positions of registration points
    #
    ctx.save()

    ctx.translate(well_width_pt, well_height_pt)
    ctx.scale(1 / hm2pt_ratio, 1 / hm2pt_ratio)

    reg_points = (point_A, point_B, point_C, point_D, point_E) + points_FG

    device_points = [ctx.user_to_device(pt.x, pt.y) for pt in reg_points]

    ctx.restore()

    #
    # Draw QR code area
    #
    ctx.save()

    ctx.translate(well_width_pt, well_height_pt)

    draw_box(ctx, 0, 0, -90, -90)
    ctx.set_source_rgb(1, 1, 1)
    ctx.fill()

    place_image(ctx, get_qrcode_image(href), -83, -83, 83, 83)

    ctx.restore()

    #
    # Draw registration points
    #
    for x, y in device_points:
        x, y = ctx.device_to_user(x, y)

        draw_circle(ctx, x, y, 0.12 * ptpin)
        ctx.set_source_rgb(0, 0, 0)
        ctx.set_line_width(0.5)
        ctx.set_dash([1.5, 3])
        ctx.stroke()

    for x, y in device_points:
        x, y = ctx.device_to_user(x, y)

        draw_circle(ctx, x, y, 0.12 * ptpin)
        ctx.set_source_rgb(1, 1, 1)
        ctx.fill()

    for x, y in device_points:
        x, y = ctx.device_to_user(x, y)

        draw_circle(ctx, x, y, 0.06 * ptpin)
        ctx.set_source_rgb(0, 0, 0)
        ctx.fill()

    #
    # Draw top-left icon
    #
    icon = pathjoin(dirname(__file__), 'images/logo.png')
    img = ImageSurface.create_from_png(icon)
    place_image(ctx, img, 0, -36, 129.1, 36)

    ctx.select_font_face(FONT)
    ctx.set_font_size(12)

    line = href.split('?')[0]
    text_width = ctx.text_extents(line).width

    ctx.move_to(well_width_pt - text_width, -6)
    ctx.show_text(line)

    title_width = ctx.text_extents(title).width

    ctx.move_to(well_width_pt - title_width, -24)
    ctx.show_text(title)

    add_scale_bar(ctx, mmap, map_height_pt)

    ctx.select_font_face(FONT, FONT_SLANT_NORMAL, FONT_WEIGHT_BOLD)
    ctx.set_font_size(18)

    for x1, y1, x2, y2, number in page_numbers:
        num_ext = ctx.text_extents(number)
        offset_x, offset_y = (x1 + x2 - num_ext.width) / 2, (y1 + y2 + num_ext.height) / 2

        draw_box(ctx, offset_x - 4, offset_y - num_ext.height - 4, num_ext.width + 8, num_ext.height + 8)
        ctx.set_source_rgb(1, 1, 1)
        ctx.fill()

        ctx.set_source_rgb(0, 0, 0)
        ctx.move_to(offset_x, offset_y)
        ctx.show_text(number)

    ctx.show_page()
