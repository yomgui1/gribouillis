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

import model
import utils

__all__ = ["command", "get_commands", "Context", "ModalContext"]


def command(name):
    "Function decorator used to add new command"

    def wrapper(func):
        Context.commands[name] = func
        return func
    return wrapper


def get_commands():
    "Returns all registered command names"
    return Context.commands.keys()


class MetaContext(type):
    __commands = {}

    def __new__(meta, name, bases, dct):
        emap =  dct.get('EVENTS_MAP')
        if emap is not None:
            # Update events mapping with user prefs
            user_maps = model.prefs.get('view-events-maps')
            if user_maps and name in user_maps:
                emap.update(user_maps[name])

            # Create a new mapping betwwen events name and cmd's functions
            d = dct['_EVENTS_MAP'] = {}
            for k, v in emap.iteritems():
                d[k] = MetaContext.__commands[v]

        return type.__new__(meta, name, bases, dct)

    @staticmethod
    def get_cmd(name):
        return MetaContext.__commands.get(name)

    @property
    def commands(cls):
        return MetaContext.__commands


class Context(object):
    """Context() class

    Contexts are used to defined a named event mapping.
    There are used to create a non-modal events handling.
    Unique events objects are mapped to named commands.
    The user implements a context manager that map named
    commands to python functions.
    Context instance is metamorph:
    user define and store a events-cmd mapping inside
    the contexts subclasses, not instances.
    User uses only one context instance where is instancied
    events-funcs mapping can be switched at runtime,
    using mapping from another Context subclass.
    """

    __metaclass__ = MetaContext

    EVENTS_MAP = {}

    _post_cleanup = id

    def __init__(self, cls, **kwds):
        self._map = {}
        self._cls = Context
        self.switch(cls, **kwds)

    def switch(self, cls, **kwds):
        _cls = self._cls
        print "CTX: %s -> %s" % (_cls.__name__, cls.__name__)
        _cls.cleanup(self)
        self._cls = cls
        self._map = cls._EVENTS_MAP
        self.__dict__.update(kwds)
        cls.setup(self)

    def switch_modal(self, cls, **kwds):
        # In modal context we save attributes
        # for restoring later and forbid context switch.

        _cls = self._cls
        print "CTX: %s -> %s (Modal)" % (_cls.__name__, cls.__name__)
        _cls.cleanup(self)
        self._cls = cls  # must be before dict copy!!
        self.__odict = self.__dict__.copy()
        self.switch = utils.idle_cb
        self.switch_modal = utils.idle_cb
        self._map = cls._EVENTS_MAP
        self.__dict__.update(kwds)
        cls.setup(self)

    def stop_modal(self):
        self.__dict__ = self.__odict

    def on_event(self, evt):
        d = self._map
        k = evt.get_key()
        cmd = d.get(str(evt)) or d.get(':'+k) or d.get(k)
        if cmd:
            self.evt = evt
            r = cmd(self)
            del self.evt
            return r
        print "EVT(%s): %s" % (self._cls.__name__, str(evt))

    def execute(self, name):
        cmd = MetaContext.get_cmd(name)
        return cmd and not cmd(self)

    @staticmethod
    def setup(ctx):
        pass

    @staticmethod
    def cleanup(ctx):
        pass
