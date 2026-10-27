from io import BytesIO
from re import DOTALL, compile

from cairo import FILTER_NEAREST, MIME_TYPE_JPEG
from PIL import Image


def place_image(context, img, x, y, width, height):
    """Add an image to a given context, at a position and size.

    Assume that the scale matrix of the context is already in pt.
    """
    context.save()
    context.translate(x, y)

    # determine the scale needed to make the image the requested size
    xscale = width / float(img.get_width())
    yscale = height / float(img.get_height())
    context.scale(xscale, yscale)

    # paint the image, without the PDF /Interpolate flag
    attach_jpeg(img)
    context.set_source_surface(img, 0, 0)
    context.get_source().set_filter(FILTER_NEAREST)
    context.paint()

    context.restore()


def attach_jpeg(img):
    """Have cairo embed an ImageSurface in PDFs as a quality-75 JPEG, if
    that is smaller than a lossless encoding. Alpha is dropped then.
    """
    if img.get_mime_data(MIME_TYPE_JPEG):
        return

    img.flush()
    w, h = img.get_width(), img.get_height()
    # ARGB32 and RGB24 surfaces are native-endian 32-bit words: BGRA/BGRx bytes
    # on little-endian machines
    rgb = Image.frombuffer('RGBA', (w, h), bytes(img.get_data()), 'raw', 'BGRA', img.get_stride(), 1).convert('RGB')

    jpg, png = BytesIO(), BytesIO()
    rgb.save(jpg, 'JPEG', quality=75)
    rgb.save(png, 'PNG')

    if jpg.tell() < png.tell():
        img.set_mime_data(MIME_TYPE_JPEG, jpg.getvalue())


def draw_box(context, x, y, w, h):
    context.move_to(x, y)
    context.rel_line_to(w, 0)
    context.rel_line_to(0, h)
    context.rel_line_to(-w, 0)
    context.rel_line_to(0, -h)


def draw_circle(context, x, y, radius):
    bezier = radius

    context.move_to(x, y - radius)
    context.rel_curve_to(bezier, 0, radius, bezier, radius, radius)
    context.rel_curve_to(0, bezier, -bezier, radius, -radius, radius)
    context.rel_curve_to(-bezier, 0, -radius, -bezier, -radius, -radius)
    context.rel_curve_to(0, -bezier, bezier, -radius, radius, -radius)


def flow_text(context, width, line_height, text):
    """Flow a block of text into the given width, returning when needed."""
    still = compile(r'^\S')
    words = compile(r'^(\S+(\s*))(.*)$', DOTALL)

    CR, LF = '\r', '\n'
    text = text.replace(CR + LF, LF).replace(CR, LF)

    while still.match(text):
        match = words.match(text)
        head, space, text = match.group(1), match.group(2), match.group(3)

        head_width = context.text_extents(head).width

        x, y = context.get_current_point()

        # will we move too far to the right with this word?
        if x + head_width > width:
            context.move_to(0, y + line_height)

        # advances the current point past the word and its spaces; a newline
        # would be drawn as a missing glyph
        context.show_text(head.replace(LF, ''))

        # apply newline if necessary
        while LF in space:
            y = context.get_current_point()[1]
            context.move_to(0, y + line_height)
            space = space[1 + space.index(LF) :]
