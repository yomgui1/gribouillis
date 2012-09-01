###############################################################################
# Copyright (c) 2009-2012 Guillaume Roguez
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

import utils

from operator import Operator


class KeymapManager():
    __metaclass__ = utils.MetaSingleton
    __maps = {}
    __map = None
    __saved = None
    
    dump_key = 0

    @staticmethod
    def _parse_map(kmap):
        dct = {}
        for k, v in kmap.iteritems():
            if isinstance(v, tuple):
                dct[k] = (Operator.get_event_op(v[0]), v[1])
            else:
                dct[k] = Operator.get_event_op(v)
        return dct


    def _process(self, action, evt, mods, kwds):
        if isinstance(action, tuple):
            action, m = action
            if m is not None and m != mods:
                return
        elif mods:
            return
        return action(evt, **kwds)

    def process(self, evt, key, mods=[], **kwds):
        actions = self.__map.get(key)
        if actions:
            if isinstance(actions, list):
                for op in actions:
                    self._process(op, evt, mods, kwds)
            else:
                return self._process(actions, evt, mods, kwds)
        elif self.dump_key:
            print key, mods

    @classmethod
    def use_map(cls, mapname):
        kmap = cls.__maps.get(mapname)
        if kmap:
            cls.__map = kmap

    @classmethod
    def save_map(cls):
        if not cls.__saved:
            cls.__saved = cls.__map

    @classmethod
    def restore_map(cls):
        cls.__map = cls.__saved
        cls.__saved = None

    @classmethod
    def register_keymap(cls, name, kmap):
        cls.__maps[name] = cls._parse_map(kmap)
