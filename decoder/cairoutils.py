import json
from os import close, write, unlink, stat
from subprocess import Popen, PIPE
from tempfile import mkstemp

from cairo import PDFSurface, Context
from PIL import Image

from matrixmath import Point as P, Transform

class Point (P):

    def add(self, other):
        return Point(self.x + other.x, self.y + other.y)

class Affine (Transform):

    def __init__(self, a=1, b=0, c=0, d=0, e=1, f=0):
        Transform.__init__(self, a, b, c, d, e, f)

    def __str__(self):
        t = self.terms()
        return f'[{t[0]:.2f}, {t[1]:.2f}, {t[2]:.2f}], [{t[3]:.2f}, {t[4]:.2f}f, {t[5]:.2f}]'

    def terms(self):
        return tuple(self.matrix[0:2,0:3].flat)
    
    def multiply(self, other):
        out = Transform.multiply(self, other)
        return Affine(*tuple(out.matrix[0:2,0:3].flat))

    def translate(self, x, y):
        return Affine(1, 0, x, 0, 1, y).multiply(self)

    def scale(self, x, y):
        return Affine(x, 0, 0, 0, y, 0).multiply(self)

class FakeContext:
    """
    """
    def __init__(self, filename, width, height):
        """
        """
        self.filename = filename
        self.size = width, height

        handle, dummy_file = mkstemp(prefix='cairoutils-', suffix='.pdf')
        close(handle)

        surface = PDFSurface(dummy_file, width, height)
        self.context = Context(surface)

        self.commands = []
        self.garbage = [dummy_file]
        self.page_commands = []

        self.point = Point(0, 0)
        self.stack = [(1, 0, 0, 0, -1, height)]
        self.affine = Affine(*self.stack[0])
    
    def get_current_point(self):
        return self.point.x, self.point.y
    
    def command(self, text, *args):
        self.page_commands.append((text, args))

    def raw_command(self, text):
        self.page_commands.append(('raw', [text]))

    def show_page(self):
        # vertically flip everything because FPDF.
        self.commands.append(('AddPage', []))
        height = self.size[1]
        self.commands.append(('raw', [f'1 0 0 -1 0 {height:.3f} cm']))

        self.commands += self.page_commands
        self.page_commands = []

    def finish(self):
        """
        """
        info = {
            'size': self.size,
            'commands': self.commands,
            'filename': self.filename
          }
        
        page = Popen(['php', 'lossy/page.php'], stdin=PIPE, text=True)
        page.communicate(json.dumps(info), timeout=60)
        page.stdin.close()
        
        for filename in self.garbage:
            unlink(filename)
    
    def translate(self, x, y):
        self.affine = self.affine.translate(x, y)
        self.point = Point(self.point.x + x, self.point.y + y)
        self.raw_command(f'1 0 0 1 {x:.3f} {y:.3f} cm')

    def scale(self, x, y):
        self.affine = self.affine.scale(x, y)
        self.point = Point(self.point.x * x, self.point.y * y)
        self.raw_command(f'{x:.6f} 0 0 {y:.6f} 0 0 cm')

    def save(self):
        self.stack.append(self.affine.terms())
        self.raw_command('q')

    def restore(self):
        self.affine = Affine(*self.stack.pop())
        self.raw_command('Q')

    def user_to_device(self, x, y):
        user = Point(x, y)
        device = self.affine(user)
        return (device.x, device.y)

    def device_to_user(self, x, y):
        device = Point(x, y)
        user = self.affine.inverse()(device)
        return (user.x, user.y)

    def move_to(self, x, y):
        self.point = Point(x, y)
        self.raw_command(f'{x:.3f} {y:.3f} m')

    def line_to(self, x, y):
        self.point = Point(x, y)
        self.raw_command(f'{x:.3f} {y:.3f} l')

    def rel_move_to(self, x, y):
        end = Point(x, y).add(self.point)
        self.point = end
        self.raw_command(f'{end.x:.3f} {end.y:.3f} m')

    def rel_line_to(self, x, y):
        end = Point(x, y).add(self.point)
        self.point = end
        self.raw_command(f'{end.x:.3f} {end.y:.3f} l')

    def set_source_rgb(self, r, g, b):
        self.raw_command(f'{r:.3f} {g:.3f} {b:.3f} rg')

    def fill(self):
        self.raw_command('f')

    def set_source_surface(self, surf, x, y):
        """
        """
        dim = surf.get_width(), surf.get_height()
        img = Image.frombytes('RGBA', dim, surf.get_data().tobytes())
        
        # weird channel order
        blue, green, red, alpha = img.split()
        img = Image.merge('RGB', (red, green, blue))

        png_handle, png_filename = mkstemp(prefix='cairoutils-', suffix='.png')
        img.save(png_filename, 'PNG')
        
        jpg_handle, jpg_filename = mkstemp(prefix='cairoutils-', suffix='.jpg')
        img.save(jpg_filename, 'JPEG', quality=75)
        
        if stat(jpg_filename).st_size < stat(png_filename).st_size:
            method, handle, filename = 'raw_jpeg', jpg_handle, jpg_filename
        else:
            method, handle, filename = 'raw_png', png_handle, png_filename
        
        self.command(method, filename)
        self.garbage.append(filename)

        close(handle)

    def paint(self):
        pass

    def set_line_width(self, w):
        self.raw_command(f'{w:.3f} w')

    def set_dash(self, a):
        a = ' '.join([f'{v:.3f}' for v in a])
        self.raw_command(f'[{a}] 0 d')

    def stroke(self):
        self.raw_command('S')

    def rel_curve_to(self, a, b, c, d, e, f):
        p1 = Point(a, b).add(self.point)
        p2 = Point(c, d).add(self.point)
        p3 = Point(e, f).add(self.point)
        self.point = p3
        self.raw_command(f'{p1.x:.3f} {p1.y:.3f} {p2.x:.3f} {p2.y:.3f} {p3.x:.3f} {p3.y:.3f} c')

    def set_font_face(self, font):
        self.context.set_font_face(font)

    def set_font_size(self, size):
        self.context.set_font_size(size)
        
        # SetFont here because only the size gives a clue to the correct weight
        self.command('SetFont', 'Helvetica', (size > 14) and 'B' or '')
        self.command('SetFontSize', size)

    def show_text(self, text):
        # invert the vertical flip in self.show_page() before showing text.
        x, y = self.point.x, -self.point.y

        self.raw_command(f'q 1 0 0 -1 0 0 cm BT {x:.3f} {y:.3f} Td ({text}) Tj ET Q')

    def text_extents(self, text):
        #https://pycairo.readthedocs.io/en/latest/reference/textextents.html#cairo.TextExtents
        return self.context.text_extents(text)

def get_drawing_context(print_filename, page_width_pt, page_height_pt):
    """
    """
    context = FakeContext(print_filename, page_width_pt, page_height_pt)
    
    return context, context.finish
