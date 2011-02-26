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

import gtk, cairo
from gtk import gdk
from math import log, exp, sin, pi

import model, view, main
from utils import Mediator, mvcHandler

from view.backend_cairo import SimpleViewPort
from model.surface import BoundedPlainSurface
from model.layer import Layer
from model.colorspace import ColorSpaceRGB
from model import _pixbuf
from model.brush import DrawableBrush
from model.devices import DeviceState

from .common import SubWindow

__all__ = [ 'BrushEditorWindow', 'BrushEditorWindowMediator' ]


class BrushPreview(gtk.DrawingArea, SimpleViewPort):
    WIDTH = 300
    HEIGHT = 64
        
    def on_expose(self, widget, evt):
        cr = widget.window.cairo_create()
        self.repaint(cr, self._layers, evt.area, self.allocation.width, self.allocation.height)
        return True

    def __init__(self, dv=None):
        super(BrushPreview, self).__init__()
        self._gen_poslist()
        self._brush = DrawableBrush()
        self._brush.rgb = (0,0,0)
        pixfmt = _pixbuf.format_from_colorspace(ColorSpaceRGB.type, _pixbuf.FLAG_15X | _pixbuf.FLAG_ALPHA_FIRST)
        self._surface = BoundedPlainSurface(pixfmt,BrushPreview.WIDTH, BrushPreview.HEIGHT)
        layer = Layer(self._surface, "BrushPreviewLayer")
        self._layers = ( layer, )
        self.set_background(main.Gribouillis.DEFAULT_BRUSHPREVIEW_BACKGROUND)

        self.set_size_request(BrushPreview.WIDTH, BrushPreview.HEIGHT)
        self.set_events(gdk.EXPOSURE_MASK)
        self.connect("expose-event", self.on_expose)
        
    def _gen_poslist(self):
        self._states = []
        xmin = 32
        xmax = BrushPreview.WIDTH-xmin
        y = BrushPreview.HEIGHT / 2
        r = BrushPreview.HEIGHT / 4
        w = (xmax-xmin)-1
        
        for x in xrange(xmin, xmax, 2):
            state = DeviceState()
            state.time = t = float(x-xmin)/w
            state.pressure = 1.0 - (2*t-1)**2
            state.vpos = (x, y + int(r*sin(2.*t*pi)))
            state.xtilt = state.ytilt = 0.0
            state.spos = self.get_model_point(*state.vpos)
            self._states.append(state)
        
    def stroke(self):
        self._surface.clear_white()       
        self._brush.surface = self._surface
        self._brush.stroke_start(self._states[0])
        for state in self._states:
            self._brush.draw_stroke(state)
        self._brush.stroke_end()
        self.set_repaint(True)
        self.queue_draw()
        
    def set_attr(self, name, v):
        setattr(self._brush, name, v)
        self.stroke()
        
    def set_from_brush(self, brush):
        self._brush.set_from_brush(brush)
        self.stroke()
        

class BrushEditorWindow(SubWindow):
    _brush = None
    __i = 0

    def __init__(self):
        super(BrushEditorWindow, self).__init__()

        # UI
        topbox = gtk.VBox()
        self.add(topbox)

        # Brush preview
        self.bprev = BrushPreview()
        
        box = gtk.HBox()
        box.pack_start(gtk.VBox())
        box.pack_start(self.bprev, False, False)
        box.pack_start(gtk.VBox())
        topbox.pack_start(box, False, False)

        # Brush parameters
        table = gtk.Table(2)
        topbox.pack_start(table, False, False)

        self.prop = {}
        self.prop['radius_min']     = self._add_slider(table, 'radius_min', -1, 5, 3, .1, .5, islog=True)
        self.prop['radius_max']     = self._add_slider(table, 'radius_max', -1, 5, 3, .1, .5, islog=True)
        self.prop['opacity_min']    = self._add_slider(table, 'opacity_min', 0, 1, 1, 1/255., 10/255.)
        self.prop['opacity_max']    = self._add_slider(table, 'opacity_max', 0, 1, 1, 1/255., 10/255.)
        self.prop['hardness']       = self._add_slider(table, 'hardness', 0, 1, 1, .01, 0.1)
        self.prop['erase']          = self._add_slider(table, 'erase', 0, 1, 1, .01, 0.1)
        self.prop['opa_comp']       = self._add_slider(table, 'opa_comp', 0, 2,  .9, 0.01, 0.1)
        self.prop['spacing']        = self._add_slider(table, 'spacing', 0.01, 4, 0.25, .01, 0.1, islog=False)
        self.prop['motion_track']   = self._add_slider(table, 'motion_track', 0.0, 2.0, 1.0, .1, 1)
        self.prop['hi_speed_track'] = self._add_slider(table, 'hi_speed_track', 0.0, 2.0, 0.0, .01, 0.1)
        self.prop['smudge']         = self._add_slider(table, 'smudge', 0.0, 1.0, 0.0, .01, 0.1)
        self.prop['smudge_var']     = self._add_slider(table, 'smudge_var', 0.0, 1.0, 0.0, .01, 0.1)
        self.prop['grain']          = self._add_slider(table, 'grain', 0.0, 1.0, 0.0, .01, 0.1)
        self.prop['radius_random']  = self._add_slider(table, 'radius_random', 0.0, 1.0, 0.0, .01, 0.1)

        self.set_title('Brush Editor')
        self.set_default_size(320, 100)
        self.connect('delete-event', self.hide)

        topbox.show_all()

    def show_all(self):
        pos = self._saved_pos
        gtk.Window.show_all(self)
        if pos: self.move(*pos)

    def hide(self, *a):
        self._saved_pos = self.get_position()
        gtk.Window.hide(self)
        return True

    def _add_slider(self, table, label, vmin, vmax, vdef, step, page_step, islog=False):
        i = self.__i
        self.__i += 1
        lb = gtk.Label(label)
        lb.set_alignment(1, .5)

        hs = gtk.HScale()
        hs.set_range(vmin, vmax)
        hs.set_increments(step, page_step)
        hs.set_value_pos(gtk.POS_LEFT)
        hs.set_digits(2)
        hs.set_value(vdef if not islog else log(vdef))
        hs.connect('value-changed', self._on_value_changed, label)
        hs.islog = islog

        if islog: hs.connect('format-value', self._format_value)

        table.attach(lb, 0, 1, i, i+1, gtk.FILL, gtk.FILL, 5, 0)
        table.attach(hs, 1, 2, i, i+1)

        return hs

    def _format_value(self, widget, value):
        return str(round(exp(value), 2))

    def _on_value_changed(self, widget, name):
        if self._brush:
            v = widget.get_value()
            v = v if not widget.islog else exp(v)
            setattr(self._brush, name, v)
            self.bprev.set_attr(name, v)

            # FIXME: this call should be in a mediator or proxy, not in the component itself!
            self.mediator.sendNotification(main.Gribouillis.BRUSH_PROP_CHANGED, (self._brush, name))

    def set_property(self, name, value):
        if name in ('color', ): return
        if name in self.prop:
            hs = self.prop[name]
            hs.set_value(value if not hs.islog else log(value))

    def _set_brush(self, brush):
        self._brush = None # forbid brush prop changed events, so a endless loop

        # Update the UI
        for name in self.prop.iterkeys():
            self.set_property(name, getattr(brush, name))

        self._brush = brush
        self.bprev.set_from_brush(brush)

    brush = property(fget=lambda self: self._brush, fset=_set_brush)


class BrushEditorWindowMediator(Mediator):
    NAME = "BrushEditorWindowMediator"

    #### Private API ####

    def __init__(self, component):
        assert isinstance(component, BrushEditorWindow)
        super(BrushEditorWindowMediator, self).__init__(viewComponent=component)

        component.mediator = self

    def _set_docproxy(self, docproxy):
        #print "[BE] using brush BH=%s" % docproxy.brush
        self.viewComponent.brush = docproxy.brush

    ### notification handlers ###

    @mvcHandler(main.Gribouillis.DOC_ACTIVATED)
    def _on_activate_document(self, docproxy):
        if docproxy.brush:
            self._set_docproxy(docproxy)

    @mvcHandler(main.Gribouillis.DOC_BRUSH_UPDATED)
    def _on_activate_document(self, docproxy):
        self._set_docproxy(docproxy)


