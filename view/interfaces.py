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

class EventParserI:
    """EventParserI : Interface class

    Used to define default methods for EventParser implementation.
    EventParser classes are OS dependent and used to convert an
    OS event into application's states.
    These states are stored into EventParser instance objects.
    When the event is consummed, the application deletes the object.
    """

    def init(self, event, classname):
        self._evt = None
        self._time = None
        self._mods = None
        self._key = None
        self._cur_pos = None
        self._cur_xtilt = None
        self._cur_ytilt = None
        self._pressure = None
        self._evt = event
        self.classname = classname

    def __hash__(self):
        return self.classname

    def __str__(self):
        return self.classname

    def get_time(self):
        pass

    def get_mods(self):
        """Return a string containing zero or more following elements,
        separated by a space: 'shift', 'control', 'alt', 'command'.
        When the OS handles same modificator keys and diffenciates them
        a number is added at the end, like 'alt2'.
        """
        pass

    def get_pressure(self):
        """Return cursor pressure if supported.
        Value is a float number in [0.0, 1.0] range.
        None if not supported or no event.
        """
        pass

    def get_cursor_position(self):
        pass

    def get_cursor_xtilt(self):
        pass

    def get_cursor_ytilt(self):
        pass

    fullname = property(fget=lambda self: self.get_fullname())
    time = property(fget=lambda self: self.get_time())
    mods = property(fget=lambda self: self.get_mods())
    pressure = property(fget=lambda self: self.get_pressure())
    cpos = property(fget=lambda self: self.get_cursor_position())
    xtilt = property(fget=lambda self: self.get_cursor_xtilt())
    ytilt = property(fget=lambda self: self.get_cursor_ytilt())
