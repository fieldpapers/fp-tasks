import ctypes as ct
from re import compile, DOTALL

from cairo import ImageSurface, Context, FORMAT_A8

def place_image(context, img, x, y, width, height):
    """ Add an image to a given context, at a position and size.
    
        Assume that the scale matrix of the context is already in pt.
    """
    context.save()
    context.translate(x, y)
    
    # determine the scale needed to make the image the requested size
    xscale = width / float(img.get_width())
    yscale = height / float(img.get_height())
    context.scale(xscale, yscale)

    # paint the image
    context.set_source_surface(img, 0, 0)
    context.paint()

    context.restore()

def draw_box(context, x, y, w, h):
    """
    """
    context.move_to(x, y)
    context.rel_line_to(w, 0)
    context.rel_line_to(0, h)
    context.rel_line_to(-w, 0)
    context.rel_line_to(0, -h)

def draw_circle(context, x, y, radius):
    """
    """
    bezier = radius

    context.move_to(x, y - radius)
    context.rel_curve_to(bezier, 0, radius, bezier, radius, radius)
    context.rel_curve_to(0, bezier, -bezier, radius, -radius, radius)
    context.rel_curve_to(-bezier, 0, -radius, -bezier, -radius, -radius)
    context.rel_curve_to(0, -bezier, bezier, -radius, radius, -radius)

def draw_cross(context, x, y, radius, weight):
    """
    """
    context.move_to(x + weight, y)
    context.line_to(x + radius + weight, y + radius)
    context.line_to(x + radius, y + radius + weight)
    context.line_to(x, y + weight)
    context.line_to(x - radius, y + radius + weight)
    context.line_to(x - radius - weight, y + radius)
    context.line_to(x - weight, y)
    context.line_to(x - radius - weight, y - radius)
    context.line_to(x - radius, y - radius - weight)
    context.line_to(x, y - weight)
    context.line_to(x + radius, y - radius - weight)
    context.line_to(x + radius + weight, y - radius)

def flow_text(context, width, line_height, text):
    """ Flow a block of text into the given width, returning when needed.
    """
    still = compile(r'^\S')
    words = compile(r'^(\S+(\s*))(.*)$', DOTALL)
    
    CR, LF = '\r', '\n'
    text = text.replace(CR+LF, LF).replace(CR, LF)
    
    while still.match(text):
        match = words.match(text)
        head, space, text = match.group(1), match.group(2), match.group(3)
        
        head_extent = context.text_extents(head)
        head_width, x_advance = head_extent.width, head_extent.x_advance
        
        x, y = context.get_current_point()

        # will we move too far to the right with this word?
        if x + head_width > width:
            context.move_to(0, y + line_height)
        
        context.show_text(head)
        context.rel_move_to(x_advance, 0)
        
        # apply newline if necessary
        while LF in space:
            y = context.get_current_point()[1]
            context.move_to(0, y + line_height)
            space = space[1 + space.index(LF):]

# https://www.cairographics.org/cookbook/freetypepython/
_initialized_create_cairo_font_face_for_file = False
def create_cairo_font_face_for_file (filename, faceindex=0, loadoptions=0):
    "given the name of a font file, and optional faceindex to pass to FT_New_Face" \
    " and loadoptions to pass to cairo_ft_font_face_create_for_ft_face, creates" \
    " a cairo.FontFace object that may be used to render text with that font."
    global _initialized_create_cairo_font_face_for_file
    global _freetype_so
    global _cairo_so
    global _ft_lib
    global _ft_destroy_key
    global _surface

    CAIRO_STATUS_SUCCESS = 0
    FT_Err_Ok = 0

    if not _initialized_create_cairo_font_face_for_file:
        # find shared objects
        _freetype_so = ct.CDLL("libfreetype.so.6")
        _cairo_so = ct.CDLL("libcairo.so.2")
        _cairo_so.cairo_ft_font_face_create_for_ft_face.restype = ct.c_void_p
        _cairo_so.cairo_ft_font_face_create_for_ft_face.argtypes = [ ct.c_void_p, ct.c_int ]
        _cairo_so.cairo_font_face_get_user_data.restype = ct.c_void_p
        _cairo_so.cairo_font_face_get_user_data.argtypes = (ct.c_void_p, ct.c_void_p)
        _cairo_so.cairo_font_face_set_user_data.argtypes = (ct.c_void_p, ct.c_void_p, ct.c_void_p, ct.c_void_p)
        _cairo_so.cairo_set_font_face.argtypes = [ ct.c_void_p, ct.c_void_p ]
        _cairo_so.cairo_font_face_status.argtypes = [ ct.c_void_p ]
        _cairo_so.cairo_font_face_destroy.argtypes = (ct.c_void_p,)
        _cairo_so.cairo_status.argtypes = [ ct.c_void_p ]
        # initialize freetype
        _ft_lib = ct.c_void_p()
        status = _freetype_so.FT_Init_FreeType(ct.byref(_ft_lib))
        if  status != FT_Err_Ok :
            raise RuntimeError("Error %d initializing FreeType library." % status)
        #end if

        class PycairoContext(ct.Structure):
            _fields_ = \
                [
                    ("PyObject_HEAD", ct.c_byte * object.__basicsize__),
                    ("ctx", ct.c_void_p),
                    ("base", ct.c_void_p),
                ]
        #end PycairoContext

        _surface = ImageSurface(FORMAT_A8, 0, 0)
        _ft_destroy_key = ct.c_int() # dummy address
        _initialized_create_cairo_font_face_for_file = True
    #end if

    ft_face = ct.c_void_p()
    cr_face = None
    try :
        # load FreeType face
        status = _freetype_so.FT_New_Face(_ft_lib, filename.encode("utf-8"), faceindex, ct.byref(ft_face))
        if status != FT_Err_Ok :
            raise RuntimeError("Error %d creating FreeType font face for %s" % (status, filename))
        #end if

        # create Cairo font face for freetype face
        cr_face = _cairo_so.cairo_ft_font_face_create_for_ft_face(ft_face, loadoptions)
        status = _cairo_so.cairo_font_face_status(cr_face)
        if status != CAIRO_STATUS_SUCCESS :
            raise RuntimeError("Error %d creating cairo font face for %s" % (status, filename))
        #end if
        # Problem: Cairo doesn't know to call FT_Done_Face when its font_face object is
        # destroyed, so we have to do that for it, by attaching a cleanup callback to
        # the font_face. This only needs to be done once for each font face, while
        # cairo_ft_font_face_create_for_ft_face will return the same font_face if called
        # twice with the same FT Face.
        # The following check for whether the cleanup has been attached or not is
        # actually unnecessary in our situation, because each call to FT_New_Face
        # will return a new FT Face, but we include it here to show how to handle the
        # general case.
        if _cairo_so.cairo_font_face_get_user_data(cr_face, ct.byref(_ft_destroy_key)) == None :
            status = _cairo_so.cairo_font_face_set_user_data \
              (
                cr_face,
                ct.byref(_ft_destroy_key),
                ft_face,
                _freetype_so.FT_Done_Face
              )
            if status != CAIRO_STATUS_SUCCESS :
                raise RuntimeError("Error %d doing user_data dance for %s" % (status, filename))
            #end if
            ft_face = None # Cairo has stolen my reference
        #end if

        # set Cairo font face into Cairo context
        cairo_ctx = Context(_surface)
        cairo_t = PycairoContext.from_address(id(cairo_ctx)).ctx
        _cairo_so.cairo_set_font_face(cairo_t, cr_face)
        status = _cairo_so.cairo_font_face_status(cairo_t)
        if status != CAIRO_STATUS_SUCCESS :
            raise RuntimeError("Error %d creating cairo font face for %s" % (status, filename))
        #end if

    finally :
        _cairo_so.cairo_font_face_destroy(cr_face)
        _freetype_so.FT_Done_Face(ft_face)
    #end try

    # get back Cairo font face as a Python object
    face = cairo_ctx.get_font_face()
    return face
#end create_cairo_font_face_for_file