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

"""This module implement a class to uniquely represent
a GTK event (keys, mouse motion, ...).
This object is used jointly with view.Context as mapping keys.
"""

from gtk import gdk

from view.interfaces import EventParserI

class EventParser(EventParserI):
    __bad_devices = []

    def get_time(self):
        if self._time is None:
            # GDK timestamp in milliseconds
            self._time = self._evt.time * 1e-3
        return self._time

    def get_mods(self):
        if self._mods is None:
            mods = ''
            s = self._evt.state
            if s & gdk.CONTROL_MASK:
                mods += 'C-'
            if s & (gdk.MOD1_MASK|gdk.MOD5_MASK):
                mods += 'M-'
            if s & gdk.SHIFT_MASK:
                mods += 'S-'
            if s & gdk.MOD4_MASK:
                mods += 's-'
            self._mods = mods[:-1]
        return  self._mods

    def get_cursor_position(self):
        if self._cur_pos is None:
            self._cur_pos = (int(self._evt.x), int(self._evt.y))
        return self._cur_pos

    def get_cursor_xtilt(self):
        if self._cur_xtilt is None:
            self._cur_xtilt = self._evt.get_axis(gdk.AXIS_XTILT) or 0.
        return self._cur_xtilt

    def get_cursor_ytilt(self):
        if self._cur_ytilt is None:
            self._cur_ytilt = self._evt.get_axis(gdk.AXIS_YTILT) or 0.
        return self._cur_ytilt

    def get_pressure(self):
        if self._pressure is None:
            # Is pressure value not in supposed range?
            p = self._evt.get_axis(gdk.AXIS_PRESSURE)
            if p is not None:
                if p < 0. or p > 1.:
                    if self._evt.device.name not in self.__bad_devices:
                        print 'WARNING: device "%s" is reporting bad pressure %+f' % (evt.device.name, p)
                        self.__bad_devices.append(self._evt.device.name)
                        # Over limits?
                    if p < -10000. or p > 10000.:
                        p = .5
            else:
                p = .5
            self._pressure = p
        return self._pressure
