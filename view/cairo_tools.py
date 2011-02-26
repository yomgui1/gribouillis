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
from math import floor, ceil, radians, pi, atan, hypot, cos, sin, exp

__all__ = ['LineTool', 'EllipseTool', 'Navigator']

pi2 = pi*2

class SimpleHandler(object):
    x = None
    y = None
    _x = None
    _y = None
    hitpath = None
    
    RADIUS = 12.
    COLOR0 = (.90, .90, 1.0, .8)
    COLOR1 = (0.0, 0.2, .4, .8)

    def _draw_circle(self, cr, off=(0,0)):
        cr.set_line_width(.7)
        self._x = off[0]
        self._y = off[1]
        cr.arc(self.x+self._x, self.y+self._y, self.radius, 0, pi2)
        self.hitpath = cr.copy_path_flat()
        cr.set_source_rgba(*self.COLOR0)
        cr.fill_preserve()
        cr.set_source_rgba(*self.COLOR1)
        cr.stroke()
        return self.hitpath

    def _draw_square(self, cr, off=(0,0)):
        cr.set_line_width(.7)
        r = self.radius
        self._x = off[0]
        self._y = off[1]
        cr.rectangle(self.x+self._x-r, self.y+self._y-r, r*2, r*2)
        del r
        self.hitpath = cr.copy_path_flat()
        cr.set_source_rgba(*self.COLOR0)
        cr.fill_preserve()
        cr.set_source_rgba(*self.COLOR1)
        cr.stroke()
        return self.hitpath

    def __init__(self, x, y, shape='circle', content=None, radius=RADIUS):
        self.x = x
        self.y = y
        self.radius = radius

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
        elif content == 'rot':
            draw = self._draw_rot
        else:
            draw = self._draw_base
            
        self.draw = draw

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

    def _draw_dot(self, cr, **kwds):
        # Shape + controlled point as a thin dot
        cr.set_line_width(2)
        cr.arc(self.x, self.y, 1, 0, pi2)
        cr.set_source_rgba(0,0,0)
        cr.stroke()
        return self._draw_base(cr, **kwds)

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

    def _draw_movey(self, cr, **kwds):
        # Shape + 2 arrows inside
        hp = self._draw_base(cr, **kwds)
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
        return hp

    def _draw_movex(self, cr, **kwds):
        # Shape + 4 arrows inside
        hp = self._draw_base(cr, **kwds)
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


class Tool(object):
    _vp = None
    _cr = None
    _hit = None
    _dash = ((2, 4), 2)
    _enabled = False

    def __init__(self, vp):
        self._vp = vp
        self.hitpaths = []
        self.enable = False

    def _set_enable(self, state):
        self.draw = self._draw if state else self._dummy_draw
        self.ishit = self._ishit if state else self._dummy_ishit
        self._enabled = state

    enable = property(fget=lambda self: self._enabled, fset=_set_enable)

    def _dummy_ishit(self, *a): pass
    def _dummy_draw(self, cr): pass
    def _draw(self, cr): pass

    # TBD by child class
    def compute_data(self): pass

    def _ishit(self, cr, x, y):
        self._hit = None
        for i, path in enumerate(self.hitpaths):
            cr.append_path(path)
            if cr.in_fill(x, y):
                self._hit = i
                return True

    
class LineTool(Tool):
    def __init__(self, *a):
        super(LineTool, self).__init__(*a)
        self.hitpaths = [None]*4

        x = self._vp.vp_size[0]/2.
        y = self._vp.vp_size[1]/2.

        self._middle = SimpleHandler(x, y, content='cross')
        self._square = SimpleHandler(x, y, shape='square', radius=6.5)
        self._handlers = (SimpleHandler(x-100,y+100, content='dot'),
                          SimpleHandler(x+100,y-100, content='dot'))

    def filter(self, state):
        h0, h1 = self._handlers

        xa = state.vpos[0]-h0.x
        ya = state.vpos[1]-h0.y

        xb = h1.x - h0.x
        yb = h1.y - h0.y
        
        g = (xa*xb+ya*yb) / hypot(xb, yb)**2
        
        state.vpos = int(h0.x + xb*g), int(h0.y + yb*g)
        
    def move_handler(self, x, y):
        if self._hit < 2:
            h = self._handlers[self._hit]
            h.move_rel(*h.get_rel(x, y))
        elif self._hit == 3:
            dx, dy = self._square.get_rel(x, y)
            self._handlers[0].move_rel(dx, dy)
            self._handlers[1].move_rel(dx, dy)
        elif self._hit == 2:
            return True

        self.compute_data()

    def compute_data(self):
        h0, h1 = self._handlers
        dx = h1.x - h0.x
        if dx:
            alpha = (h1.y-h0.y) / dx
            if alpha:
                beta = h0.y - alpha*h0.x
                x1 = -beta/alpha
                y1 = 0
                y2 = self._vp.vp_size[1]
                x2 = (y2-beta)/alpha
            else:
                x1 = 0
                x2 = self._vp.vp_size[0]
                y1 = y2 = h0.y
        else:
            y1 = 0
            y2 = self._vp.vp_size[1]
            x1 = x2 = h0.x

        self._line0 = x1, y1
        self._line1 = x2, y2

    def _draw(self, cr):
        # The dashed line
        cr.set_line_width(1.5)
        cr.set_source_rgba(0,0,0,.33)
        dash = cr.get_dash()
        cr.set_dash(*self._dash)
        cr.move_to(*self._line0)
        cr.line_to(*self._line1)
        cr.stroke()
        cr.set_dash(*dash)

        # Handlers
        self.hitpaths[0] = self._handlers[0].draw(cr, off=(16, 16))
        self.hitpaths[1] = self._handlers[1].draw(cr, off=(16, 16))

        x = (self._handlers[0].x + self._handlers[1].x) // 2
        y = (self._handlers[0].y + self._handlers[1].y) // 2

        self._middle.move_to(x, y)
        self._square.move_to(x, y)

        self.hitpaths[2] = self._middle.draw(cr, off=(38, 38))
        self.hitpaths[3] = self._square.draw(cr, off=(12, 12))


class EllipseTool(Tool):
    def __init__(self, *a):
        super(EllipseTool, self).__init__(*a)
        self.hitpaths = [None]*5
        self._angle = 0.0

        x = self._vp.vp_size[0]/2.
        y = self._vp.vp_size[1]/2.

        self._middle = SimpleHandler(x, y, shape='square', radius=6.5)
        self._handlers = (SimpleHandler(x, y-100, content='movey'),
                          SimpleHandler(x-150, y, content='movex'),
                          SimpleHandler(x+150, y, content='rot'),
                          SimpleHandler(x, y+100, content='cross'))
        
    def filter(self, state):
        x,y = state.vpos
        x -= self._middle.x
        y -= self._middle.y

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

        state.vpos = int(self._middle.x + x), int(self._middle.y + y)
        
    def move_handler(self, x, y):
        if self._hit < 3:
            h = self._handlers[self._hit]
            dx, dy = h.get_rel(x, y)
            if self._hit == 0:
                x = h.x - self._middle.x
                y = h.y - self._middle.y
                g = (dx*x+dy*y) / hypot(x, y)**2
                x *= g
                y *= g
                h.move_rel(x, y)

                self._handlers[3].move_to(h.x, h.y)
                self._handlers[3].rotate(self._middle.x, self._middle.y, -1.0, 0.0)
            elif self._hit == 1:
                x = h.x - self._middle.x
                y = h.y - self._middle.y
                g = (dx*x+dy*y) / hypot(x, y)**2
                x *= g
                y *= g
                h.move_rel(x, y)

                self._handlers[2].move_to(h.x, h.y)
                self._handlers[2].rotate(self._middle.x, self._middle.y, -1.0, 0.0)
            elif self._hit == 2:                
                a = self._angle
                self._angle = ViewPort.compute_angle(h.x+dx-self._middle.x, h.y+dy-self._middle.y)
                self._dangle = self._angle - a
                cs = cos(self._dangle)
                sn = sin(self._dangle)
                self._handlers[0].rotate(self._middle.x, self._middle.y, cs, sn)
                self._handlers[1].rotate(self._middle.x, self._middle.y, cs, sn)
                self._handlers[2].rotate(self._middle.x, self._middle.y, cs, sn)
                self._handlers[3].rotate(self._middle.x, self._middle.y, cs, sn)
                
        elif self._hit == 4:
            dx, dy = self._middle.get_rel(x, y)
            self._middle.move_rel(dx, dy)
            self._handlers[0].move_rel(dx, dy)
            self._handlers[1].move_rel(dx, dy)
            self._handlers[2].move_rel(dx, dy)
            self._handlers[3].move_rel(dx, dy)
        elif self._hit == 3:
            return True

        self.compute_data()

    def compute_data(self):
        self._yradius = hypot(self._handlers[0].x-self._middle.x, self._handlers[0].y-self._middle.y)
        self._xradius = hypot(self._handlers[1].x-self._middle.x, self._handlers[1].y-self._middle.y)
        self._cs = cos(self._angle)
        self._sn = sin(self._angle)

    def _draw(self, cr):
        x = self._middle.x
        y = self._middle.y
        
        # The dashed line
        cr.set_line_width(1.5)
        cr.set_source_rgba(0,0,0,.33)
        dash = cr.get_dash()
        cr.set_dash(*self._dash)
        cr.translate(x, y)
        cr.rotate(self._angle)
        cr.scale(self._xradius/self._yradius, 1.0)
        cr.arc(0., 0., self._yradius, 0., pi2)
        cr.identity_matrix()
        cr.stroke()
        cr.set_dash(*dash)

        # Handlers
        h = self._handlers[0]
        dx = h.x - x
        dy = h.y - y
        d = hypot(dx, dy)
        self.hitpaths[0] = h.draw(cr, off=(20*dx/d, 20*dy/d))

        h = self._handlers[1]
        dx = h.x - x
        dy = h.y - y
        d = hypot(dx, dy)
        self.hitpaths[1] = h.draw(cr, off=(20*dx/d, 20*dy/d))
        
        h = self._handlers[2]
        dx = h.x - x
        dy = h.y - y
        d = hypot(dx, dy)
        self.hitpaths[2] = h.draw(cr, off=(20*dx/d, 20*dy/d))

        h = self._handlers[3]
        dx = h.x - x
        dy = h.y - y
        d = hypot(dx, dy)
        self.hitpaths[3] = h.draw(cr, off=(20*dx/d, 20*dy/d))
        
        self.hitpaths[4] = self._middle.draw(cr)


class Navigator(Tool):
    WIDTH = 160
    HEIGHT = 128
    LINE_WIDTH = 2
    
    def __init__(self, *a):
        super(Navigator, self).__init__(*a)

    def compute_data(self):
        w, h = self._vp.vp_size
        self._draw_area = (5, h-1-5-self.HEIGHT, self.WIDTH, self.HEIGHT)
        self._rect_area = (5-self.LINE_WIDTH, h-1-5-self.HEIGHT-self.LINE_WIDTH,
                           self.WIDTH+2*self.LINE_WIDTH, self.HEIGHT+2*self.LINE_WIDTH)

    def _draw(self, cr):
        cr.set_source_rgb(1,0,0) # pure red
        cr.set_line_width(self.LINE_WIDTH)

        cr.rectangle(*self._rect_area)
        cr.stroke()
        
