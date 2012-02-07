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

# Python 2.5 compatibility
from __future__ import with_statement

import os
import math

from math import sin, pi

import _brush
import _pixbuf

from devices import DeviceState
from colorspace import ColorSpaceRGB
from surface import BoundedPlainSurface

__all__ = ['Brush', 'DrawableBrush']

class Brush(object):
    """Brush base class"""

    __version__ = 2.5
    ALLBRUSHES = "brushes.data"
    PROPERTIES = 'radius_min radius_max yratio angle spacing opacity_min opacity_max opa_comp hardness erase grain'.split()
    PROPERTIES += 'motion_track hi_speed_track smudge smudge_var direction_jitter dab_pos_jitter dab_radius_jitter'.split()
    PROPERTIES += 'color_shift_h color_shift_v color_shift_s'.split()
    PROPERTIES += 'icon'.split()

    # default values = pen
    radius_min          = 1.0
    radius_max          = 1.5
    yratio              = 1.0
    angle               = 0.0
    erase               = 1.0
    grain               = 0.0
    spacing             = 0.25
    opacity_min         = 0.15
    opacity_max         = 1.0
    hardness            = 0.28
    opa_comp            = 1.2
    motion_track        = 0.5
    hi_speed_track      = 0.0
    smudge              = 0.0
    smudge_var          = 0.0
    color_shift_h       = 0.0
    color_shift_v       = 0.0
    color_shift_s       = 0.0
    dab_radius_jitter   = 0.0
    dab_pos_jitter      = 0.0
    direction_jitter    = 0.0
    icon                = None
    page                = None
    icon_preview        = None # runtime usage only, not saved

    def __init__(self, name='brush', icon=None, **kwds):
        self.name = name
        self.icon = icon
        self.__dict__.update(kwds)
        self._erase = 0 # temp save of erase

    @staticmethod
    def save_brushes(brushes):
        filename = Brush.ALLBRUSHES + '_'
        try:
            with open(filename, 'w') as file:
                file.write("%s\n" % Brush.__version__)
                for brush in brushes:
                    file.write("[brush]\n")
                    for prop in Brush.PROPERTIES + ['name', 'page']:
                        if prop == 'icon' and not brush.icon: continue
                        if prop == 'page' and not brush.page: continue
                        file.write("%s = %s\n" % (prop, getattr(brush, prop)))
                    file.write("\n")
        except Exception, e:
            print "[DBG] error during brushes saving:", e
            if os.path.isfile(filename):
                os.remove(filename)
        else:
            if os.path.isfile(Brush.ALLBRUSHES):
                os.remove(Brush.ALLBRUSHES)
            os.rename(filename, Brush.ALLBRUSHES)

    @staticmethod
    def load_brushes():
        l = []
        if os.path.isfile(Brush.ALLBRUSHES):
            try:
                with open(Brush.ALLBRUSHES, 'r') as file:
                    ver = float(file.readline())
                    if ver > Brush.__version__:
                        raise TypeError("Incompatible brushes file version")
                    brush = None
                    for line in file.readlines():
                        if line.strip().lower() == '[brush]':
                            brush = Brush()
                            l.append(brush)
                        elif brush and '=' in line:
                            attr, value = line.split('=')
                            attr = attr.strip().lower()
                            value = value.strip()
                            if attr != 'icon' and attr in Brush.PROPERTIES:
                                value = float(value)
                            else: # compatibility support
                                if ver <= 1.0:
                                    if attr == 'radius':
                                        value = float(value)
                                        setattr(brush, 'radius_min', value)
                                        attr = 'radius_max'
                                    elif attr == 'opacity':
                                        value = float(value)
                                        setattr(brush, 'opacity_min', value)
                                        attr = 'opacity_max'
                                if ver <= 2.2:
                                    if attr == 'icon' and value == 'None':
                                        value = None
                                if ver <= 2.4:
                                    if attr.startswith('smudge_add_'):
                                        continue
                                    
                            setattr(brush, attr, value)
            except Exception, e:
                print "[DBG] error during brushes loading:", e

        # Default brushes
        if not l:
            b = Brush('pen')
            l.append(b)
            b = Brush('chalk', radius_min=7.0, radius_max=7.0, opacity_min=.8, opacity_max=.8, hardness=0.3,
                      opa_comp=1.8, spacing=.5, grain=.8)
            l.append(b)

        return l

    def swap_erase(self):
        self.erase = 1 - self.erase
        
    def set_erase(self, value=1.0):
        self.erase = value
        
    def set_from_brush(self, brush):
        self.name = brush.name
        for name in Brush.PROPERTIES:
            setattr(self, name, getattr(brush, name))
        
class DrawableBrush(_brush.Brush, Brush):
    """Brush class used by documents"""

    tool = None # current tool used

    def start(self, surface, state):
        "Called at to start a new drawing path on given surface using given input device"
        self.surface = surface

        # Setup initial conditions
        self.stroke_start(state)

    def stop(self):
        "Finish the path"
        return self.stroke_end()
        
    def flush_area(self):
        "Get the modified area and reset it"
        pass

    def pixel_processor(self):
        "Return pixel processor function used for each pixel to draw"
        pass

    def gen_preview_states(self, width, height):
        assert width >= 32
        assert height >= 16
        
        y = height / 2
        r = height / 4
        size = width - 20
        
        for x in xrange(10, width-10):
            state = DeviceState()
            state.time = t = float(x-10)/size
            state.pressure = 1.0 - (2*t-1)**2
            state.vpos = (x, y + int(r*sin(2*t*pi)))
            state.xtilt = 1.0
            state.ytilt = 0.0
            state.angle = 0.0
            state.spos = state.vpos
            yield state
            
    def paint_rgb_preview(self, width, height, surface=None, states=None, fmt=_pixbuf.FORMAT_ARGB8_NOA):
        if surface is None:
            surface = BoundedPlainSurface(fmt, width, height)
            
        if states is None:
            states = list(self.gen_preview_states(width, height))

        surface.clear_value(1.0 if self.erase == 1.0 else 0.0)
        self.surface = surface
        self.stroke_start(states[0])
        for state in states:
            self.draw_stroke(state)
        self.stroke_end()
        
        return surface.get_rawbuf()
