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

import os
from pymui import MUIV_InputMode_Toggle, MUIV_Frame_ImageButton, Dtpic
import _brush

MUIA_Dtpic_Scale = 0x8042ca4c  # private

class Brush(Dtpic):
    BRUSH_SCALE = 48

    def __init__(self):
        super(Brush, self).__init__(InputMode=MUIV_InputMode_Toggle, Frame=MUIV_Frame_ImageButton)
        self._set(MUIA_Dtpic_Scale, self.BRUSH_SCALE)
        self._color = (0, 0, 0)
        self.shortname = ''

        # Brush model (features + drawing routines)
        self._brush = _brush.Brush()

    def load(self, search_paths, name):
        fullname = name + '_prev.png'
        
        for path in search_paths:
            filename = os.path.join(path, fullname)
            if not os.path.isfile(filename): continue

            self.shortname = name
            self.Name = filename
            return
        
        raise RuntimeError('brush "' + name + '" not found')

    def set_color(self, color):
        self._color = color

    color = property(fget=lambda self: self._color, fset=set_color)

    def copy(self, brush):
        self.shortname = brush.shortname
        self.color = brush.color
        self.Name = brush.Name # in last because can trig some notification callbacks

    def InitDraw(self, sf, x, y):
        self._brush.surface = sf

    def Draw(self, x, y, dx, dy, p=0.5, xtilt=0.0, ytilt=0.0):
        self._brush.draw(x, y, dx, dy, p, 8.0, 1.8)
        return ()
