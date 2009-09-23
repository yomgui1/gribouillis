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

clamp = lambda m, x, M: max(min(x, M), m)

class ColorChooser(Window):
    __default_color = (0.0,) * 3
    
    def __init__(self, title):
        self.watchers = []
        
        super(ColorChooser, self).__init__(title, ID="COL0", RightEdge=64, TopEdge=64)

        top = VGroup()
        self.RootObject = top

        self._colstr = String(Accept="0123456789abcdefABCDEF#",
                              MaxLen=8,
                              FixWidthTxt="#000000*",
                              Frame=MUIV_Frame_String)

        g = ColGroup(2)
        g.AddChild(Text("Hex value:", Weight=0), self._colstr)

        g = HGroup(Child=(g, HSpace(0)))

        self.coladj = Coloradjust()
        bar = Rectangle(Weight=0, HBar=True)

        top.AddChild(self.coladj, bar, g)

        self.coladj.Notify('RGB', MUIV_EveryTime, self.OnColorChanged)
        self._colstr.Notify('Acknowledge', MUIV_EveryTime, self.OnColStrChanged)

        self.color = ColorChooser.__default_color

    @staticmethod
    def SysColToFloat(v):
        return float(clamp(0, v / 0x01010101, 255)) / 255.

    @staticmethod
    def FloatToSysCol(v):
        return clamp(0, int(v * 0xff) * 0x01010101, 255)

    def OnColStrChanged(self):
        s = self._colstr.Contents
        if not s:
            self._colstr.Contents = self._colstr_save
        else:
            if s[0] == '#':
                c = long(s[1:], 16)
            else:
                c = long(s)
            self.color = (self.SysColToFloat((c>>16)&0xff), self.SysColToFloat((c>>8)&0xff), self.SysColToFloat(c&0xff))

    def OnColorChanged(self):
        rgb = self.coladj.RGB
        self._color = tuple(self.SysColToFloat(x) for x in rgb)
        self._colstr_save = "#%02x%02x%02x" % tuple((x >> 24) for x in rgb)
        self._colstr.Contents = self._colstr_save

        for cb in self.watchers:
            cb(self._color)

    def SetColor(self, *rgb):
        if len(rgb) == 3:
            rgb = tuple(self.clamp(0.0, float(x), 1.0) for x in rgb)
        elif isinstance(rgb[0], float):
            rgb = tuple(clamp(0.0, float(rgb[0]), 1.0)) * 3
        else:
            rgb = tuple(clamp(0.0, float(x), 1.0) for x in rgb[0])

        # will call OnColorChanged()
        self.coladj.RGB = tuple(self.FloatToSysCol(x) for x in rgb)

    def DelColor(self):
        self.color = self.default_color

    color = property(fget=lambda self: self._color, fset=SetColor, fdel=DelColor)

    def add_watcher(self, cb):
        if cb not in self.watchers:
            self.watchers.append(cb)

    def rem_watcher(self, cb):
        self.watchers.remove(cb)

