###############################################################################
# Copyright (c) 2009-2013 Guillaume Roguez
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

from math import floor, ceil

import main

from model import _pixbuf, prefs
from utils import virtualmethod, resolve_path


def get_imat(m):
    m = cairo.Matrix(*m)
    m.invert()
    return m


class ViewPort(object):
    SCALES = [0.05, 0.1, 0.2, 0.25, 0.33333, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 10., 20.]
    MAX_SCALE = len(SCALES) - 1

    _debug = 0
    _ox = _oy = 0.0
    _sox = _soy = 0.0
    _facx = _facy = 1.0
    _scale_idx = SCALES.index(1.)
    _rot_mat = None

    def __init__(self, render):
        self._re = render
        self.reset_view()
        self.update_matrix()
        render.viewport = self

        # Alias
        self.apply_operator = render.apply_operator

    def set_view_size(self, width, height):
        width = int(width)
        height = int(height)
        assert width > 0 and height > 0

        self.width = width
        self.height = height
        self.full_area = (0, 0, width, height)
        self.update_matrix()

        self._re.set_view_size(width, height)

        return self.full_area

    def update_matrix(self):
        # View affine transformations
        s = ViewPort.SCALES[self._scale_idx]
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
        self._mat_model2view = view_mat
        self._mat_view2model = get_imat(view_mat)

        # Matrix operations aliases
        self.get_model_point = self._mat_view2model.transform_point
        self.get_model_distance = self._mat_view2model.transform_distance
        self.get_view_point = view_mat.transform_point
        self.get_view_distance = view_mat.transform_distance
        self._re.matrix_changed()

    def like(self, other):
        "Copy viewing properties from an other Viewport instance"

        assert isinstance(other, ViewPort)
        for name in "_ox _oy _sox _soy _facx _facy _scale_idx".split():
            setattr(self, name, getattr(other, name))

        if other._rot_mat:
            self._rot_mat = cairo.Matrix(*other._rot_mat)
            self._rot_imat = get_imat(self._rot_mat)
        else:
            self._rot_mat = self._rot_imat = None

        self.update_matrix()

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

    # scroll, scale_up, scale_down, set_scale, rotate and all reset methods
    # don't call update_matrix! This method shall be called by user
    # when all transformations are done to finalize viewing matrices.

    def reset_view(self):
        self.reset_translation()
        self.reset_scale()
        self.reset_rotation()
        self.reset_mirror()

    def reset_translation(self):
        res = self._ox or self._oy
        self._ox = self._oy = 0.0
        return res

    def reset_scale(self):
        os = self._scale_idx
        self._scale_idx = ViewPort.SCALES.index(1.)
        return os != self._scale_idx

    def reset_rotation(self):
        res = self._rot_mat is not None
        self._rot_mat = None
        self._rot_imat = None
        return res

    def reset_mirror(self):
        self._sox = self._soy = 0.0
        self._facx = self._facy = 1.0

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
        self._scale_idx = min(self._scale_idx + 1, ViewPort.MAX_SCALE)
        return s != self._scale_idx

    def scale_down(self):
        s = self._scale_idx
        self._scale_idx = max(self._scale_idx - 1, 0)
        return s != self._scale_idx

    def set_scale(self, s=SCALES.index(1.)):
        self._scale_idx = max(0, min(s + ViewPort.SCALES.index(1.), ViewPort.MAX_SCALE))
        return s != self._scale_idx

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

    # Rendering related methods

    def clear_area(self, clip=None):
        self._re.clear_area(clip or self.full_area)

    def repaint(self, clip=None):
        self._re.repaint(clip or self.full_area)

    # Properties

    def get_offset(self):
        return self._ox, self._oy

    def set_offset(self, offset):
        self._ox, self._oy = offset

    @property
    def scale(self):
        return ViewPort.SCALES[self._scale_idx]

    @property
    def scale_idx(self):
        return self._scale_idx

    offset = property(get_offset, set_offset)
    matrix = property(fget=get_matrix, fset=set_matrix)


class Render(object):
    viewport = None

    def matrix_changed(self): pass

    def apply_operator(self):
        raise NotImplemented()

    def set_view_size(self, width, height):
        raise NotImplemented()

    def clear_area(self, clip):
        raise NotImplemented()

    def repaint(self, clip):
        raise NotImplemented()

    @property
    def pixbuf(self):
        raise NotImplemented()


class CairoRenderBase(Render):
    # Cairo render implementation

    def set_view_size(self, width, height):
        self._buf = _pixbuf.Pixbuf(_pixbuf.FORMAT_RGBA8, width, height)
        self.surface = cairo.ImageSurface.create_for_data(self._buf, cairo.FORMAT_ARGB32, width, height)
        self.ctx = cairo.Context(self.surface)

    def clear_area(self, clip):
        self.pixbuf.clear_area(*clip)
        self.surface.mark_dirty_rectangle(*clip)

    @property
    def pixbuf(self):
        return self._buf


class DocumentCairoRender(CairoRenderBase):
    filter = cairo.FILTER_FAST
    passepartout = False
    docproxy = None # need to be set before repaint() call

    def enable_fast_filter(self, state=True):
        self.filter = cairo.FILTER_FAST if state else None

    def render_passepartout(self):
        cr = self.ctx
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
                    cr.set_matrix(self.viewport.matrix)
                    cr.new_sub_path()
                    cr.rectangle(x, y, w, h)
                    cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
                    cr.fill()

        cr.restore()

    def repaint(self, clip):
        # Start with a fully transparent region
        self.clear_area(clip)

        # Cairo rendering pipeline start here
        cr = self.ctx
        cr.save()

        # Clip again on requested area
        cr.rectangle(*clip)
        cr.clip()

        # Setup our cairo context using document viewing matrix
        cr.set_matrix(self.viewport.matrix)

        # Paint the document, pixelize using FILTER_FAST filter if zoom level is high
        if self.filter is None:
            flt = cairo.FILTER_FAST if self.viewport.scale_idx > prefs['view-filter-threshold'] else cairo.FILTER_BILINEAR
        else:
            flt = self.filter

        self.docproxy.document.rasterize(cr, self.pixbuf, filter=flt)
        cr.restore()


class ToolsCairoRender(CairoRenderBase):
    def __init__(self):
        CairoRenderBase.__init__(self)
        self.tools = []

    def add_tool(self, tool):
        self.tools.append(tool)
        self.repaint(tool.area)

    def rem_tool(self, tool):
        area = tool.area
        self.tools.remove(tool)
        tool.reset()
        self.repaint(area)

    def is_tool_hit(self, tool, *pos):
        return tool.hit(self.ctx, *pos)

    def get_handler_at_pos(self, *pos):
        for tool in self.tools:
            handler = tool.hit_handler(self.ctx, *pos)
            if handler:
                return handler

    def repaint(self, clip):
        cr = self.ctx
        cr.save()

        # Clip on the requested area
        cr.rectangle(*clip)
        cr.clip()

        # Clear the repaint region
        self.clear_area(clip)

        for tool in self.tools:
            cr.save()
            tool.repaint(self, cr, self.width, self.height)
            cr.restore()

        cr.restore()


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


prefs.add_default('view-filter-threshold', 7)
prefs.add_default('view-color-passepartout', (0.33, 0.33, 0.33, 1.0))
