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
from .cairo_tools import *

pi2 = pi*2

def get_imat(m):
    m = m * cairo.Matrix()
    m.invert()
    return m

class SimpleViewPort:
    """USed only to draw strokes, without cursor display and
    no dynamic model matrix modifications.
    """
    
    _model_context = None
    _model_surface = None
    _backcolor = None # background as solid color
    _backsurf = None # background as pattern

    _cr = None
    _model_mat = cairo.Matrix()
    _model_imat = get_imat(_model_mat)

    _width = None
    _height = None

    _repaint_model = True

    def set_background(self, back):
        if isinstance(back, basestring):
            self.set_background_file(back)
        else:
            self.set_background_rgb(back)

    def set_background_file(self, filename):
        self._backsurf = cairo.SurfacePattern(cairo.ImageSurface.create_from_png(filename))
        self._backsurf.set_extend(cairo.EXTEND_REPEAT)
        self._backsurf.set_filter(cairo.FILTER_NEAREST)
        self._backcolor = None

    def set_background_rgb(self, rgb):
        self._backcolor = rgb
        self._backsurf = None

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
            cr.set_source(self._backsurf)
        cr.paint()

        # Convert the area given into viewport coordinates
        # into model coordinates, by installing a clip.
        x,y,w,h = cr.clip_extents()
        x = int(floor(x)-1)
        y = int(floor(y)-1)
        w = int(ceil(w)+1) - x + 1
        h = int(ceil(h)+1) - y + 1
        area = (x,y,w,h)
        
        for layer in layers:
            rsurf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
            
            # Blit layer's tiles using over ope mode on the render surface
            def cb(tile):
                tile.blit(_pixbuf.FORMAT_ARGB8,
                          rsurf.get_data(),
                          rsurf.get_stride(),
                          w, h, tile.x-x, tile.y-y)
                          
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
    SCALES = [0.2, 0.25, 0.33333, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 10., 20.]
    MAX_SCALE = len(SCALES)-1

    _debug = 0

    _backcolor = None # background as solid color
    _backsurf = None # background as pattern

    _tools = None

    # View context
    _cr = None
    _mat_model2view = None
    _mat_view2model= None

    _width = None
    _height = None

    __scale_idx = SCALES.index(1.)
    __ox = .0
    __oy = .0
    __xoff = .0
    __yoff = .0
    __angle = .0

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

    def set_background(self, back):
        if isinstance(back, basestring):
            self.set_background_file(back)
        else:
            self.set_background_rgb(back)

    def set_background_file(self, filename):
        self._backsurf = cairo.SurfacePattern(cairo.ImageSurface.create_from_png(filename))
        self._backsurf.set_extend(cairo.EXTEND_REPEAT)
        self._backsurf.set_filter(cairo.FILTER_NEAREST)
        self._backcolor = None

    def set_background_rgb(self, rgb):
        self._backcolor = rgb
        self._backsurf = None

    def reset(self):
        self.__ox = self.__oy = .0
        self.__angle = .0
        self.__scale_idx = ViewPort.SCALES.index(1.)

    def repaint(self, cr, docproxy, area, width, height):
        "Cached model painting routine"
        newsize = self.init_cairo_context(cr, width, height)

        try:
            assert all(isinstance(int(x), int) for x in area)
        except:
            raise RuntimeError("bad area values: %s" % str(area))

        # Need to regenerate model surface?
        if self._repaint_model or newsize:
            self.draw_model(docproxy, area)
            self._repaint_model = False

        # Need to regenerate tools surface?
        if self._repaint_tools or newsize:
            self.draw_tools(area)
            self._repaint_tools = False

        # Paint cached surfaces on the destination context

        # Clip on the requested area
        cr.rectangle(*area)
        cr.clip()
        
        cr.set_operator(cairo.OPERATOR_SOURCE)
        
        cr.set_source_surface(self._model_surface, 0, 0)
        cr.paint()
        
        cr.set_operator(cairo.OPERATOR_OVER)
        
        cr.set_source_surface(self._tools_surface, 0, 0)
        cr.paint()

        # Cursor
        # FIXME: see draw_cursor comment
        ##if self.__paint_cursor:
        ##    self.paint_cursor()
        ##    self.__paint_cursor = False
                
        return area

    def set_repaint(self, model, tools, cursor):
        self._repaint_model |= model
        self._repaint_tools |= tools
        self.__paint_cursor = cursor;

    def draw_cursor(self):
        # FIXME: cursor refresh causes dirty drawing on the model is rotated.
        return
        
        # Erase old position
        self.redraw(self.__old_area, model=False, tools=False, cursor=False)

        # Paint the new one
        self.__old_area = self.get_cursor_area()
        self.redraw(self.__old_area, model=False, tools=False)

    def init_cairo_context(self, cr, w, h):
        self._cr = cr
        if self._width != w or self._height != h:
            self._width = w
            self._height = h

            # Create some caches for drawings
            self._model_buf = _pixbuf.Pixbuf(_pixbuf.FORMAT_ARGB8, w, h)
            self._model_surface = cairo.ImageSurface.create_for_data(self._model_buf, cairo.FORMAT_ARGB32, w, h)
            self._model_ctx = cairo.Context(self._model_surface)
            self._tools_buf = _pixbuf.Pixbuf(_pixbuf.FORMAT_ARGB8, w, h)
            self._tools_surface = cairo.ImageSurface.create_for_data(self._tools_buf, cairo.FORMAT_ARGB32, w, h)
            self._tools_ctx = cairo.Context(self._tools_surface)

            self.update_model_matrix()
            res = True
        else:
            res = False

        if not self._tools:
            self._tools = (LineTool(self), EllipseTool(self), Navigator(self))

        if res:
            for tool in self._tools:
                tool.compute_data()
            
        return res

    def update_model_matrix(self, *args):
        self._mat_model2view = m = cairo.Matrix()

        # Apply affine transformations
        # xoff, yoff are used to define active layer origin
        m.translate(self.__ox, self.__oy)
        m.rotate(self.__angle)
        s = ViewPort.SCALES[self.__scale_idx]
        m.scale(s, s)
        if args:
            self.__xoff, self.__yoff = args
        m.translate(self.__xoff, self.__yoff)

        # Do origin pixel alignement
        # Cairo FAQ preconise to do this for fast renderings.
        x, y = get_imat(m).transform_distance(1, 1)
        x, y = m.transform_distance(round(x), round(y))
        m.translate(x, y)
        
        self._mat_view2model = get_imat(m)

    def draw_model(self, docproxy, area):
        self._model_buf.clear_area(*area)
        cr = self._model_ctx
        cr.save()

        # Clip on the requested area
        cr.rectangle(*area)
        cr.clip()
        
        # Set model affines transformations
        cr.set_matrix(self._mat_model2view)
        
        # Temporary remove the active layer offset
        cr.translate(-self.__xoff, -self.__yoff)

        # Convert the clipped area given into viewport coordinates
        # into model coordinates, add extra pixels for cairo internals.
        x,y,w,h = cr.clip_extents()
        x = int(floor(x)-1)
        y = int(floor(y)-1)
        w = int(ceil(w)+1) - x + 1
        h = int(ceil(h)+1) - y + 1
        
        for layer in docproxy.layers:
            if not layer.visible: continue
            
            rsurf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
                        
            # Add layer offset
            ox = x - int(layer.x)
            oy = y - int(layer.y)
            
            # Blit layer's tiles using over ope mode on the render surface
            def cb(tile):
                tile.blit(_pixbuf.FORMAT_ARGB8,
                          rsurf.get_data(),
                          rsurf.get_stride(),
                          w, h, tile.x-ox, tile.y-oy)
                          
            layer.surface.rasterize((ox,oy,w,h), cb)
            rsurf.mark_dirty()
            
            # Now paint this rendered layer surface on the model surface
            cr.set_source_surface(rsurf, x, y)
            
            # pixelize if zoom level is high.
            if self.__scale_idx > 7:
                cr.get_source().set_filter(cairo.FILTER_FAST)
            else:
                cr.get_source().set_filter(cairo.FILTER_BILINEAR)
                
            cr.set_operator(layer.OPERATORS[layer.operator])
            cr.paint_with_alpha(layer.opacity)
            
        # Paint background, but as bottom layer
        cr.set_operator(cairo.OPERATOR_DEST_OVER)
        if self._backcolor:
            cr.set_source_rgb(*self._backcolor)
        else:
            cr.set_source(self._backsurf)
        cr.paint()
            
        cr.restore()
        
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
        
    def get_model_point(self, *a):
        return self._mat_view2model.transform_point(*a)

    def get_model_distance(self, *a):
        return self._mat_view2model.transform_distance(*a)

    def get_view_point(self, *a):
        return self._mat_model2view.transform_point(*a)
        
    def get_view_distance(self, *a):
        return self._mat_model2view.transform_distance(*a)

    def get_view_area(self, x, y, w, h):
        """Transform given area coordinates from model to view space.
        Note this function returns integers, not float.
        """

        if self.__angle:
            # XXX: need a C version?
            x2, y2 = self.get_view_point(x,y)
            x3, y3 = self.get_view_point(x+w,y)
            x4, y4 = self.get_view_point(x+w,y+h)
            x5, y5 = self.get_view_point(x,y+h)
            x = min(x2,x3,x4,x5)
            y = min(y2,y3,y4,y5)
            return x, y, ceil(max(x2,x3,x4,x5))-x, ceil(max(y2,y3,y4,y5))-y
        
        w, h = self._mat_model2view.transform_distance(w,h)
        return self._mat_model2view.transform_point(x,y) + (ceil(w), ceil(h))

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

    def scroll(self, dx, dy):
        self.__ox += dx
        self.__oy += dy

    def scale_up(self):
        s = self.__scale_idx
        self.__scale_idx = min(self.__scale_idx+1, ViewPort.MAX_SCALE)
        #self.set_cursor_radius(self.__rr)
        return s != self.__scale_idx

    def scale_down(self):
        s = self.__scale_idx
        self.__scale_idx = max(self.__scale_idx-1, 0)
        #self.set_cursor_radius(self.__rr)
        return s != self.__scale_idx

    def rotate(self, dr):
        self.__angle = (self.__angle + dr) % pi2

    @property
    def scale(self):
        return ViewPort.SCALES[self.__scale_idx]

    @staticmethod
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

    def compute_motion(self, device):
        if device.previous:
            os = device.previous
            ns = device.current
            return [ a-b for a,b in zip(ns.vpos, os.vpos) ]
        return 0, 0

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
