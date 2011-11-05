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

from view.interfaces import EventParserI
from view.contexts import EventBase
from const import *

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
            0x68: 'mouse_leftpress',
            0x69: 'mouse_rightpress',
            0x6a: 'mouse_middlepress',
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

class EventParser(EventBase, EventParserI):    
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

    def __str__(self):
        return ' '.join([self.NAME, self.get_modificators(), str(self.get_key())]).strip()
       
    @property
    def fullkey(self):
        return self.__class__.TAG + self._hash
        
    @property
    def key(self):
        return self.__class__.TAG + self.__key

    @classmethod
    def encode(cl, key):
        return cl.TAG + cl._convert_keyadj_string(key)
        
    @staticmethod
    def _convert_keyadj_string(key):
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
        
    def get_time(self):
        if self._time is None:
            ## Removing 252460800 is the trick to synchronize the reference time used by time.time()
            ## and the time returned by system events.
            self._time = self._event.Seconds - self.__t0 + self._event.Micros*1e-6
        return self._time
    
    def get_modificators(self):
        if self._mods is None:
            mods = []
            qual = self._event.Qualifier 
            if qual & IEQUALIFIER_CAPSLOCK and self._event.Up:
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
            self._mods = ' '.join(mods)
        return self._mods
    
    def get_key(self):
        if self._key is None:
            self._key = _KEYVALS.get(self._event.RawKey)
            if self._key is None:
                self._key = (self._event.SimpleKey or chr(self._event.RawKey)).lower()
        return self._key

    def get_screen_position(self):
        if self._scr_pos is None:
            self._scr_pos = self._event.MouseX, self._event.MouseY
        return self._scr_pos

    def get_cursor_position(self):
        if self._cur_pos is None:
            self._cur_pos = self._event.MouseX - self._left, self._event.MouseY - self._top
        return self._cur_pos

    def get_cursor_xtilt(self):
        if self._cur_xtilt is None:
            if self._event.td_Tags:
                self._cur_xtilt = 2.0 * float(self._event.td_Tags.get(pymui.TABLETA_AngleX, 0)) / _ANGLE_MAX - 1.0
            else:
                self._cur_xtilt = 1.0
        return self._cur_xtilt

    def get_cursor_ytilt(self):
        if self._cur_ytilt is None:
            if self._event.td_Tags:
                self._cur_ytilt = 1.0 - 2.0 * float(self._event.td_Tags.get(pymui.TABLETA_AngleY, 0)) / _ANGLE_MAX
            else:
                self._cur_ytilt = 0.0
        return self._cur_ytilt

    def get_pressure(self):
        if self._pressure is None:
            if self._event.td_Tags:
                p = float(self._event.td_Tags.get(pymui.TABLETA_Pressure, _PRESSURE_MAX/2)) / _PRESSURE_MAX
            else:
                p = _DEFAULT_PRESSURE
            self._pressure = p
        return self._pressure

class CursorMoveEvent(EventParser):
    NAME = _T('cursor_move')
    TAG = 0x01000000

class GetFocusEvent(EventParser):
    NAME = _T('get_focus')
    TAG = 0x02000000

class LooseFocusEvent(EventParser):
    NAME = _T('loose_focus')
    TAG = 0x03000000

class KeyReleasedEvent(EventParser):
    NAME = _T('key_released')
    TAG = 0x04000000

class KeyPressedEvent(EventParser):
    NAME = _T('key_pressed')
    TAG = 0x05000000
        

__all__ = ['CursorMoveEvent', 'GetFocusEvent', 'LooseFocusEvent', 'KeyReleasedEvent', 'KeyPressedEvent']