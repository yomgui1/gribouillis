###############################################################################
# Copyright (c) 2009-2011 Guillaume Roguez
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
###############################################################################

import cairo

from math import floor, ceil, radians, pi, atan, hypot, cos, sin, exp, degrees

import utils

from model import _pixbuf, prefs
from view.viewport import ViewPortBase

compute_angle = ViewPortBase.compute_angle
del ViewPortBase

pi2 = pi*2
IECODE_LBUTTON = 0x68

def compute_angle(x, y):
    # (x,y) in view coordinates

    if y >= 0:
        r = 0.
    else:
        r = pi
        y = -y
        x = -x

    if x > 0:
        r += atan(float(y)/x)
    elif x < 0:
        r += pi - atan(float(y)/-x)
    else:
        r += pi/2.

    return r

def rotate(xo, yo, cs, sn):
    x = self.x - xo
    y = self.y - yo
    self.x = xo + x*cs - y*sn
    self.y = yo + y*cs + x*sn


class Cursor:
    _r = None
    _scale = 1.0
    _debug = 0
    _cache = None
    
    def __init__(self):
        self.set_radius(10.)
        
    def set_radius(self, r):
        r = max(1., min(r, 20.))
        if r == self._r:
            return
        self._r = r
        self._resize()
        
    def _resize(self):
        # Width must always be an odd number to be center correctly
        w = int(2*ceil((self._r * self._scale) + 1.5)) + 1 + 2 # +2 for the antialiasing, +1.5 for the white circle
        self.width = self.height = w
        self._off = w / 2.
        self._cache = None
        
    def set_scale(self, s):
        s = max(0.001, s)
        if s != self._scale:
            self._scale = s
            self._resize()
        
    def render(self):
        if self._debug:
            self._cache = None
            
        if not self._cache:
            r = self._r * self._scale
            self._buf = _pixbuf.Pixbuf(_pixbuf.FORMAT_ARGB8, self.width, self.height)
            self._buf.clear()
            self._cache = cairo.ImageSurface.create_for_data(self._buf, cairo.FORMAT_ARGB32, self.width, self.height)
            self.stride = self._cache.get_stride()
            cr = cairo.Context(self._cache)
            cr.translate(self._off, self._off)
            
            if self._debug:
                cr.set_line_width(1)
                cr.set_source_rgb(0,0,0)
                cr.paint()
                cr.set_source_rgb(1,0,0)
                cr.move_to(0,-self.height/2.)
                cr.rel_line_to(0,self.height)
                cr.stroke()
                cr.move_to(-self.width/2.,0)
                cr.rel_line_to(self.width,0)
                cr.stroke()
            
            cr.set_line_width(1.5)
            
            # Drawing 2 concentric circles: one black, one white (but not pure)
            cr.arc(0, 0, r, 0, pi2)
            cr.set_source_rgb(0.03,0.03,0.03)
            cr.stroke()
            cr.arc(0, 0, r+1.5, 0, pi2)
            cr.set_source_rgb(0.97, 0.97, 0.97)
            cr.stroke()

    @property
    def cairo_surface(self):
        return self._cache
        
    @property
    def pixbuf(self):
        return self._buf
        
    @property
    def radius(self):
        return self._off

class Tool(object):
    _dash1 = ((4, 10), 2)
    _dash2 = ((4, 3), 2)
    _area = None
    _handlers = []
    added = False
    
    def hit(self, cr, *pos): pass
    def repaint(self, vp, cr, w, h): pass
    def reset(self): pass

    @property
    def area(self): return self._area

    def hit_handler(self, cr, x, y):
        for hl in self._handlers:
            cr.new_path()
            cr.append_path(hl.hitpath)
            if cr.in_fill(x, y):
                return hl

class Text(Tool):
    _text = ''
    
    def set_text(self, text):
        self._text = text.decode('latin-1')

    def repaint(self, vp, cr, width, height):
        # Compute text size
        cr.select_font_face ("monospace", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(15)
        te = cr.text_extents(self._text)
        w = (int(te[2]) & ~7) + 28 # text width + border
        h = 32

        x = (width-w)/2
        y = height-h-16
        self._area = x,y,w,h
        cr.rectangle(x,y,w-1,h-1)
        cr.clip_preserve()

        # Background
        cr.set_source_rgba(*prefs['view-color-bg'])
        cr.paint()

        # Frame
        cr.set_line_width(1)
        cr.set_source_rgba(*prefs['view-color-ol'])
        cr.stroke()

        # Text
        cr.translate(x, y)
        cr.move_to(w*.5 - te[0] - te[2]*.5, h*.5 - te[1] - te[3]*.5)
        cr.set_source_rgba(*prefs['view-color-text'])
        cr.show_text(self._text)
        cr.stroke()

class Rotate(Tool):
    dr = None
    _pos = None
    _ox = None
    _oy = None

    def set_cursor_pos(self, pos):
        if self._ox and self._pos:
            x, y = self._pos
            a = compute_angle(x-self._ox, y-self._oy)
            self.dr = a-compute_angle(pos[0]-self._ox, pos[1]-self._oy)
        self._pos = pos

    def repaint(self, vp, cr, width, height):
        self._ox = width/2.
        self._oy = height/2.
        cr.translate(self._ox, self._oy)

        # Draw a background filled circle
        cr.set_line_width(1)
        cr.set_source_rgba(*prefs['view-color-bg'])
        cr.arc(0, 0, 16, 0, pi2)
        cr.fill_preserve()
        
        # Then its outline
        cr.set_source_rgba(*prefs['view-color-ol'])
        cr.stroke()

        # And a little cross inside
        cr.move_to(-6, 0)
        cr.line_to(6, 0)
        cr.stroke()

        cr.move_to(0, -6)
        cr.line_to(0, 6)
        cr.stroke()
        
class SelectionDisplay(Tool):
    _path = []
    _surf = None
    _mat = cairo.Matrix()

    def set_position(self, x, y):
        self._x = x
        self._y = y

    def move(self, dx, dy):
        self._x += dx
        self._y += dy
        x,y,w,h = self._area
        self._area = (x+dx,y+dy,w,h)

    def set_selection(self, buf, path):
        self._x, self._y = path[0]
        self._surf = cairo.ImageSurface.create_for_data(buf, cairo.FORMAT_ARGB32,
                                                        buf.width, buf.height, buf.stride)
        self._path = path

    def set_path(self, path):
        self._x = self._y = 0.
        self._path = path

    def reset(self):
        self._x = self._y = 0.
        self._path = None
        self._area = None
        
    def repaint(self, vp, cr, width, height):
        if not self._path: return
        
        cr.save()

        if self._surf:
            cr.set_source_surface(self._surf, vp.get_view_point(self._x, self._y))
            cr.paint()

        # Build outlines
        dash = cr.get_dash()
        cr.set_dash(*self._dash)
        cr.set_source_rgb(0,0,0)
        cr.set_line_width(1)
        cr.new_path()
        cr.translate(self._x, self._y)
        m = cr.get_matrix()
        m2 = m.multiply(self._mat)
        cr.set_matrix(m2)
        for pos in self._path:
            cr.line_to(*vp.get_view_point(*pos))
        cr.close_path()
        cr.set_matrix(m)
        cr.translate(-self._x, -self._y)

        # Compute the dirty area
        x1,y1,x2,y2 = cr.path_extents()
        self._area = int(floor(x1)), int(floor(y1)), int(ceil(x2-x1))+2, int(ceil(y2-y1))+2

        # Stroke outlines
        cr.stroke()
        cr.set_dash(*dash)
        
        cr.restore()
        
class DrawFreeSelection(Tool):
    _cpos = []
    _spos = []
    
    def add_pt(self, state):
        pos = state.cpos
        self._cpos.append(pos)
        self._spos.append(state.spos)

    def reset(self):
        self._cpos = []
        self._spos = []
        self._area = None
        
    def repaint(self, vp, cr, width, height):
        if not self._cpos: return
        cr.new_path()
        cr.set_source_rgb(0,0,0)
        cr.set_line_width(1)
        dash = cr.get_dash()
        cr.set_dash(*self._dash)
        for pos in self._cpos:
            cr.line_to(*pos)
        cr.close_path()
        x1,y1,x2,y2 = cr.path_extents()
        
        # limit the next redraw
        self._area = int(floor(x1)), int(floor(y1)), int(ceil(x2-x1))+1, int(ceil(y2-y1))+1
        
        cr.stroke()
        cr.set_dash(*dash)

    @property
    def path(self):
        return tuple(self._spos)

class ToolsWheel(Tool):
    cpos = None
    _bg_img = None
    _paths = None
    _icons = []
    selection = -1

    ALIASING_PADDING = 3
    SIZE = 174
    CENTER = SIZE / 2.
    LINE_WIDTH = 3
    BIG_RADIUS = CENTER - (LINE_WIDTH + ALIASING_PADDING) / 2.
    LITTLE_RADIUS = BIG_RADIUS - 46
    ICON_SIZE = 32
    ICON_RADIUS = ICON_SIZE / 2.

    def _draw_background(self):
        if self._bg_img:
            return self._bg_img
        
        self._bg_img = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.SIZE, self.SIZE)
        cr = cairo.Context(self._bg_img)
        
        cr.set_line_width(1)
        cr.translate(self.CENTER, self.CENTER)

        # Background
        cr.set_antialias(cairo.ANTIALIAS_NONE)
        cr.set_source_rgba(*prefs['view-color-wheel-bg'])
        cr.arc(0, 0, self.BIG_RADIUS, 0, pi2)
        cr.fill_preserve()
        
        # Outline
        cr.set_line_width(self.LINE_WIDTH)
        cr.set_antialias(cairo.ANTIALIAS_DEFAULT)
        cr.set_source_rgba(*prefs['view-color-wheel-ol'])
        cr.stroke()
        
        # Separators
        cr.set_line_width(self.LINE_WIDTH*.6)
        a = pi / 8
        for i in range(0, 8):
            x = round(self.BIG_RADIUS * sin(a))
            y = round(self.BIG_RADIUS * -cos(a))
            cr.move_to(x, y)
            cr.line_to(-x, -y)
            cr.stroke()
            a += i * pi / 4

        # Inner hole
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_antialias(cairo.ANTIALIAS_NONE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.arc(0, 0, self.LITTLE_RADIUS, 0, pi2)
        cr.fill_preserve()
        
        # Inline
        cr.set_line_width(self.LINE_WIDTH)
        cr.set_antialias(cairo.ANTIALIAS_DEFAULT)
        cr.set_source_rgba(*prefs['view-color-wheel-ol'])
        cr.stroke()

        return self._bg_img

    def _draw(self, cr):
        # Background (without icons)
        bg = self._draw_background()
        cr.set_source_surface(bg, 0, 0)
        cr.paint()
        
        cr.translate(self.CENTER, self.CENTER)
        
        # Draw icons
        r = self.LITTLE_RADIUS + (self.BIG_RADIUS - self.LITTLE_RADIUS) / 2.
        self._paths = []
                
        a = 0.0
        b = -pi / 8
        for i in range(0, 8):
            x = round(r * cos(a))
            y = round(r * sin(a))
            
            # Path
            cr.set_antialias(cairo.ANTIALIAS_NONE)
            cr.new_path()
            cr.arc(0, 0, self.BIG_RADIUS, b, b+pi/4)
            cr.arc_negative(0, 0, self.LITTLE_RADIUS, b+pi/4, b)
            cr.close_path()
            self._paths.append(cr.copy_path_flat())
            cr.new_path()
            
            # Icons layer (optional)
            cr.save()
            if self.selection == i:
                im = self._icons[i+8]
            else:
                im = self._icons[i]
            cr.translate(x - self.ICON_RADIUS, y - self.ICON_RADIUS)
            cr.scale(32./im.get_width(), 32./im.get_height())
            cr.set_source_surface(im, 0, 0)
            cr.paint()
            cr.restore()
            
            a += pi / 4
            b += pi / 4
            i += 1
                        
    def _hit_path(self, cr, x, y):
        for i, path in enumerate(self._paths):
            cr.new_path()
            cr.append_path(path)
            if cr.in_fill(x, y):
                self.selection = i
                return i
        self.selection = -1
        return -1
        
    def hit(self, cr, x, y):
        x -= self._area[0] + self.CENTER
        y -= self._area[1] + self.CENTER
        return self._hit_path(cr, x, y) >= 0
        
    def set_center(self, pos):
        self.cpos = None
        self.selection = None
        cx, cy = pos
        d = self.SIZE
        self._area = (cx-d/2, cy-d/2, d, d)

    def set_icons(self, icons):
        assert len(icons) >= 8
        self._icons = icons

    def repaint(self, vp, cr, width, height):
        cr.rectangle(*self._area)
        cr.clip()
        
        ox = self._area[0]
        oy = self._area[1]
        cr.translate(ox, oy)
        
        self._draw(cr)
        
class ColorWheel(Tool):
    cpos = None
    _bg_img = None
    _fg_img = None
    _paths = None
    _icons = []
    selection = -1
    
    ALIASING_PADDING = 3
    SIZE = 174
    CENTER = SIZE / 2.
    LINE_WIDTH = 3
    BIG_RADIUS = CENTER - (LINE_WIDTH + ALIASING_PADDING) / 2.
    LITTLE_RADIUS = BIG_RADIUS - 46
    ICON_SIZE = 32
    ICON_RADIUS = ICON_SIZE / 2.

    def _draw_background(self):
        if self._bg_img:
            return self._bg_img
        
        self._bg_img = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.SIZE, self.SIZE)
        cr = cairo.Context(self._bg_img)
        
        cr.set_line_width(1)
        cr.set_antialias(cairo.ANTIALIAS_NONE)
        cr.translate(self.CENTER, self.CENTER)

        # Background
        cr.set_source_rgba(*prefs['view-color-wheel-bg'])
        cr.arc(0, 0, self.BIG_RADIUS, 0, pi2)
        cr.fill()

        # Inner hole
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.arc(0, 0, self.LITTLE_RADIUS, 0, pi2)
        cr.fill()

        return self._bg_img
        
    def _draw_foreground(self):
        if self._fg_img:
            return self._fg_img
        
        self._fg_img = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.SIZE, self.SIZE)
        cr = cairo.Context(self._fg_img)
        
        cr.set_line_width(self.LINE_WIDTH)
        cr.translate(self.CENTER, self.CENTER)

        # Outline
        cr.set_source_rgba(*prefs['view-color-wheel-ol'])
        cr.arc(0, 0, self.BIG_RADIUS, 0, pi2)
        cr.stroke()
        
        # Separators
        cr.set_line_width(self.LINE_WIDTH*.6)
        a = pi / 8
        for i in range(0, 8):
            x = round(self.BIG_RADIUS * sin(a))
            y = round(self.BIG_RADIUS * -cos(a))
            cr.move_to(x, y)
            cr.line_to(-x, -y)
            cr.stroke()
            a += i * pi / 4
        
        # Inner hole
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.arc(0, 0, self.LITTLE_RADIUS, 0, pi2)
        cr.fill()
        
        # Inline
        cr.set_line_width(self.LINE_WIDTH)
        cr.set_antialias(cairo.ANTIALIAS_DEFAULT)
        cr.set_source_rgba(*prefs['view-color-wheel-ol'])
        cr.arc(0, 0, self.LITTLE_RADIUS, 0, pi2)
        cr.stroke()

        return self._fg_img

    def _draw(self, cr):
        # Background
        bg = self._draw_background()
        cr.set_source_surface(bg, 0, 0)
        cr.paint()
        
        # Draw colors
        cr.save()
        cr.translate(self.CENTER, self.CENTER)
        cr.set_line_width(self.LINE_WIDTH)
        
        r = self.LITTLE_RADIUS + (self.BIG_RADIUS - self.LITTLE_RADIUS) / 2.
        self._paths = []
                
        a = -pi/2 - pi/8
        for i in range(0, 8):
            # Path
            cr.new_path()
            cr.arc(0, 0, self.BIG_RADIUS, a, a+pi/4)
            cr.arc_negative(0, 0, self.LITTLE_RADIUS, a+pi/4, a)
            cr.close_path()
            self._paths.append(cr.copy_path_flat())
            
            c = self._colors[i]
            if c:
                cr.set_source_rgb(*c)
                cr.fill_preserve()
            
            a += pi / 4
            i += 1
            
        cr.restore()
            
        # Foreground
        fg = self._draw_foreground()
        cr.set_source_surface(fg, 0, 0)
        cr.paint()
        
        if self.selection >= 0:
            cr.translate(self.CENTER, self.CENTER)
            cr.new_path()
            cr.append_path(self._paths[self.selection])
            cr.set_source_rgba(*prefs['view-color-wheel-sel'])
            cr.stroke()
                        
    def _hit_path(self, cr, x, y):
        for i, path in enumerate(self._paths):
            if not self._colors[i]:
                continue
            cr.new_path()
            cr.append_path(path)
            if cr.in_fill(x, y):
                self.selection = i
                return i
        self.selection = -1
        return -1
        
    def hit(self, cr, x, y):
        x -= self._area[0] + self.CENTER
        y -= self._area[1] + self.CENTER
        return self._hit_path(cr, x, y) >= 0
        
    def set_center(self, pos):
        self.cpos = None
        self.selection = None
        cx, cy = pos
        d = self.SIZE
        self._area = (cx-d/2, cy-d/2, d, d)

    def set_colors(self, colors):
        assert len(colors) == 8
        self._colors = colors

    def repaint(self, vp, cr, width, height):
        cr.rectangle(*self._area)
        cr.clip()
        
        ox = self._area[0]
        oy = self._area[1]
        cr.translate(ox, oy)
        
        self._draw(cr)
        
class Handler(object):
    # Hook point
    x = None
    y = None
    
    hitpath = None
    kill = False
    
    RADIUS = 12.

    def __init__(self, tool, position, shape='circle', content=None, radius=RADIUS, drawdot=False):
        self.tool = tool
        self.x, self.y = position
        self.radius = radius
        self._dot = drawdot

        if shape == 'square':
            self._draw_base = self._draw_square
        else:
            self._draw_base = self._draw_circle
            
        if content == 'cross':
            draw = self._draw_cross
        elif content == 'dot':
            draw = self._draw_dot
        elif content == 'movey':
            draw = self._draw_movey
        elif content == 'movex':
            draw = self._draw_movex
        elif content == 'move':
            draw = self._draw_move
        elif content == 'rot':
            draw = self._draw_rot
        else:
            draw = self._draw_base
            
        self.draw = draw
        
    def _draw_circle(self, cr, off=(0,0)):
        if self._dot:
            cr.set_line_width(2)
            cr.arc(self.x+.5, self.y+.5, 1, 0, pi2)
            cr.set_source_rgb(1,1,1)
            cr.stroke()
            cr.arc(self.x-.5, self.y-.5, 1, 0, pi2)
            cr.set_source_rgb(0,0,0)
            cr.stroke()
        cr.set_line_width(.7)
        self._x = off[0]
        self._y = off[1]
        cr.arc(self.x+self._x, self.y+self._y, self.radius, 0, pi2)
        self.hitpath = cr.copy_path_flat()
        cr.set_source_rgba(*prefs['view-color-handler-bg'])
        cr.fill_preserve()
        cr.set_source_rgba(*prefs['view-color-handler-ol'])
        cr.stroke()
        d = int((self.radius+1)*2) # take car of antialiasing thinkness
        self.area = (int(self.x+off[0]-self.radius-1), int(self.y+off[1]-self.radius-1), d, d)
        if self._dot:
            self.area = utils.join_area(self.area, [int(self.x-3), int(self.y-3), 6, 6])
        return self.hitpath

    def _draw_square(self, cr, off=(0,0)):
        cr.set_line_width(.7)
        r = self.radius
        self._x = off[0]
        self._y = off[1]
        cr.rectangle(self.x+self._x-r, self.y+self._y-r, r*2, r*2)
        del r
        self.hitpath = cr.copy_path_flat()
        cr.set_source_rgba(*prefs['view-color-handler-bg'])
        cr.fill_preserve()
        cr.set_source_rgba(*prefs['view-color-handler-ol'])
        cr.stroke()
        d = int((self.radius+2)*2)
        self.area = (int(self.x-self.radius-2), int(self.y-self.radius-2), d, d)
        return self.hitpath

    def _draw_dot(self, cr, **kwds):
        # Shape + centered dot
        hp = self._draw_base(cr, **kwds)
        cr.set_line_width(2)
        cr.arc(self.x+self._x, self.y+self._y, 1, 0, pi2)
        cr.stroke()
        return hp

    def _draw_cross(self, cr, **kwds):
        # Shape + cross inside
        hp = self._draw_base(cr, **kwds)
        r = self.radius * .4
        x = self.x + self._x - r
        y = self.y + self._y - r
        r *= 2
        cr.move_to(x, y)
        cr.rel_line_to(r, r)
        cr.stroke()
        cr.move_to(x, y + r)
        cr.rel_line_to(r, -r)
        cr.stroke()
        return hp

    def __draw_movey(self, cr):
        r = self.radius * .7
        r2 = self.radius * .2
        x = self.x + self._x - r2
        y = self.y + self._y - r
        cr.move_to(x, y+r2)
        cr.rel_line_to(r2, -r2)
        cr.rel_line_to(r2, r2)
        cr.stroke()
        y = self.y + self._y + r
        cr.move_to(x, y-r2)
        cr.rel_line_to(r2, r2)
        cr.rel_line_to(r2, -r2)
        cr.stroke()
        
    def __draw_movex(self, cr):
        r = self.radius * .7
        r2 = self.radius * .2
        x = self.x + self._x - r
        y = self.y + self._y - r2
        cr.move_to(x+r2, y)
        cr.rel_line_to(-r2, r2)
        cr.rel_line_to(r2, r2)
        cr.stroke()
        x = self.x + self._x + r
        cr.move_to(x-r2, y)
        cr.rel_line_to(r2, r2)
        cr.rel_line_to(-r2, r2)
        cr.stroke()
        
    def _draw_movey(self, cr, **kwds):
        # Shape + 2 arrows inside
        hp = self._draw_base(cr, **kwds)
        self.__draw_movey(cr)
        return hp

    def _draw_movex(self, cr, **kwds):
        # Shape + 2 arrows inside
        hp = self._draw_base(cr, **kwds)
        self.__draw_movex(cr)
        return hp
        
    def _draw_move(self, cr, **kwds):
        # Shape + 4 arrows inside
        hp = self._draw_base(cr, **kwds)
        self.__draw_movex(cr)
        self.__draw_movey(cr)
        return hp

    def _draw_rot(self, cr, **kwds):
        # Shape + 2 arc arrows inside
        hp = self._draw_base(cr, **kwds)
        r = self.radius * .55
        r2 = self.radius * .25
        x = self.x + self._x
        y = self.y + self._y
        cr.arc(x, y, r, pi, -pi/2)
        cr.rel_move_to(-r2*.2, -r2)
        cr.rel_line_to(r2, r2)
        cr.rel_line_to(-r2, r2)
        cr.stroke()
        cr.arc(x, y, r, 0, pi/2)
        cr.rel_move_to(r2*.2, -r2)
        cr.rel_line_to(-r2, r2)
        cr.rel_line_to(r2, r2)
        cr.stroke()
        return hp
            
    def move_to(self, x, y):
        self.x = float(x)
        self.y = float(y)

    def move_rel(self, dx, dy):
        self.x += dx
        self.y += dy

    def get_rel(self, x, y):
        return x - self.x - self._x, y - self.y - self._x

    def rotate(self, xo, yo, cs, sn):
        x = self.x - xo
        y = self.y - yo
        self.x = xo + x*cs - y*sn
        self.y = yo + y*cs + x*sn

class LineGuide(Tool):
    def __init__(self, x, y):
        self._move = Handler(self, (x, y), content='move', drawdot=True)
        self._dot = Handler(self, (x-200, y+150), content='dot', drawdot=True)
        self._cross = Handler(self, (x-200, y+110), content='cross', radius=8)
        self._cross.kill = True
        self._handlers = (self._dot, self._move, self._cross)
        
    def repaint(self, vp, cr, width, height):
        # The guide line
        cr.set_line_width(1.5)
        dash = cr.get_dash()
        cr.set_dash(*self._dash1)
        cr.move_to(self._move.x, self._move.y)
        cr.line_to(self._dot.x, self._dot.y)
        cr.set_source_rgba(0, 0, 0, .66)
        cr.stroke_preserve()
        cr.set_dash(*self._dash2)
        cr.set_source_rgba(1, 1, 1, .66)
        cr.stroke()
        cr.set_dash(*dash)
        
        # Handlers
        self._cross.draw(cr)
        self._move.draw(cr, off=(16, 16))
        self._area = utils.join_area(self._cross.area, self._move.area)
        self._dot.draw(cr, off=(16,16))
        self._area = utils.join_area(self._area, self._dot.area)

    def move_handler(self, hl, *pos):
        delta = hl.get_rel(*pos)
        if hl == self._move:
            # Global move
            for hl in self._handlers:
                hl.move_rel(*delta)
        elif hl == self._dot:
            hl.move_rel(*delta)
            self._cross.move_rel(*delta)

    def filter(self, state):
        h0 = self._move
        h1 = self._dot
        
        xa = state.vpos[0] - h0.x
        ya = state.vpos[1] - h0.y

        xb = h1.x - h0.x
        yb = h1.y - h0.y
        
        g = (xa*xb+ya*yb) / hypot(xb, yb)**2
        
        state.vpos = int(h0.x + xb*g), int(h0.y + yb*g)

class EllipseGuide(Tool):
    _angle = 0.0
    
    def __init__(self, x, y):
        self._move = Handler(self, (x, y), shape='square', content='move', radius=8)
        self._movey = Handler(self, (x, y-100), content='movey', drawdot=True)
        self._movex = Handler(self, (x-150, y), content='movex', drawdot=True)
        self._rot = Handler(self, (x+150, y), content='rot', drawdot=True)
        self._cross = Handler(self, (x+25, y-25), content='cross', radius=8)
        self._cross.kill = True
        self._handlers = (self._rot, self._movex, self._movey, self._move, self._cross)
        self._compute_data()
        
    def hit_handler(self, cr, x, y):
        for hl in self._handlers:
            cr.new_path()
            cr.append_path(hl.hitpath)
            if cr.in_fill(x, y):
                return hl
        
    def _compute_data(self):
        self._xradius = hypot(self._movex.x - self._move.x, self._movex.y - self._move.y)
        self._yradius = hypot(self._movey.x - self._move.x, self._movey.y - self._move.y)
        self._cs = cos(self._angle)
        self._sn = sin(self._angle)
        
    def repaint(self, vp, cr, width, height):
        # The guide ellipse
        cr.set_line_width(1.5)
        dash = cr.get_dash()
        cr.set_dash(*self._dash1)
        cr.translate(self._move.x, self._move.y)
        cr.rotate(self._angle)
        cr.scale(self._xradius/self._yradius, 1.0)
        cr.arc(0., 0., self._yradius, 0., pi2)
        cr.identity_matrix()
        x1, y1, x2, y2 = cr.path_extents()
        self._area = [ int(x1-36), int(y1-36), int(x2-x1+72), int(y2-y1+72) ] # Approximative dirty area
        del x1, x2, y1, y2
        cr.set_source_rgba(0, 0, 0, .66)
        cr.stroke_preserve()
        cr.set_dash(*self._dash2)
        cr.set_source_rgba(1, 1, 1, .66)
        cr.stroke()
        cr.set_dash(*dash)

        # Handlers (reverse priority)
        self._cross.draw(cr)
        self._move.draw(cr)
        self._movex.draw(cr, off=(-20, 0))
        self._movey.draw(cr, off=(0, -20))
        self._rot.draw(cr, off=(20, 0))

    def move_handler(self, hl, *pos):
        delta = hl.get_rel(*pos)
        if hl == self._move:
            # Global move
            for hl in self._handlers:
                hl.move_rel(*delta)
        elif hl == self._movex:
            # take care of current rotation
            x = hl.x - self._move.x
            y = hl.y - self._move.y
            g = (delta[0]*x + delta[1]*y) / hypot(x, y)**2
            x *= g
            y *= g
            hl.move_rel(x, y)
            self._rot.move_rel(-x, -y)
            self._compute_data()
        elif hl == self._movey:
            # take care of current rotation
            x = hl.x - self._move.x
            y = hl.y - self._move.y
            g = (delta[0]*x + delta[1]*y) / hypot(x, y)**2
            x *= g
            y *= g
            hl.move_rel(x, y)
            self._compute_data()
        elif hl == self._rot:
            mhx = self._move.x
            mhy = self._move.y
            a = self._angle
            self._angle = compute_angle(hl.x+delta[0]-mhx, hl.y+delta[1]-mhy)
            a = self._angle - a
            cs = cos(a)
            sn = sin(a)
            self._rot.rotate(mhx, mhy, cs, sn)
            self._movex.rotate(mhx, mhy, cs, sn)
            self._movey.rotate(mhx, mhy, cs, sn)
            self._compute_data()

    def filter(self, state):
        x,y = state.vpos
        x -= self._move.x
        y -= self._move.y
        if not (x or y):
            return

        cs = self._cs
        sn = self._sn
        
        x2 = x*cs + y*sn
        y2 = y*cs - x*sn
        
        n = self._xradius*self._yradius
        n /= hypot(self._yradius*x2, self._xradius*y2)

        x2 *= n
        y2 *= n

        x = x2*cs - y2*sn
        y = y2*cs + x2*sn

        state.vpos = int(self._move.x + x), int(self._move.y + y)
        
