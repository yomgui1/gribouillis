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

from gi.repository import Gtk as gtk
from gi.repository import Gdk as gdk
from gi.repository import GObject as gobject
import cairo

from math import log, exp

import main

from model import _pixbuf, BrushProxy
from model.surface import BoundedPlainSurface
from model.colorspace import ColorSpaceRGB
from model.brush import DrawableBrush
from utils import _T

from .common import SubWindow


class BrushPreview(gtk.DrawingArea):
    WIDTH = 300
    HEIGHT = 64
    _cur_pos = None
        
    def on_expose(self, widget, evt):
        cr = widget.window.cairo_create()
        return True

    def __init__(self, dv=None):
        super(BrushPreview, self).__init__()
        self._brush = DrawableBrush()
        self._brush.rgb = (0,0,0)
        self._states = list(self._brush.gen_preview_states(BrushPreview.WIDTH,
                                                           BrushPreview.HEIGHT))
        self._surface = BoundedPlainSurface(_pixbuf.FORMAT_ARGB8,
                                            BrushPreview.WIDTH,
                                            BrushPreview.HEIGHT)

        self.set_size_request(BrushPreview.WIDTH, BrushPreview.HEIGHT)
        self.set_events(gdk.EXPOSURE_MASK)
        self.connect("expose-event", self.on_expose)
        
    def stroke(self, v=1.0):
        self._brush.paint_rgb_preview(BrushPreview.WIDTH, BrushPreview.HEIGHT,
                                      surface=self._surface, states=self._states)
        self.queue_draw()

    def set_attr(self, name, v):
        if name == 'smudge': return
        setattr(self._brush, name, v)
        self.stroke()
        
    def set_from_brush(self, brush):
        self._brush.set_from_brush(brush)
        self._brush.smudge = 0.
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
        self.prop['radius_min']        = self._add_slider(table, 'radius_min', -1, 5, 3, .1, .5, islog = True)
        self.prop['radius_max']        = self._add_slider(table, 'radius_max', -1, 5, 3, .1, .5, islog=True)
        self.prop['yratio']            = self._add_slider(table, 'yratio', 1.0, 32., 1., 0.1, 2)
        self.prop['spacing']           = self._add_slider(table, 'spacing', 0.01, 4, 0.25, .01, 0.1)
        self.prop['opacity_min']       = self._add_slider(table, 'opacity_min', 0, 1, 1, 1/255., 10/255.)
        self.prop['opacity_max']       = self._add_slider(table, 'opacity_max', 0, 1, 1, 1/255., 10/255.)
        self.prop['hardness']          = self._add_slider(table, 'hardness', 0, 1, 1, .01, 0.1)
        self.prop['erase']             = self._add_slider(table, 'erase', 0, 1, 1, .01, 0.1)
        self.prop['opa_comp']          = self._add_slider(table, 'opa_comp', 0, 2,  .9, 0.01, 0.1)
        self.prop['motion_track']      = self._add_slider(table, 'motion_track', 0.0, 2.0, 1.0, .1, 1)
        self.prop['hi_speed_track']    = self._add_slider(table, 'hi_speed_track', 0.0, 2.0, 0.0, .01, 0.1)
        self.prop['smudge']            = self._add_slider(table, 'smudge', 0.0, 1.0, 0.0, .01, 0.1)
        self.prop['smudge_var']        = self._add_slider(table, 'smudge_var', 0.0, 1.0, 0.0, .01, 0.1)
        self.prop['grain']             = self._add_slider(table, 'grain', 0.0, 1.0, 0.0, .01, 0.1)
        self.prop['dab_radius_jitter'] = self._add_slider(table, 'dab_radius_jitter', 0.0, 1.0, 0.0, .01, 0.1)
        self.prop['dab_pos_jitter']    = self._add_slider(table, 'dab_pos_jitter', 0.0, 5.0, 0.0, .01, 0.1)
        self.prop['direction_jitter']  = self._add_slider(table, 'direction_jitter', 0.0, 1.0, 0.0, .01, 0.1)

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
            self.mediator.sendNotification(BrushProxy.BRUSH_PROP_CHANGED, (self._brush, name))

    def set_property(self, name, value):
        if name in ('color', ): return
        if name in self.prop:
            hs = self.prop[name]
            hs.set_value(value if not hs.islog else log(value))

    def _set_brush(self, brush):
        self._brush = None # forbid brush prop changed events, so a endless loop

        # Update the UI
        for name in self.prop.keys():
            self.set_property(name, getattr(brush, name))

        self._brush = brush
        self.bprev.set_from_brush(brush)

    brush = property(fget=lambda self: self._brush, fset=_set_brush)
