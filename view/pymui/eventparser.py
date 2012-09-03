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

import pymui
import time

from utils import _T

from .const import *

_KEYVALS = {0x40: 'space',
            0x41: 'backspace',
            0x42: 'tab',
            0x43: 'enter',
            0x44: 'return',
            0x45: 'esc',
            0x46: 'delete',
            0x47: 'insert',
            0x48: 'page_up',
            0x49: 'page_down',
            0x4b: 'f11',
            0x4c: 'up',
            0x4d: 'down',
            0x4e: 'right',
            0x4f: 'left',
            0x50: 'f1',
            0x51: 'f2',
            0x52: 'f3',
            0x53: 'f4',
            0x54: 'f5',
            0x55: 'f6',
            0x56: 'f7',
            0x57: 'f8',
            0x58: 'f9',
            0x59: 'f10',
            0x5f: 'help',
            0x60: 'lshift',
            0x61: 'rshift',
            0x68: 'mouse-left',
            0x69: 'mouse-right',
            0x6a: 'mouse-middle',
            0x6f: 'f12',
            0x70: 'home',
            0x71: 'end',
            0x7a: 'wheel_up',
            0x7b: 'wheel_down',
            0x7e: 'mouse_fourth',
            0x7f: '',
            }

_KEYVALS_INV = {}
for k, v in _KEYVALS.iteritems():
    _KEYVALS_INV[v] = k

_DEFAULT_PRESSURE = 0.5
_PRESSURE_MAX     = 0x7ffff800
_ANGLE_MAX        = 128.0

class MUIEventParser:
    __t0 = int(time.time()) - 252460800.
    
    def __init__(self, event, src):
        self._event = event
        self._left, self._top, self._right, self._bottom = src.MBox
        
        if self._event.RawKey in _KEYVALS:
            v = self._event.RawKey
        else:
            v = ord((self._event.SimpleKey or chr(self._event.RawKey))[0].lower()) + 0x10000
            
        self.__key = v
        q = self._event.Qualifier
        self._hash = ((q & ALL_QUALIFIERS) << 8) + v
        self.repeat = q & IEQUALIFIER_REPEAT

    @classmethod
    def encode(cl, key):
        return cl._convert_keyadj_string(key)
        
    @staticmethod
    def convert_key(key):
        qual = 0
        for word in key.split():
            if word == 'capslock': qual += IEQUALIFIER_CAPSLOCK
            elif word == 'lalt': qual += IEQUALIFIER_LALT
            elif word == 'ralt': qual += IEQUALIFIER_RALT
            elif word == 'control': qual += IEQUALIFIER_CONTROL
            elif word == 'lshift': qual += IEQUALIFIER_LSHIFT
            elif word == 'rshift': qual += IEQUALIFIER_RSHIFT
            elif word == 'lcommand': qual += IEQUALIFIER_LCOMMAND
            elif word == 'rcommand': qual += IEQUALIFIER_RCOMMAND
            elif word in _KEYVALS_INV:
                return (qual << 8) + _KEYVALS_INV[word]
            else:
                return (qual << 8) + ord(word[0]) + 0x10000
        return (qual << 8) + 0x7f
    
    @staticmethod
    def get_modificators(event):
        mods = []
        qual = event.Qualifier 
        if qual & IEQUALIFIER_CAPSLOCK and event.Up:
            mods.append('capslock')
        if qual & IEQUALIFIER_LALT:
            mods.append('lalt')
        if qual & IEQUALIFIER_RALT:
            mods.append('ralt')
        if qual & IEQUALIFIER_CONTROL:
            mods.append('control')
        if qual & IEQUALIFIER_LSHIFT:
            mods.append('lshift')
        if qual & IEQUALIFIER_RSHIFT:
            mods.append('rshift')
        if qual & IEQUALIFIER_LCOMMAND:
            mods.append('lcommand')
        if qual & IEQUALIFIER_RCOMMAND:
            mods.append('rcommand')
        return ' '.join(mods)
    
    @staticmethod
    def get_key(event):
        key = _KEYVALS.get(event.RawKey)
        if key is None:
            return (self._event.SimpleKey or chr(self._event.RawKey)).lower()
        return key

    @staticmethod
    def get_time(event):
        ## Removing 252460800 is the trick to synchronize the reference time used by time.time()
        ## and the time returned by system events.
        return event.Seconds - MUIEventParser.__t0 + event.Micros*1e-6

    @staticmethod
    def get_screen_position(event):
        return event.MouseX, event.MouseY

    @staticmethod
    def get_cursor_xtilt(event):
        if event.td_Tags:
            return 2.0 * float(event.td_Tags.get(pymui.TABLETA_AngleX, 0)) / _ANGLE_MAX - 1.0
        return 1.0

    @staticmethod
    def get_cursor_ytilt(event):
        if event.td_Tags:
            return 1.0 - 2.0 * float(event.td_Tags.get(pymui.TABLETA_AngleY, 0)) / _ANGLE_MAX
        return 0.0

    @staticmethod
    def get_pressure(event):
        if event.td_Tags:
            return float(event.td_Tags.get(pymui.TABLETA_Pressure, _PRESSURE_MAX/2)) / _PRESSURE_MAX
        return _DEFAULT_PRESSURE
