###############################################################################
# Copyright (c) 2009 Guillaume Roguez
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

from languages import lang_dict
lang = lang_dict['default']

from pymui import *
from pymui.mcc import laygroup
from brush import DrawableBrush
import math, surface, _pixarray

__all__ = ('BrushSelectWindow', 'BrushEditorWindow')

class BrushSelectWindow(Window):
    def __init__(self, title):
        super(BrushSelectWindow, self).__init__(title, ID="BSEL",
                                                RightEdge=64, BottomEdge=64,
                                                Width=6*DrawableBrush.BRUSH_SCALE,
                                                Height=12*DrawableBrush.BRUSH_SCALE)

        top = VGroup()
        self.RootObject = top 

        self.brush = DrawableBrush()
        self.brush.Notify('Name', MUIV_EveryTime, self.OnBrushChange)

        o = SimpleButton("Edit")
        o.Notify('Pressed', False, self.EditBrush)
        brush_group = VGroup(Child=(self.brush, o))

        self.obj_BName = Text(Frame=MUIV_Frame_Text, SetMin=False)
        info_group = VGroup(Child=(self.obj_BName, VSpace(0)))
        
        top.AddChild(HGroup(Title="Current brush", Child=(brush_group, info_group)))
        top.AddChild(Rectangle(HBar=True, FixHeight=8))
        self._bgroup = laygroup.LayGroup(SameSize=True, TopOffset=0, Spacing=0)
        top.AddChild(self._bgroup)

    def OnBrushChange(self):
        self.obj_BName.Contents = self.brush.shortname

    def SetBrushes(self, brushes):
        self._bgroup.DoMethod(MUIM_Group_InitChange)
        self._bgroup.AddChild(lock=True, *brushes)
        self._bgroup.DoMethod(MUIM_Group_ExitChange)

    def EditBrush(self):
        if not hasattr(self, '_editor'):
            self._editor = BrushEditorWindow("Brush Editor")
            self.ApplicationObject.AddWindow(self._editor)
            self._editor.Notify('CloseRequest', True, self._editor.Close)
        self._editor.SetBrush(self.brush)
        self._editor.Open()


class BrushPreview(Area):
    WIDTH = 200
    HEIGHT = 96

    def __init__(self):
        super(BrushPreview, self).__init__(MCC=True, FillArea=False)
        self._rsurface = surface.BoundedSurface(self.WIDTH, self.HEIGHT, 'RGB8')
        self._rbuf = self._rsurface.GetBuffer(0, 0, read=False)
        self._rbuf.one()
        self._brush = DrawableBrush()

    def MCC_AskMinMax(self, minw, defw, maxw, minh, defh, maxh):
        w = minw + self.WIDTH
        h = minh + self.HEIGHT
        return w, w, w, h, h, h

    def MCC_Draw(self, flags):
        if flags & MADF_DRAWOBJECT == 0: return
        self._rp.Blit8(self._rbuf, self.MLeft, self.MTop, self.WIDTH, self.HEIGHT)

    def DrawBrush(self, brush):
        self._rbuf.one()
        b = self._brush
        b.copy(brush)
        b.color = (0.0, )*3

        w = int(self.WIDTH * 3.0 / 4)
        h = self.HEIGHT / 2
        stroke = dict(time=0.0)
        b.InitDraw(self._rsurface, (self.WIDTH/8, h))

        for i in xrange(w+1):
            fx = float(i)/w
            x = i + self.WIDTH/8
            y = int(h + (h/2)*math.sin(fx*math.pi*2))
            stroke['pos'] = (x, y)
            stroke['pressure'] = (fx**2-fx**3)*6.75
            b.DrawStroke(stroke)
        
        self.Redraw()


class FloatValue(Group):
    def __init__(self, min, max, default=None, cb=None, cb_args=(), **kwds):
        super(FloatValue, self).__init__(Horiz=True, **kwds)

        if default is None:
            default = min
        
        assert min < max and min <= default and max >= default

        self._min = min
        self._range = (max - min)/1000.
        self._default = default

        self._cb = cb
        self._cb_args = cb_args

        self._value = String(MaxLen=7, Accept="0123456789.", Format='r', FixWidthTxt="-#.###", Background=None)
        self._value.Notify('Acknowledge', MUIV_EveryTime, self.OnStringValue, MUIV_TriggerValue)
        self._slider = Slider(Min=0, Max=1000)
        self._slider.Notify('Value', MUIV_EveryTime, self.OnSliderValue, MUIV_TriggerValue)
        self.AddChild(self._value, self._slider)

        self.value = default

    def _as_float(self, value):
        return value*self._range + self._min

    def _as_str(self, value):
        return "%.3g" % value

    def __float__(self):
        return self._as_float(self._slider.Value)

    def __str__(self):
        return "%.3g" % float(self)

    def OnSliderValue(self, value, *args):
        value = self._as_float(value)
        self._value.NNSet('Contents', self._as_str(value))
        if self._cb:
            self._cb(value, *self._cb_args)
            
    def OnStringValue(self, value):
        self.value = value

    def SetValue(self, value):
        self._slider.Value = min(1000, max(0, int((value-self._min)/self._range)))

    def SetDefault(self):
        self.value = self._default

    value = property(fget=lambda self: float(self), fset=SetValue, fdel=SetDefault)


class PercentSlider(Slider):
    def __init__(self, min, max, default=None, cb=None, cb_args=(), **kwds):
        super(PercentSlider, self).__init__(Min=0, Max=100, **kwds)
  
        if default is None:
            default = min
        
        assert min < max and min <= default and max >= default

        self._min = min
        self._range = (max - min)/100.
        self._default = default

        self._cb = cb
        self._cb_args = cb_args

        self.Notify('Value', MUIV_EveryTime, self.OnValue)

        self.value = default   

    def __float__(self):
        return self.Value*self._range + self._min

    def OnValue(self, *args):
        if self._cb:
            self._cb(float(self), *self._cb_args)

    def SetValue(self, value):
        self.Value = min(100, max(0, int((value-self._min)/self._range)))

    def SetDefault(self):
        self.value = self._default

    value = property(fget=lambda self: float(self), fset=SetValue, fdel=SetDefault)
    

class BrushEditorWindow(Window):
    def __init__(self, title):
        ro = VGroup()
        super(BrushEditorWindow, self).__init__(title, ID="BrushEditor", RootObject=ro)

        self._obj = {}
        self._brush = None

        self._prev = BrushPreview()
        ro.AddChild(HCenter(self._prev), HBar(4))

        top = ColGroup(4)
        ro.AddChild(top)

        def Buttons(obj):
            b1 = SimpleButton("R")
            b1.HorizWeight = 0; b1.CycleChain = True
            b1.Notify('Pressed', False, self.ResetValue, obj)
            b2 = SimpleButton("F(x)")
            b2.HorizWeight = 0; b2.CycleChain = True
            b2.Notify('Pressed', False, self.OpenFxWin, obj)
            return b1, b2

        o = self._obj['radius'] = FloatValue(min=-2.0, max=4.0, default=0.91,
                                             cb=self.OnFloatChange, cb_args=('radius',),
                                             ShortHelp=lang.ShortHelp_BrushEditor_Radius)
        top.AddChild(Label('Radius:'), o, *Buttons(o))

        o = self._obj['yratio'] = FloatValue(min=0.0, max=2.0, default=0.0,
                                             cb=self.OnFloatChange, cb_args=('yratio',),
                                             ShortHelp=lang.ShortHelp_BrushEditor_YRatio)
        top.AddChild(Label('Radius Y-ratio:'), o, *Buttons(o))

        o = self._obj['hardness'] = PercentSlider(min=0.0, max=1.0, default=0.5,
                                                  cb=self.OnFloatChange, cb_args=('hardness',))
        top.AddChild(Label('Hardness:'), o, *Buttons(o))

        o = self._obj['opacity'] = PercentSlider(min=0.0, max=1.0, default=1.0,
                                                 cb=self.OnFloatChange, cb_args=('opacity',))
        top.AddChild(Label('Opacity:'), o, *Buttons(o))

        o = self._obj['erase'] = PercentSlider(min=0.0, max=1.0, default=1.0,
                                              cb=self.OnFloatChange, cb_args=('erase',),)
        top.AddChild(Label('Erase:'), o, *Buttons(o))

        o = self._obj['rad_rand'] = PercentSlider(min=0.0, max=10.0, default=0.0,
                                                  cb=self.OnFloatChange, cb_args=('rad_rand',))
        top.AddChild(Label('Radius Randomize:'), o, *Buttons(o))


    def SetBrush(self, brush):
        self._brush = brush
        self._obj['radius'].value = math.log(brush.radius)
        self._obj['yratio'].value = math.log(brush.yratio)
        self._obj['hardness'].value = brush.hardness
        self._obj['opacity'].value = brush.opacity
        self._obj['erase'].value = brush.erase
        self._obj['rad_rand'].value = brush.radius_random

    def OnFloatChange(self, value, n):
        if self._brush is None: return

        if n == 'radius':
            self._brush.radius = math.exp(value)
        elif n == 'yratio':
            self._brush.yratio = math.exp(value)
        elif n == 'hardness':
            self._brush.hardness = value
        elif n == 'opacity':
            self._brush.opacity = value
        elif n == 'erase':
            self._brush.erase = value
        elif n == 'rad_rand':
            self._brush.radius_random = value
   
        self._prev.DrawBrush(self._brush)

    def OpenFxWin(self, obj):
        pass

    def ResetValue(self, obj):
        del obj.value
