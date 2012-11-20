###############################################################################
# Copyright (c) 2009-2012 Guillaume Roguez
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

from view import Render
from model import _pixbuf


class DocumentOpenGLRender(Render):
    filter = cairo.FILTER_FAST
    passepartout = False
    docproxy = None # need to be set before repaint() call
    
    def enable_fast_filter(self, state=True):
        self.filter = cairo.FILTER_FAST if state else None

    def render_passepartout(self):
        cr = self._ctx
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

        self.docproxy.document.rasterize(cr, self.buf, filter=flt)
        cr.restore()

    # Render class implemtation
    
    def set_view_size(self, width, height):
        # create new cairo surface/context
        self.buf = _pixbuf.Pixbuf(_pixbuf.FORMAT_RGBA8, width, height)
        self.surf = cairo.ImageSurface.create_for_data(self.buf, cairo.FORMAT_ARGB32, width, height)
        self.ctx = cairo.Context(self.surf)
    
    def clear_area(self, clip):
        self.buf.clear_area(*clip)
        self.surf.mark_dirty_rectangle(*clip)

    @property
    def pixbuf(self):
        return self.buf