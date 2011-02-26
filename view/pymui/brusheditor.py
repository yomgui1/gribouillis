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

import pymui
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


__all__ = [ 'BrushEditorWindow', 'BrushEditorWindowMediator' ]

class BrushPreview(pymui.Area, SimpleViewPort):
    _MCC_ = True
    WIDTH = 300
    HEIGHT = 64
    
    @pymui.muimethod(pymui.MUIM_AskMinMax)
    def _mcc_AskMinMax(self, msg):
        msg.DoSuper()

        minmax = msg.MinMaxInfo.contents

        # FIXME: use += when pymui will be fixed
        minmax.MinWidth = minmax.MinWidth.value + BrushPreview.WIDTH
        minmax.MinHeight = minmax.MinHeight.value + BrushPreview.HEIGHT
        minmax.MaxWidth = minmax.MaxWidth.value + BrushPreview.WIDTH
        minmax.MaxHeight = minmax.MaxHeight.value + BrushPreview.HEIGHT
        minmax.DefWidth = minmax.DefWidth.value + BrushPreview.WIDTH
        minmax.DefHeight = minmax.DefHeight.value + BrushPreview.HEIGHT
        
    @pymui.muimethod(pymui.MUIM_Draw)
    def _mcc_Draw(self, msg):
        msg.DoSuper()

        if msg.flags.value & pymui.MADF_DRAWOBJECT:
            area = (0,0,self.MWidth,self.MHeight)
            cr = self.cairo_context
            cr.reset_clip()
            cr.identity_matrix()
            area = self.repaint(cr, self._layers, area, self.MWidth, self.MHeight)
            self.ClipCairoPaintArea(*area)
            
    def __init__(self, dv=None):
        super(BrushPreview, self).__init__(InnerSpacing=(0,)*4,
                                           Frame='Virtual',
                                           FillArea=False,
                                           DoubleBuffer=True)
        self._gen_poslist()
        self._brush = DrawableBrush()
        self._brush.rgb = (0,0,0)
        pixfmt = _pixbuf.format_from_colorspace(ColorSpaceRGB.type, _pixbuf.FLAG_15X | _pixbuf.FLAG_ALPHA_FIRST)
        self._surface = BoundedPlainSurface(pixfmt,BrushPreview.WIDTH, BrushPreview.HEIGHT)
        layer = Layer(self._surface, "BrushPreviewLayer")
        self._layers = (layer,)
        self.set_background_rgb([1,1,1])
        
    def _gen_poslist(self):
        self._states = []
        xmin = 32
        xmax = BrushPreview.WIDTH-xmin
        y = BrushPreview.HEIGHT / 2
        r = BrushPreview.HEIGHT / 4
        w = (xmax-xmin)-1
        
        for x in xrange(xmin, xmax):
            state = DeviceState()
            state.time = t = float(x-xmin)/w
            state.pressure = 1.0 - (2*t-1)**2
            state.vpos = (x, y + int(r*sin(2.*t*pi)))
            state.xtilt = state.ytilt = 0.0
            state.spos = self.get_model_point(*state.vpos)
            self._states.append(state)
        
    def stroke(self):
        self._surface.clear()
        self._brush.surface = self._surface
        self._brush.stroke_start(self._states[0])
        for state in self._states:
            self._brush.draw_stroke(state)
        self._brush.stroke_end()
        self.set_repaint(True)
        self.Redraw()
        
    def set_attr(self, name, v):
        setattr(self._brush, name, v)
        self.stroke()
        
    def set_from_brush(self, brush):
        self._brush.set_from_brush(brush)
        self.stroke()
        

class FloatValue(pymui.Group):
    def __init__(self, min, max, default=None, cb=None, cb_args=(), islog=False, **kwds):
        super(FloatValue, self).__init__(Horiz=True, **kwds)

        if default is None:
            default = min

        assert min < max and min <= default and max >= default

        self.islog = islog
        self._min = min
        self._range = (max - min)/1000.
        self._default = default

        self._cb = cb
        self._cb_args = cb_args

        self._value = pymui.String(MaxLen=7, Accept="0123456789.", Format='r', FixWidthTxt="-#.###", Frame='String', Background=None)
        self._value.Notify('Acknowledge', self.OnStringValue)
        self._slider = pymui.Slider(Min=0, Max=1000)
        self._slider.Notify('Value', self.OnSliderValue)
        self.AddChild(self._value, self._slider)

        self.value = default

    def _as_float(self, value):
        return value*self._range + self._min

    def _as_str(self, value):
        return "%.3g" % value

    def __float__(self):
        v = self._as_float(self._slider.Value.value)
        return (v if not self.islog else exp(v))

    def __str__(self):
        return "%.3g" % float(self)

    def OnSliderValue(self, evt, *args):
        v = self._as_float(evt.value.value)
        self._value.NNSet('Contents', self._as_str(v if not self.islog else exp(v)))
        if self._cb:
            self._cb(self, *self._cb_args)

    def OnStringValue(self, evt):
        self.value = float(evt.value.contents or (exp(self._min) if self.islog else self._min))

    def SetValue(self, value):
        if self.islog:
            value = log(value)
        self._slider.Value = min(1000, max(0, int((value-self._min)/self._range)))

    def SetDefault(self):
        self.value = self._default

    value = property(fget=lambda self: float(self), fset=SetValue, fdel=SetDefault)


class BrushEditorWindow(pymui.Window):
    _brush = None

    def __init__(self):
        super(BrushEditorWindow, self).__init__(ID='BEW', Width=320, Height=100, CloseOnReq=True)

        # UI
        self.RootObject = topbox = pymui.VGroup()
        self.AddChild(topbox)
        
        # Brush preview
        self.bprev = BrushPreview()
        topbox.AddChild(self.bprev)
        
        # Brush parameters
        table = pymui.ColGroup(2)
        topbox.AddChild(table)

        self.prop = {}
        self.prop['radius_min'] = self._add_slider(table, 'radius_min', -2, 5, 3, .1, .5, islog=True)
        self.prop['radius_max'] = self._add_slider(table, 'radius_max', -2, 5, 3, .1, .5, islog=True)
        self.prop['yratio'] = self._add_slider(table, 'yratio', 1.0, 32., 1., 0.1, 2)
        self.prop['spacing'] = self._add_slider(table, 'spacing', 0.01, 4.0, 0.25, .01, 0.1)
        self.prop['opacity_min'] = self._add_slider(table, 'opacity_min', 0, 1, 1, 1/255., 10/255.)
        self.prop['opacity_max'] = self._add_slider(table, 'opacity_max', 0, 1, 1, 1/255., 10/255.)
        self.prop['opa_comp'] = self._add_slider(table, 'opa_comp', 0, 2, .9, 0.01, 0.1)
        self.prop['hardness'] = self._add_slider(table, 'hardness', 0, 1, 1, .01, 0.1)
        self.prop['erase'] = self._add_slider(table, 'erase', 0, 1, 1, .01, 0.1)
        self.prop['grain'] = self._add_slider(table, 'grain', 0, 1, 1, .01, 0.1)
        self.prop['radius_random'] = self._add_slider(table, 'radius_random', 0, 1, 0, .1, 0.2)
        self.prop['motion_track'] = self._add_slider(table, 'motion_track', 0.0, 2.0, 1.0, .1, 1)
        self.prop['hi_speed_track'] = self._add_slider(table, 'hi_speed_track', 0.0, 2.0, 0.0, .01, 0.1)
        self.prop['smudge'] = self._add_slider(table, 'smudge', 0, 1, 1, .01, 0.1)
        self.prop['smudge_var'] = self._add_slider(table, 'smudge_var', 0, 1, 1, .01, 0.1)

        self.Title = 'Brush Editor'

    def _add_slider(self, table, label, vmin, vmax, vdef, step, page_step, islog=False):
        lb = pymui.Label(label+':')

        vdef = vdef if not islog else log(vdef)

        hs = FloatValue(vmin, vmax, vdef,cb=self._on_value_changed, cb_args=(label,), islog=islog)

        table.AddChild(lb)
        table.AddChild(hs)

        return hs

    def _format_value(self, widget, value):
        return str(round(exp(value), 2))

    def _on_value_changed(self, widget, name):
        if self._brush:
            v = widget.value
            setattr(self._brush, name, v)
            self.bprev.set_attr(name, v)

            # FIXME: this call should be in a mediator or proxy, not in the component itself!
            self.mediator.sendNotification(main.Gribouillis.BRUSH_PROP_CHANGED, (self._brush, name))

    def brush_changed_prop(self, name, value):
        if name == 'color': return
        if name in self.prop:
            hs = self.prop[name]
            hs.value = value

    def _set_brush(self, brush):
        self._brush = None # forbid brush prop changed events, so a endless loop

        # Update the UI
        for name in self.prop.iterkeys():
            self.brush_changed_prop(name, getattr(brush, name))

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

    @mvcHandler(main.Gribouillis.BRUSH_PROP_CHANGED)
    def _on_doc_brush_prop_changed(self, brush, name):
        if self.viewComponent.brush is not brush: return
        self.viewComponent.brush_changed_prop(name, getattr(brush, name))
