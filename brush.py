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

__all__ = ('Brush', 'DummyBrush')

import os
from pymui import MUIV_InputMode_Toggle, MUIV_Frame_ImageButton, Dtpic
import _brush, functools

MUIA_Dtpic_Scale = 0x8042ca4c  # private

class Brush(Dtpic):
    BRUSH_SCALE = 48
    DEFAULT_COLOR = (0.0, )*3

    def __init__(self):
        super(Brush, self).__init__(InputMode=MUIV_InputMode_Toggle, Frame=MUIV_Frame_ImageButton)
        self._set(MUIA_Dtpic_Scale, self.BRUSH_SCALE, 'I')
        self.shortname = ''
        self.base_radius = 4.61
        self.base_yratio = 1.0
        self.hardness = 0.5
        self.color = self.DEFAULT_COLOR

    def load(self, search_paths, name):
        fullname = name + '_prev.png'
        
        for path in search_paths:
            filename = os.path.join(path, fullname)
            if not os.path.isfile(filename): continue

            self.shortname = name
            self.Name = filename
            return
        
        raise RuntimeError('brush "' + name + '" not found')

    def copy(self, brush):
        self.shortname = brush.shortname
        self.color = brush.color
        self.Name = brush.Name # in last because can trig some notification callbacks

    def get_color(self):
        return self._color

    def set_color(self, color):
        self._color = color

    def del_color(self):
        self.set_color(self.DEFAULT_COLOR)

    color = property(fget=get_color, fset=set_color, fdel=functools.partial(set_color, DEFAULT_COLOR))


class DrawableBrush(Brush):
    def __init__(self):
        # Brush model (features + drawing routines) 
        self._brush = _brush.Brush()
        super(DrawableBrush, self).__init__()
        
    def copy(self, brush):
        self._brush.base_radius = brush.base_radius
        self._brush.base_yratio = brush.base_yratio
        self._brush.hardness = brush.hardness
        super(DrawableBrush, self).copy(brush)
            
    def InitDraw(self, sf, pos):
        self._brush.invalid_cache()
        self._brush.surface = sf
        self._brush.x, self._brush.y = pos

    def DrawStroke(self, stroke):
        return self._brush.draw_stroke(stroke)

    def DrawSolidDab(self, pos, pressure=0.5):
        return self._brush.drawdab_solid(pos, pressure, 0.6)

    def get_color(self):
        return self._brush.red, self._brush.green, self._brush.blue

    def set_color(self, color):
        self._brush.red, self._brush.green, self._brush.blue = color

    def del_color(self):
        self.set_color(self.DEFAULT_COLOR)

    color = property(fget=get_color, fset=set_color, fdel=del_color)


class DummyBrush:
    "Class used when no brush is set for a model."
    def InitDraw(self, *a, **k):
        pass

    def DrawStroke(self, *a, **k):
        return tuple()

    def DrawSolidDab(self, *a, **k):
        return tuple()
