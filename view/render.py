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

from model import _pixbuf, _cutils, surface


class Render(object):
    viewport = None

    def matrix_changed(self): pass

    def apply_operator(self):
        raise NotImplemented()

    def reset(self, width, height, pixel_format):
        raise NotImplemented()

    def render(self, clip):
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

        self.docproxy.document.rasterize(cr, self.pixbuf)
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


class DocumentRender(Render):
    # Full PixBuf Render implementation

    def __init__(self):
        self._s = None

    def reset(self, width, height, pixel_format=_pixbuf.FORMAT_ARGB15X):
        del self._s
        self._s = surface.UnboundedTiledSurface(pixel_format)

    def set_pixbuf(self, pixbuf):
        self._pb = pixbuf

    def render(self, clip, m2v_mat):
        assert isinstance(clip, _cutils.Area)
        self._pb.clear_area(*clip)
        self._s.clear()
        self.docproxy.document.rasterize_to_surface(self._s, clip, m2v_mat)
        self._s.rasterize(clip, 0, 0, destination=self._pb)

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

