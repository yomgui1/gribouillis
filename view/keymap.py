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
import context

from operator import Operator


class KeymapManager():
    """KeymapManager

    Instance of this class helps to map OS specific events
    to application methods.
    Application actions (aka Operators) are mapped on events,
    using a function as key. This function is used to match events.
    Another feature is the multi maps handling: at any moments
    the KeymapManager instance can uses another map,
    that permit to implement modal handling.

    Requiers 2.7
    """

    __metaclass__ = utils.MetaSingleton
    __maps = {} # all registered maps
    
    def __init__(self, context, parent=None):
        self.context = context
        self._parent_process = (parent.process if parent else lambda *a: True)
        self._mapstack = []
        self._map = None # active map
        self._keys = None # current map keys view
        self._default = None # default keymap if use method used without argument

    def process(self, evt):
        assert self._map is not None
        # Each key is a function that return True if the given event fits
        keys = [ k for k in self._keys if k(evt) ]
        if keys:
            self.context.keymap = self
            for k in keys:
                if self._map[k](self.context, evt):
                    return True
        else:
            return self._parent_process(evt)

    def set_default(self, name):
        self._default = name
        self.use(name)

    def use(self, name):
        m = KeymapManager.__maps.get(name, self._map)
        if m is not self._map:
            self._map = m
            self._keys = self._map.viewkeys()

    def use_default(self):
        assert self._default is not None
        self.use(self._default)

    def push(self, name):
        self._mapstack.append(self._map.NAME)
        self.use(name)

    def pop(self):
        if self._mapstack:
            self.use(self._mapstack.pop())

    @classmethod
    def register_keymap(cls, kmap):
        """Transform each key string of keymap dictionnary
        as a callable returning a boolean.
        """
        for k in kmap.keys():
            kmap[eval("lambda evt:" + k)] = Operator.get_event_op(kmap.pop(k))
        cls.__maps[kmap.NAME] = kmap


class Keymap(dict):
    def __init__(self, name, *a, **k):
        dict.__init__(self, *a, **k)
        self.NAME = name
        KeymapManager.register_keymap(self)
