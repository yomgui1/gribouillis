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

from gtk import gdk

from view.interfaces import EventParserI

_KEYVALS = { 0x0020: 'space',
             0xfe03: 'ralt',
             0xff08: 'backspace',
             0xff09: 'tab',
             0xff0d: 'enter',
             0xff13: 'pause',
             0xff14: 'scrolllock',
             0xff1b: 'esc',
             0xff50: 'home',
             0xff51: 'left',
             0xff52: 'up',
             0xff53: 'right',
             0xff54: 'down',
             0xff55: 'page_up',
             0xff56: 'page_down',
             0xff57: 'end',
             0xff63: 'insert',
             0xff67: 'menu',
             0xff7f: 'numlock',
             0xff8d: 'return',
             0xffbe: 'f1',
             0xffbf: 'f2',
             0xffc0: 'f3',
             0xffc1: 'f4',
             0xffc2: 'f5',
             0xffc3: 'f6',
             0xffc4: 'f7',
             0xffc5: 'f8',
             0xffc6: 'f9',
             0xffc7: 'f10',
             0xffc8: 'f11',
             0xffc9: 'f12',
             0xffe1: 'lshift',
             0xffe2: 'rshift',
             0xffe3: 'lcontrol',
             0xffe4: 'rcontrol',
             0xffe5: 'capslock',
             0xffe9: 'lalt',
             0xffeb: 'lcommand',
             0xffec: 'rcommand',
             0xffff: 'delete',
             }

class EventParser(EventParserI):
    __bad_devices = []
    
    def __init__(self, event):
        self._event = event

    def get_time(self):
        if self._time is None
            self._time = evt.time * 1e-3 # GDK timestamp in milliseconds
        return self._time
    
    def get_modificators(self):
        if self._mods is None:
            self._mods = mods = []
            state = self._event.state
            if state & gdk.MOD1_MASK:
                mods.append('alt1')
            if state & gdk.MOD5_MASK:
                mods.append('alt2')
            if state & gdk.CONTROL_MASK:
                mods.append('control')
            if state & gdk.SHIFT_MASK:
                mods.append('shift')
            if state & gdk.MOD4_MASK:
                mods.append('command')
        return ' '.join(self._mods) or None
    
    def get_key(self):
        if self._key is None:
            if self._event.type == gdk.MOTION_NOTIFY:
                key = 'cursor_move'
            elif self._event.type == gdk.ENTER_NOTIFY:
                key = 'cursor_enter'
            elif self._event.type == gdk.LEAVE_NOTIFY:
                key = 'cursor_leave'
            elif self._event.type in (gdk.BUTTON_PRESS, gdk.BUTTON_RELEASE):
                if self._event.button == 1:
                    key = 'mouse_left'
                elif self._event.button == 2:
                    key = 'mouse_middle'
                elif self._event.button == 3:
                    key = 'mouse_right'
                elif self._event.button == 4:
                    key = 'mouse_fourth'
                else:
                    key = ''
            elif self._event.type in (gdk.KEY_PRESS, gdk.KEY_RELEASE):
                key = _KEYVALS.get(self._event.keyval)
                if not key:
                    if key <= 0xff:
                        key = chr(self._event.keyval).lower()
                    else:
                        key = hex(self._event.keyval)
            elif self._event.type == gdk.SCROLL:
                if self._event.direction == gdk.SCROLL_UP:
                    key = 'wheel_up'
                elif self._event.direction == gdk.SCROLL_DOWN:
                    key = 'wheel_down'
                else:
                    key = ''
            else:
                print '[*DBG*] unknown event type:', self._event.type
                key = ''
            self._key = key
        return self._key

    def get_screen_position(self):
        if self._scr_pos is None:
            self._scr_pos = self.get_pointer()
        return self._scr_pos

    def get_cursor_position(self):
        if self._cur_pos is None:
            self._cur_pos = (evt.get_axis(gdk.AXIS_X)), int(evt.get_axis(gdk.AXIS_Y))
        return self._cur_pos

    def get_cursor_xtilt(self):
        if self._cur_xtilt is None:
            self._cur_xtilt = evt.get_axis(gdk.AXIS_XTILT) or 0.
        return self._cur_xtilt

    def get_cursor_ytilt(self):
        if self._cur_ytilt is None:
            self._cur_ytilt = evt.get_axis(gdk.AXIS_YTILT) or 0.
        return self._cur_ytilt

    def get_pressure(self):
        if self._pressure is None:
            # Is pressure value not in supposed range?
            p = self._event.get_axis(gdk.AXIS_PRESSURE)
            if p is not None:
                if p < 0. or p > 1.:
                    if evt.device.name not in self.__bad_devices:
                        print 'WARNING: device "%s" is reporting bad pressure %+f' % (evt.device.name, p)
                        self.__bad_devices.append(evt.device.name)
                        # Over limits?
                    if p < -10000. or p > 10000.:
                        p = .5
                else:
                    p = .5
            self._pressure = p
        return self._pressure
