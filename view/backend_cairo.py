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
import random
import math

from math import floor, ceil, radians, pi, atan, hypot, cos, sin, exp
from time import time

from model import _pixbuf
from cairo_tools import *

from .viewport import BackgroundMixin

pi2 = pi*2

def get_imat(m):
    m = m * cairo.Matrix()
    m.invert()
    return m


class SimpleViewPort(BackgroundMixin):
    """USed only to draw strokes, without cursor display and
    no dynamic model matrix modifications.
    """
    
    _model_context = None
    _model_surface = None

    _cr = None
    _model_mat = cairo.Matrix()
    _model_imat = get_imat(_model_mat)

    _width = None
    _height = None

    _repaint_model = True

    def repaint(self, cr, layers, area, width, height):
        newsize = self.init_cairo_context(cr, width, height)

        ## Need to regenerate model surface?
        if self._repaint_model or newsize:
            self.draw_model(layers, area)
            self._repaint_model = False

        ## Paint cached surfaces on the destination context
        # Clip on the requested area
        cr.rectangle(*area)
        cr.clip()

        # Paint all drawing surfaces
        self.paint_model()
        
        return area

    def set_repaint(self, model):
        self._repaint_model |= model

    def init_cairo_context(self, cr, w, h):
        self._cr = cr
        if self._width != w or self._height != h:
            self._width = w
            self._height = h

            # Drawing caches
            self._model_surface = cairo.ImageSurface(cairo.FORMAT_RGB24, w, h)
            self._model_context = cairo.Context(self._model_surface)
            
            return True

    def draw_model(self, layers, area):
        cr = self._model_context
        cr.save()

        # Clip on the requested area
        cr.rectangle(*area)
        cr.clip()

        # Set model affines transformations
        cr.set_matrix(self._model_mat)

        # Paint background
        if self._backcolor:
            cr.set_source_rgb(*self._backcolor)
        else:
            cr.set_source(self._backpat)
        cr.paint()

        # Convert the area given into viewport coordinates
        # into model coordinates, by installing a clip.
        x,y,w,h = cr.clip_extents()
        x = int(floor(x)-1)
        y = int(floor(y)-1)
        w = int(ceil(w)+1) - x + 1
        h = int(ceil(h)+1) - y + 1
        area = (x,y,w,h)
        
        rbuf = _pixbuf.Pixbuf(_pixbuf.FORMAT_ARGB8, w, h)
        rsurf = cairo.ImageSurface.create_for_data(rbuf, cairo.FORMAT_ARGB32, w, h)
        
        for layer in layers:
            rbuf.clear()
            
            # Blit layer's tiles using over ope mode on the render surface
            def cb(tile):
                tile.blit(rbuf, tile.x-x, tile.y-y)
                          
            layer.surface.rasterize(area, cb)
            rsurf.mark_dirty()
            
            # Now paint this rendered layer surface on the model surface
            cr.set_source_surface(rsurf, x, y)
            cr.paint()

    def paint_model(self):
        cr = self._cr
        cr.set_source_surface(self._model_surface, 0, 0)
        cr.paint()

    def get_model_point(self, *a):
        return self._model_imat.transform_point(*a)

    def get_model_distance(self, *a):
        return self._model_imat.transform_distance(*a)

    def get_view_point(self, *a):
        return self._model_mat.transform_point(*a)

    def get_view_distance(self, *a):
        return self._model_mat.transform_distance(*a)

    def get_view_area(self, x, y, w, h):
        w, h = self._model_mat.transform_distance(w,h)
        return self._model_mat.transform_point(x,y) + (ceil(w), ceil(h))

    def compute_motion(self, device):
        if device.previous:
            os = device.previous
            ns = device.current
            return ns.x-os.x, ns.y-os.y
        return 0., 0.

    @property
    def vp_size(self):
        return self._width, self._height

class ViewPort:
    _tools = None

    # View context
    _cr = None
    _mat_model2view = None
    _mat_view2model= None

    # Current cursor position in device space
    __x = .0
    __y = .0
    __r = .0
    __old_area = __cur_area = [0]*4

    draw_rot = False

    _repaint_model = True
    _repaint_tools = True
    __paint_cursor = False

    _locked = None
    _horiz = None
    _pos = None

    def reset(self):
        self.__ox = self.__oy = .0
        self.__angle = .0
        self.__scale_idx = ViewPort.SCALES.index(1.)

    def draw_cursor(self):
        # FIXME: cursor refresh causes dirty drawing on the model is rotated.
        return
        
        # Erase old position
        self.redraw(self.__old_area, model=False, tools=False, cursor=False)

        # Paint the new one
        self.__old_area = self.get_cursor_area()
        self.redraw(self.__old_area, model=False, tools=False)
        
    def draw_tools(self, area):
        self._tools_buf.clear_area(*area)
        cr = self._tools_ctx
        cr.save()

        # Clip on the requested area
        cr.rectangle(*area)
        cr.clip()

        #=== Tools section ===
        for tool in self._tools:
            tool.draw(cr)

        # rotation helper
        if self.draw_rot:
            cr.set_source_rgba(1,0,0,.7)
            x,y = self._mat_view2model.transform_point(0, 0)
            cr.arc(x,y, 12, 0, pi2)
            cr.stroke()
            cr.arc(x,y, .5, 0, pi2)
            cr.stroke()

            cr.move_to(x, y)
            cr.line_to(self.__x, self.__y)
            cr.stroke()

        cr.restore()

    def paint_cursor(self):
        cr = self._cr    

        cr.set_line_width(1)
        cr.set_source_rgb(0,0,0)
        cr.arc(self.__x+.5, self.__y+.5, self.__r, 0, pi2)
        cr.stroke()

        cr.set_source_rgb(1,1,1)
        cr.arc(self.__x-.5, self.__y-.5, self.__r, 0, pi2)
        cr.stroke()

    def stroke_end(self):
        self._pos = None
        self._locked = None
        self._horiz = None
        
    def __gen_cursor_area(self):
        # Offsets are due to the antialiasing
        self.__cur_area = (int(floor(self.__x-self.__r))-1,
                           int(floor(self.__y-self.__r))-1,
                           int(ceil(2*self.__r))+3,
                           int(ceil(2*self.__r))+3)

    def move_cursor(self, x, y):
        self.__x = x
        self.__y = y

    def set_cursor_radius(self, r):
        self.__rr = r
        self.__r = max(1.5, r*ViewPort.SCALES[self.__scale_idx])
        self.__gen_cursor_area()

    def get_cursor_area(self):
        return self.__cur_area

    def tool_hit(self, state):
        for tool in self._tools:
            if tool.enable and tool.ishit(self._cr, *state.vpos):
                return tool

    def tool_motion(self, tool, state):
        res = tool.move_handler(*state.vpos)
        if res:
            tool.enable = False
        self.redraw(model=False, tools=True, cursor=False)
        return res

    def toggle_line_ruler(self):
        state = not self._tools[0].enable
        self._tools[0].enable = state
        if state:
            self._tools[1].enable = False
        self.redraw(model=False, tools=True, cursor=False)
        if state:
            return self._tools[0]

    def toggle_ellipse_ruler(self):
        state = not self._tools[1].enable
        self._tools[1].enable = state
        if state:
            self._tools[0].enable = False
        self.redraw(model=False, tools=True, cursor=False)
        if state:
            return self._tools[1]

    def toggle_navigator(self):
        state = not self._tools[2].enable
        self._tools[2].enable = state
        self.redraw(model=False, tools=True, cursor=False)
        if state:
            return self._tools[2]

    @property
    def vp_size(self):
        return self._width, self._height
