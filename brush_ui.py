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

from pymui import *
from pymui.mcc import laygroup
from brush import DrawableBrush

global lang

__all__ = ('BrushSelectWindow', 'BrushEditorWindow')

class BrushSelectWindow(Window):
    def __init__(self, title):
        super(BrushSelectWindow, self).__init__(title, ID="BSEL",
                                                RightEdge=64, BottomEdge=64,
                                                Width=6*DrawableBrush.BRUSH_SCALE,
                                                Height=12*DrawableBrush.BRUSH_SCALE)

        self.brush = DrawableBrush()
        self.brush.Notify('Name', MUIV_EveryTime, self.OnBrushChange)

        o = SimpleButton("Edit")
        o.Notify('Pressed', False, self.EditBrush)
        brush_group = VGroup(Child=(self.brush, o))

        self.obj_BName = Text(Frame=MUIV_Frame_Text, SetMin=False)
        info_group = VGroup(Child=(self.obj_BName, VSpace(0)))

        ro = VGroup()
        ro.AddChild(HGroup(Title="Current brush", Child=(brush_group, info_group)))
        ro.AddChild(Rectangle(HBar=True, FixHeight=8))
        self._bgroup = laygroup.LayGroup(SameSize=True, TopOffset=0, Spacing=0)
        ro.AddChild(self._bgroup)

        self.RootObject = ro

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

        self._value = String(MaxLen=7, Accept="0123456789.", Format='r', FixWidthTxt="-#.###")
        self._slider.Notify('Acknowledge', callback=self.OnStringValue, MUIV_TriggerValue)
        self._slider = Slider(Min=0, Max=1000)
        self._slider.Notify('Value', callback=self.OnSliderValue, MUIV_TriggerValue)
        self.AddChild(self._value, self._slider)

    def _as_float(self, value):
        return value*self._range + self._min

    def _as_str(self, value):
        return "%.3g" % value

    def __float__(self):
        return self._as_float(self._slider.Value)

    def __str__(self):
        return "%.3g" % float(self)

    def OnSliderValue(self, value):
        value = self._as_float(value)
        self._value.NNset('Contents', self._as_str(value))
        if self._cb:
            self._cb(value, *self._cb_args)
            
    def OnStringValue(self, value):
        self.value = value

    def SetValue(self, value):
        self._slider.Value = min(1000, max(0, int((value-self._min)*1000)))

    def SetDefault(self):
        self.value = self._default

    value = property(fget=lambda self: float(self), fset=SetValue, fdel=SetDefault)

    
class BrushEditorWindow(Window):
    def __init__(self, title):
        ro = ColGroup(4)
        super(BrushEditorWindow, self).__init__(title, ID="BrushEditor", RootObject=ro)

        self._obj = {}

        def Buttons(obj):
            b1 = SimpleButton("R")
            b1.Notify('Pressed', False, self.ResetValue, obj)
            b2 = SimpleButton("F(x)")
            b2.Notify('Pressed', False, self.OpenFxWin, obj)
            return b1, b2

        o = self._obj['radius'] = FloatValue(min=0.1, max=128, default=2.0,
                                              cb=self.OnFloatChange, cb_args='radius',
                                              ShortHelp=lang.ShortHelp_BrushEditor_Radius)
        ro.AddChild(Label('Radius:'), o, Buttons(o))

        o = self._obj['yratio'] = FloatValue(min=0.1, max=100, default=1.0,
                                              ShortHelp=lang.ShortHelp_BrushEditor_YRatio)
        ro.AddChild(Label('Radius Y-ratio:'), o, Buttons(o))

        o = self._obj['hardness'] = FloatValue(min=0.0, max=1.0, default=0.5)
        ro.AddChild(Label('Hardness:'), o) + Buttons(o))

    def SetBrush(self, brush):
        self.brush = brush
        self._obj['radius'].value = brush.base_radius
        self._obj['yratio'].value = brush.base_yratio
        self._obj['hardness'].value = brush.hardness

    def OnFloatChange(self, value, n):
        if n == 'radius':
            brush.base_radius = value
        elif n == 'yratio':
            brush.base_yratio = value
        elif n == 'hardness':
            brush.hardness = value

    def OpenFxWin(self, obj):
        pass

    def ResetValue(self, obj):
        del obj.value
