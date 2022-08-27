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

"""This module implement a class to uniquely represent
a GTK event (keys, mouse motion, ...).
This object is used jointly with view.Context as mapping keys.
"""

from gi.repository import Gdk as gdk


class GdkEventParser:
    __bad_devices = []

    @staticmethod
    def get_time(evt):
        # GDK timestamp in milliseconds
        return evt.time * 1e-3

    @staticmethod
    def get_cursor_position(evt):
        return int(evt.x), int(evt.y)

    @staticmethod
    def get_cursor_xtilt(evt):
        return evt.get_axis(gdk.AxisUse.XTILT) or 0.0

    @staticmethod
    def get_cursor_ytilt(evt):
        return evt.get_axis(gdk.AxisUse.YTILT) or 0.0

    @classmethod
    def get_pressure(cls, evt):
        # Is pressure value not in supposed range?
        p = evt.get_axis(gdk.AxisUse.PRESSURE)
        if p is not None:
            if p < 0.0 or p > 1.0:
                if evt.device.name not in cls.__bad_devices:
                    print('WARNING: device "%s" is reporting bad pressure %+f' % (evt.device.name, p))
                    cls.__bad_devices.append(evt.device.name)
                    # Over limits?
                if p < -10000.0 or p > 10000.0:
                    p = 0.5
        else:
            p = 0.5

        return p
