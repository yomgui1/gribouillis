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

import utils
import context
import operator
import view.context as ctx


class Keymap(dict):
    def __init__(self, name, *a, **k):
        dict.__init__(self, *a, **k)
        self.NAME = name
        KeymapManager.register_keymap(self)


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
    __kmd = {} # all registered keymaps

    def __init__(self, default):
        self._km = None # active keymap
        self._filters = None # current keymap's keys view used as filters
        self._mapstack = []
        self.use(default)
        self._locals = {}

    def process(self, *fargs):
        assert self._km is not None # need a valid keymap

        self._locals['event'] = fargs[1]
        for f in self._filters:
            if f(*fargs):
                eval(self._km[f], operator.ope_globals, self._locals)

    def use(self, name):
        m = KeymapManager.__kmd.get(name, self._km)
        if m is not self._km:
            ctx.keymap = self
            self._km = m
            self._filters = m.viewkeys()

    def use_default(self):
        assert self._default is not None
        self.use(self._default)

    def push(self, name):
        self._mapstack.append(self._km.NAME)
        self.use(name)

    def pop(self):
        if self._mapstack:
            self.use(self._mapstack.pop())

    @classmethod
    def register_keymap(cls, km):
        """Transform each keymap dictionnary key (string)
        into a callable with following prototype:

        "lambda evt_type, evt: bool"

        Note: this operation destroy original contents of the keymap.
        """

        for k in km.keys():
            km[eval("lambda evt_type, evt:" + k)] = compile(km.pop(k), 'keymap', 'exec')
        cls.__kmd[km.NAME] = km


