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

"""ViewPort is a view component to render a model component
and gives the result to the user.

A ViewPort is connected to only one model component, and a model component may
be connected to many ViewPorts.

As view components, ViewPorts are reactive to model changes and user inputs.

ViewPort is the base class used to construct real used classes:

DocumentViewPort: model is document (composite of layers)
SurfaceViewPort: model is only a single surface.
"""

import cairo
import random

from math import floor, ceil, pi, atan

import main

from model import _pixbuf
from utils import virtualmethod, resolve_path
from model.prefs import prefs, defaults

pi2 = 2 * pi


def get_imat(m):
    m = cairo.Matrix(*m)
    m.invert()
    return m


class ViewPortBase(object):
    _debug = 0

    SCALES = [0.2, 0.25, 0.33333, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 10., 20.]
    MAX_SCALE = len(SCALES) - 1

    width = height = stride = 0
    _ctx = None

    # View matrix data
    _scale_idx = SCALES.index(1.)

    def __init__(self):
        self.reset_view()

    def set_view_size(self, width, height):
        width = int(width)
        height = int(height)
        assert width > 0 and height > 0

        if self.width != width or self.height != height:
            self.width = width
            self.height = height

            self.update_matrix()

            # create new cairo surface/context
            self._buf = _pixbuf.Pixbuf(_pixbuf.FORMAT_ARGB8, width, height)
            self.stride = self._buf.stride
            self.__surf = cairo.ImageSurface.create_for_data(self._buf, cairo.FORMAT_ARGB32, width, height)
            self._ctx = cairo.Context(self.__surf)

        return (0, 0, width, height)

    def update_matrix(self):
        # View affine transformations
        s = ViewPortBase.SCALES[self._scale_idx]
        view_mat = cairo.Matrix(s, 0, 0, s, self._ox, self._oy)

        if self._rot_mat:
            view_mat = view_mat.multiply(self._rot_mat)

        # Prepare matrix with possible axial symetries
        swap_mat = cairo.Matrix(self._facx, 0, 0, self._facy, self._sox * (1 - self._facx), self._soy * (1 - self._facy))
        self._swap_mat = swap_mat
        view_mat = view_mat.multiply(swap_mat)

        # Do origin pixel alignement
        # Cairo FAQ preconise to do this for fast renderings.
        #x, y = get_imat(view_mat).transform_distance(1, 1)
        #x, y = view_mat.transform_distance(round(x), round(y))
        #view_mat.translate(x, y)
        self.set_matrix(view_mat)

    def get_matrix(self):
        return self._mat_model2view

    def set_matrix(self, view_mat=None):
        self._mat_view2model = get_imat(view_mat)
        self._mat_model2view = view_mat

        # Matrix operations aliases
        self.get_model_point = self._mat_view2model.transform_point
        self.get_model_distance = self._mat_view2model.transform_distance
        self.get_view_point = view_mat.transform_point
        self.get_view_distance = view_mat.transform_distance

    def reset_view(self):
        self._ox = self._oy = .0
        self._sox = self._soy = .0
        self._facx = self._facy = 1.
        self._rot_mat = None
        self._rot_imat = None
        self._scale_idx = ViewPortBase.SCALES.index(1.)
        self.update_matrix()

    def clear_area(self, clip=None):
        if clip is None:
            clip = (0, 0, self.width, self.height)

        self._buf.clear_area(*clip)
        self.__surf.mark_dirty_rectangle(*clip)

    def mark_dirty_rectangle(self, rect):
        self.__surf.mark_dirty_rectangle(*rect)

    def get_view_point_pos(self, pos):
        return self.get_view_point(*pos)

    def get_view_area(self, x, y, w, h):
        """Transform a given area from model to view coordinates.
        This function uses the full matrix coefficients.

        WARNING: returns integer area values, not clipped
        on viewport bounds (possible negative values!).
        """

        # Get position of the second point
        w += x - 1
        h += y - 1

        # 2 points are enough for scaling and translation only matrix
        c = [self.get_view_point(x, y), self.get_view_point(w, h)]

        # but in case of rotation we need to check the four corners
        if self._rot_mat:
            c.append(self.get_view_point(w, y))
            c.append(self.get_view_point(x, h))

        lx = sorted(x for x, y in c)
        ly = sorted(y for x, y in c)

        x = int(floor(lx[0]))
        y = int(floor(ly[0]))
        w = int(ceil(lx[-1])) - x + 1
        h = int(ceil(ly[-1])) - y + 1

        # due to mathematical operations just used
        # w and h are always positive numbers.
        return x, y, w, h

    # scoll, scale_up, scale_down, set_scale and rotate don't call update_matrix!
    # This method must be called by user when transformations are done.

    def scroll(self, dx, dy):
        # multiplied by axial swaping coeffiscient to get the right direction
        dx *= self._facx
        dy *= self._facy

        if self._rot_imat:
            dx, dy = self._rot_imat.transform_distance(dx, dy)

        self._ox += dx
        self._oy += dy

    def scale_up(self):
        s = self._scale_idx
        self._scale_idx = min(self._scale_idx + 1, ViewPortBase.MAX_SCALE)
        return s != self._scale_idx

    def scale_down(self):
        s = self._scale_idx
        self._scale_idx = max(self._scale_idx - 1, 0)
        return s != self._scale_idx

    def set_scale(self, s=SCALES.index(1.)):
        self._scale_idx = max(0, min(s + ViewPortBase.SCALES.index(1.), ViewPortBase.MAX_SCALE))
        return s != self._scale_idx

    def reset_translation(self):
        res = self._ox or self._oy
        self._ox = self._oy = 0.0
        return res

    def reset_scale(self):
        os = self._scale_idx
        self._scale_idx = ViewPortBase.SCALES.index(1.)
        return os != self._scale_idx

    def reset_rotation(self):
        res = self._rot_mat is not None
        self._rot_mat = None
        self._rot_imat = None
        return res

    def rotate(self, dr):
        "Rotate around the ViewPort center"
        mat = self._rot_mat or cairo.Matrix()

        cx = self.width / 2.
        cy = self.height / 2.

        inv = cairo.Matrix(*self._swap_mat)
        inv.invert()
        mat = inv.multiply(mat)
        mat.translate(cx, cy)
        mat.rotate(dr)
        mat.translate(-cx, -cy)
        mat = self._swap_mat.multiply(mat)

        self._rot_mat = mat
        self._rot_imat = get_imat(mat)

    def swap_x(self, ox=0):
        self._sox = ox
        self._facx = -self._facx

    def swap_y(self, oy=0):
        self._soy = oy
        self._facy = -self._facy

    def apply_ope(self, operator):
        operator(self._buf, self._buf)

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
            r += atan(float(y) / x)
        elif x < 0:
            r += pi - atan(float(y) / -x)
        else:
            r += pi / 2.

        return r

    # Properties
    #

    @property
    def offset(self):
        return self._ox, self._oy

    @property
    def scale(self):
        return ViewPortBase.SCALES[self._scale_idx]

    @property
    def pixbuf(self):
        "Obtain the raw pixels buffer (ARGB8)"
        return self._buf

    @property
    def cairo_surface(self):
        return self.__surf


class BackgroundMixin:
    _backcolor = None  # background as solid color
    _backpat = None  # background as pattern

    def set_background(self, back):
        if isinstance(back, basestring):
            self.set_background_file(back)
        else:
            self.set_background_rgb(back)
        assert not (self._backpat and self._backcolor)

    def set_background_file(self, filename):
        surf = cairo.ImageSurface.create_from_png(filename)
        self._backpat = cairo.SurfacePattern(surf)
        self._backpat.set_extend(cairo.EXTEND_REPEAT)
        self._backpat.set_filter(cairo.FILTER_NEAREST)
        self._backcolor = None

    def set_background_rgb(self, rgb):
        assert len(rgb) == 3
        self._backcolor = rgb
        self._backpat = None
        try:
            self.docproxy.document.fill = rgb
            self.repaint()
        except:
            pass


class DocumentViewPort(ViewPortBase):
    DEFAULT_FILTER_THRESHOLD = 7

    _backcolor = None  # background as solid color
    _backsurf = None  # background as pattern
    _filter = None
    passepartout = False

    def __init__(self, docproxy):
        ViewPortBase.__init__(self)
        self.docproxy = docproxy

    def enable_fast_filter(self, state=True):
        self._filter = cairo.FILTER_FAST if state else None

    def repaint(self, clip=None):
        if clip is None:
            clip = (0, 0, self.width, self.height)

        cr = self._ctx
        cr.save()

        cr.rectangle(*clip)
        cr.clip()

        # Start with a fully transparent region
        self.clear_area(clip)

        # Setup our cairo context using document viewing matrix
        cr.set_matrix(self._mat_model2view)

        # Paint the document, pixelize using FILTER_FAST filter if zoom level is high
        if self._filter is not None:
            flt = self._filter
        else:
            flt = cairo.FILTER_FAST if self._scale_idx > prefs['view-filter-threshold'] else cairo.FILTER_BILINEAR

        self.docproxy.document.rasterize(cr, filter=flt)
        cr.restore()

        cr.save()

        # Add a Passe-Partout on request
        if self.passepartout:
            area = self.docproxy.document.metadata['dimensions']
            if area:
                x, y, w, h = area
                if w and h:
                    buf = self._buf
                    cr.set_source_rgba(*prefs['view-color-passepartout'])
                    cr.rectangle(0, 0, buf.width, buf.height)
                    cr.set_matrix(self._mat_model2view)
                    cr.new_sub_path()
                    cr.rectangle(x, y, w, h)
                    cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
                    cr.fill()

        cr.restore()


class ToolsViewPort(ViewPortBase):
    """ToolsViewPort class

    Transparent viewport without transformations except pixel alignment correction.
    """

    def __init__(self, *a, **k):
        super(ToolsViewPort, self).__init__(*a, **k)
        self._tools = []

    def add_tool(self, tool):
        self._tools.append(tool)
        self.repaint(tool.area)

    def rem_tool(self, tool):
        area = tool.area
        self._tools.remove(tool)
        tool.reset()
        self.repaint(area)

    def is_tool_hit(self, tool, *pos):
        return tool.hit(self._ctx, *pos)

    def get_handler_at_pos(self, *pos):
        for tool in self._tools:
            handler = tool.hit_handler(self._ctx, *pos)
            if handler:
                return handler

    def repaint(self, clip=None):
        if clip is None:
            clip = (0, 0, self.width, self.height)

        cr = self._ctx
        cr.save()

        # Clip on the requested area
        cr.rectangle(*clip)
        cr.clip()

        # Clear the repaint region
        self.clear_area(clip)

        for tool in self._tools:
            cr.save()
            tool.repaint(self, cr, self.width, self.height)
            cr.restore()

        cr.restore()

    @property
    def tools(self):
        return self._tools


defaults['view-filter-threshold'] = DocumentViewPort.DEFAULT_FILTER_THRESHOLD
defaults['view-color-passepartout'] = (0.33, 0.33, 0.33, 1.0)
prefs.update(defaults)
