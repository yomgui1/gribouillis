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

import pymui

from math import log, exp

import model
import view
import main
import utils

from model import _pixbuf
from model.surface import BoundedPlainSurface
from model.colorspace import ColorSpaceRGB
from model.brush import DrawableBrush
from utils import _T


__all__ = [ 'BrushEditorWindow' ]

class BrushPreview(pymui.Area):
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
            buf = self._surface.get_rawbuf()
            self._rp.Blit8(buf, buf.stride, self.MLeft, self.MTop, self.MWidth, self.MHeight, 0, 0, True)
            
    def __init__(self, dv=None):
        super(BrushPreview, self).__init__(InnerSpacing=(0,)*4,
                                           Frame='Virtual',
                                           DoubleBuffer=True)
                                           
        # surface used for brush preview
        self._surface = BoundedPlainSurface(_pixbuf.FORMAT_ARGB8, BrushPreview.WIDTH, BrushPreview.HEIGHT)
        self._brush = DrawableBrush()
        self._brush.rgb = (0,0,0)
        self._states = list(self._brush.gen_preview_states(BrushPreview.WIDTH,
                                                           BrushPreview.HEIGHT))
        self.Background = "5:" + utils.resolve_path(main.Gribouillis.TRANSPARENT_BACKGROUND)
                
    def stroke(self, v=1.0):
        buf = self._brush.paint_rgb_preview(BrushPreview.WIDTH, BrushPreview.HEIGHT,
                                            surface=self._surface, states=self._states)
        self.Redraw()
        return buf
        
    def set_attr(self, name, v):
        if name == 'smudge': return
        setattr(self._brush, name, v)
        self._curbrush.icon_preview = self.stroke()
        
    def set_from_brush(self, brush):
        self._brush.set_from_brush(brush)
        self._brush.smudge = 0.
        self._curbrush = brush
        brush.icon_preview = self.stroke()
        
class FloatSlider(pymui.Slider):
    _MCC_ = 1
    
    def __init__(self, fmin, frange, islog, **k):
        super(FloatSlider, self).__init__(Min=0, Max=1000, CycleChain=True, **k)
        self._fmin = fmin
        self._frange = frange
        self._islog = islog
    
    @pymui.muimethod(pymui.MUIM_Numeric_Stringify)
    def MCC_Stringify(self, msg):
        msg.DoSuper()
        v = self._fmin + msg.value.value*self._frange
        if self._islog:
            v = exp(v)
        return pymui.c_STRPTR('%.3f' % v)
    
class FloatValue(pymui.Group):
    def __init__(self, min, max, default=None, cb=None, cb_args=(), islog=False, **kwds):
        super(FloatValue, self).__init__(Horiz=True, **kwds)

        if default is None:
            default = min

        assert min < max and min <= default and max >= default

        self.islog = islog
        self._min = min
        self._max = max
        self._range = (max - min)/1000.
        self._default = default

        self._cb = cb
        self._cb_args = cb_args

        self._value = pymui.String(MaxLen=7, Accept="0123456789.", Format='r', FixWidthTxt="-##.###",
                                   Frame='String', Background=None, CycleChain=True)
        self._value.Notify('Acknowledge', self.OnStringValue)
        self._slider = FloatSlider(self._min, self._range, islog)
        self._slider.Notify('Value', self.OnSliderValue)
        self.AddChild(self._value, self._slider)
        
        reset = pymui.SimpleButton(_T('R'), ShortHelp=_T('Reset value'), CycleChain=True, Weight=0)
        self.AddChild(reset)
        
        reset.Notify('Pressed', lambda *a: self.SetDefault())
        
        del self.value

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

    def SetValue(self, value, notify=True):
        if self.islog:
            value = max(exp(self._min), min(value, exp(self._max)))
            value = log(value)
        else:
            value = max(self._min, min(value, self._max))
        if notify:
            self._slider.Value = min(1000, max(0, int((value-self._min)/self._range)))
        else:
            self._slider.NNSet('Value', min(1000, max(0, int((value-self._min)/self._range))))

    def SetDefault(self):
        self.value = self._default

    value = property(fget=lambda self: float(self), fset=SetValue, fdel=SetDefault)

class BrushEditorWindow(pymui.Window):
    _brush = None

    def __init__(self, name):
        super(BrushEditorWindow, self).__init__(name, ID='BEW', Width=320, Height=100, CloseOnReq=True)
        self.name = name

        # UI
        self.RootObject = topbox = pymui.VGroup()
        self.AddChild(topbox)
        
        # Brush preview
        self.bprev = BrushPreview()
        topbox.AddChild(self.bprev)
        
        self.namebt = pymui.String(Frame='String', CycleChain=True)
        topbox.AddChild(pymui.HGroup(Child=[pymui.Label(_T('Name')+':'), self.namebt ]))
        
        topbox.AddChild(pymui.HBar(2))
        
        # Brush parameters
        table = pymui.ColGroup(2)
        topbox.AddChild(table)

        self.prop = {}
        self.prop['radius_min']        = self._add_slider(table, 'radius_min', -2, 5, 3, .1, .5, islog=True)
        self.prop['radius_max']        = self._add_slider(table, 'radius_max', -2, 5, 3, .1, .5, islog=True)
        self.prop['yratio']            = self._add_slider(table, 'yratio', 1.0, 32., 1., 0.1, 2)
        self.prop['angle']             = self._add_slider(table, 'angle', -180., 180.0, 0.0, 0.5, 1)
        self.prop['spacing']           = self._add_slider(table, 'spacing', 0.01, 4.0, 0.25, .01, 0.1)
        self.prop['opacity_min']       = self._add_slider(table, 'opacity_min', 0, 1, 1, 1/255., 10/255.)
        self.prop['opacity_max']       = self._add_slider(table, 'opacity_max', 0, 1, 1, 1/255., 10/255.)
        self.prop['opa_comp']          = self._add_slider(table, 'opa_comp', 0, 2, .9, 0.01, 0.1)
        self.prop['hardness']          = self._add_slider(table, 'hardness', 0, 1, 1, .01, 0.1)
        self.prop['erase']             = self._add_slider(table, 'erase', 0, 1, 1, .01, 0.1)
        self.prop['grain']             = self._add_slider(table, 'grain', 0, 1, 1, .01, 0.1)
        self.prop['motion_track']      = self._add_slider(table, 'motion_track', 0.0, 2.0, 1.0, .1, 1)
        self.prop['hi_speed_track']    = self._add_slider(table, 'hi_speed_track', 0.0, 2.0, 0.0, .01, 0.1)
        self.prop['smudge']            = self._add_slider(table, 'smudge', 0, 1, 0, .01, 0.1)
        self.prop['smudge_var']        = self._add_slider(table, 'smudge_var', 0, 1, 0, .01, 0.1)
        self.prop['color_shift_h']     = self._add_slider(table, 'color_shift_h', -.1, .1, 0, .01, 0.1)
        self.prop['color_shift_s']     = self._add_slider(table, 'color_shift_s', -.1, .1, 0, .01, 0.1)
        self.prop['color_shift_v']     = self._add_slider(table, 'color_shift_v', -.1, .1, 0, .01, 0.1)
        self.prop['dab_radius_jitter'] = self._add_slider(table, 'dab_radius_jitter', 0.0, 1.0, 0.0, .01, 0.1)
        self.prop['dab_pos_jitter']    = self._add_slider(table, 'dab_pos_jitter', 0.0, 5.0, 0.0, .01, 0.1)
        self.prop['direction_jitter']  = self._add_slider(table, 'direction_jitter', 0.0, 1.0, 0.0, .01, 0.1)
        self.prop['alpha_lock']        = self._add_slider(table, 'alpha_lock', 0.0, 1.0, 0.0, 1.0, 1.0)

        self.Title = 'Brush Editor'
        
        # overwritten by mediator
        self.on_value_changed_cb = utils.idle_cb

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
            self.bprev.set_attr(name, v)
            self.on_value_changed_cb(self._brush, name, v)

    def brush_changed_prop(self, name, value):
        if name == 'color': return
        if name in self.prop:
            hs = self.prop[name]
            hs.SetValue(value, False) # NNset() used

    def _set_brush(self, brush):
        self._brush = None # forbid brush prop changed events, so a endless loop

        # Update the UI
        for name in self.prop.keys():
            self.brush_changed_prop(name, getattr(brush, name))

        self._brush = brush
        self.bprev.set_from_brush(brush)
        self.namebt.NNSet('Contents', brush.name)
        
    brush = property(fget=lambda self: self._brush, fset=_set_brush)

