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

import os, array
from pymui import MUIV_InputMode_Toggle, MUIV_Frame_ImageButton, Dtpic, Rectangle
import _brush, functools

MUIA_Dtpic_Scale = 0x8042ca4c  # private

class Brush(Dtpic):
    BRUSH_SCALE = 48
    DEFAULT_COLOR = (0.0, )*3

    def __init__(self):
        super(Brush, self).__init__(InputMode=MUIV_InputMode_Toggle, Frame=MUIV_Frame_ImageButton)
        self._set(MUIA_Dtpic_Scale, self.BRUSH_SCALE)
        self.shortname = ''
        self._states = array.array('f', (0.0, )*_brush.BASIC_VALUES_MAX)
        self.color = self.DEFAULT_COLOR
        
        del self.states

    def load(self, search_paths, name):
        if name.endswith('.png'):
            fullname = name
            name = os.path.splitext(os.path.basename(name))[0]
        else:
            fullname = name + '_prev.png'
        
        for path in search_paths:
            filename = os.path.join(path, fullname)
            if not os.path.isfile(filename): continue

            self.shortname = name
            self.Name = filename
            return
        
        raise RuntimeError('brush "' + name + '" not found')


    def _get_states(self):
        return self._states.tostring()

    def _set_states(self, states):
        assert len(states) == len(self._states.tostring())
        self._states = array.array('f', states)

    def _set_default_states(self):
        self.radius = 2.0
        self.yratio = 1.0
        self.hardness = 0.5
        self.opacity = 1.0
        self.erase = 1.0
        self.grain = 0.0
        self.radius_random = 0.0
        self.dabs_per_radius = 10.0

    states = property(fget=lambda self: self._get_states(),
                      fset=lambda self, s: self._set_states(s),
                      fdel=lambda self: self._set_default_states())

    def copy(self, brush):
        self.states = brush.states
        self.shortname = brush.shortname
        # color is not copied
        self.Name = brush.Name # in last because can trig some notification callbacks

    def get_color(self):
        return self._color

    def set_color(self, color):
        self._color = color

    def del_color(self):
        self.set_color(self.DEFAULT_COLOR)

    color = property(fget=get_color, fset=set_color, fdel=functools.partial(set_color, DEFAULT_COLOR))

    def get_state(self, i):
        return self._states[i]

    def set_state(self, i, state):
        self._states[i] = state

    radius = property(fget=lambda self: self.get_state(_brush.BV_RADIUS), fset=lambda self, v: self.set_state(_brush.BV_RADIUS, v))
    yratio = property(fget=lambda self: self.get_state(_brush.BV_YRATIO), fset=lambda self, v: self.set_state(_brush.BV_YRATIO, v))
    hardness = property(fget=lambda self: self.get_state(_brush.BV_HARDNESS), fset=lambda self, v: self.set_state(_brush.BV_HARDNESS, v))
    opacity = property(fget=lambda self: self.get_state(_brush.BV_OPACITY), fset=lambda self, v: self.set_state(_brush.BV_OPACITY, v))
    erase = property(fget=lambda self: self.get_state(_brush.BV_ERASE), fset=lambda self, v: self.set_state(_brush.BV_ERASE, v))
    radius_random = property(fget=lambda self: self.get_state(_brush.BV_RADIUS_RANDOM), fset=lambda self, v: self.set_state(_brush.BV_RADIUS_RANDOM, v))
    dabs_per_radius = property(fget=lambda self: self.get_state(_brush.BV_DABS_PER_RADIUS), fset=lambda self, v: self.set_state(_brush.BV_DABS_PER_RADIUS, v))
    grain = property(fget=lambda self: self.get_state(_brush.BV_GRAIN_FAC), fset=lambda self, v: self.set_state(_brush.BV_GRAIN_FAC, v))


class DrawableBrush(Brush):
    def __init__(self):
        # Brush model (features + drawing routines) 
        self._brush = _brush.Brush()
        super(DrawableBrush, self).__init__()
        
    def InitDraw(self, sf, pos):
        self._brush.invalid_cache()
        self._brush.surface = sf
        self._brush.p1x, self._brush.p1y = pos
        self._brush.pressure = 0.0
        self._brush.start = 0
        self.ok = False

    def DrawStroke(self, stroke):
        if self.ok:
            return self._brush.draw_stroke(stroke)
        self._brush.p2x, self._brush.p2y = stroke['pos']
        self._brush.t1x = .5*(self._brush.p2x - self._brush.p1x)
        self._brush.t1y = .5*(self._brush.p2y - self._brush.p1y)
        self.ok = True
        return ()

    def DrawSolidDab(self, pos, pressure=0.5):
        return self._brush.drawdab_solid(pos, pressure, 0.6)

    def _get_states(self):
        return str(self._brush.get_states())

    def _set_states(self, states):
        self._brush.get_states()[:] = states

    def get_color(self):
        return self._brush.red, self._brush.green, self._brush.blue

    def set_color(self, color):
        self._brush.red, self._brush.green, self._brush.blue = color

    def del_color(self):
        self.set_color(self.DEFAULT_COLOR)

    color = property(fget=get_color, fset=set_color, fdel=del_color)

    def get_state(self, i):
        return self._brush.get_state(i)

    def set_state(self, i, state):
        self._brush.set_state(i, state)


class DummyBrush:
    "Class used when no brush is set for a model."
    def InitDraw(self, *a, **k):
        pass

    def DrawStroke(self, *a, **k):
        return tuple()

    def DrawSolidDab(self, *a, **k):
        return tuple()
