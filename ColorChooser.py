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
    default_color = (0, 0, 0) 
    
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
        g.AddChild(Text("Hex value:", Weight=0),
                   self._colstr)

        g = HGroup(Child=(g, HSpace(0)))

        self.coladj = Coloradjust()
        bar = Rectangle(Weight=0, HBar=True)

        top.AddChild(self.coladj, bar, g)

        self.coladj.Notify('RGB', MUIV_EveryTime, self.OnColorChanged)
        self._colstr.Notify('Acknowledge', MUIV_EveryTime, self.OnColStrChanged)

        self.color = (0, 0, 0)

    def OnColStrChanged(self):
        s = self._colstr.Contents
        if not s:
            self._colstr.Contents = self._colstr_save
        else:
            if s[0] == '#':
                c = long(s[1:], 16)
            else:
                c = long(s)
            self.color = c

    def OnColorChanged(self):
        self._color = self.coladj.RGB
        self._colstr_save = "#%s%s%s" % tuple(hex(x)[2:4] for x in self._color)
        self._colstr.Contents = self._colstr_save

        for cb in self.watchers:
            cb(self._color)

    def SetColor(self, *rgb):
        if len(rgb) == 3:
            r, g, b = rgb
        elif isinstance(rgb[0], (int, long)):
            c = rgb[0]
            r = (c >> 16) & 255
            g = (c >> 8) & 255
            b = c & 255
            del c
        else:
            r, g, b = rgb[0]

        r = clamp(0, r, 255)
        g = clamp(0, g, 255)
        b = clamp(0, b, 255)

        # Notify only after the blue
        self.coladj.RGB = (r << 24, g << 24, b << 24)

    def DelColor(self):
        self.color = self.default_color

    color = property(fget=lambda self: self._color, fset=SetColor, fdel=DelColor)

    def add_watcher(self, cb):
        if cb not in self.watchers:
            self.watchers.append(cb)

    def rem_watcher(self, cb):
        self.watchers.remove(cb)

