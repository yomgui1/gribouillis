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

__all__ = ["command", "get_commands", "Context", "ModalContext"]


def command(name):
    def wrapper(func):
        Context.commands[name] = func
        return func
    return wrapper


def get_commands():
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

    def __init__(self, **data):
        self.__dict__.update(data)
        self._map = {}
        self._ctx = Context
        self.switch(self.__class__)        

    @classmethod
    def remap(cls, ctx):
        omap = getattr(ctx, '_oldmap', None)
        if omap is not None:
            ctx._map = omap
            del ctx._oldmap
        ctx._map.update(cls._EVENTS_MAP)

    def switch(self, ctx):
        print "CTX: %s" % ctx.__name__
        self._ctx.cleanup(self)
        self._ctx = ctx
        ctx.remap(self)
        ctx.setup(self)

    def execute(self, evt):
        cmd = self._map[str(evt)]
        if not cmd(self, evt):
            return True

    @staticmethod
    def setup(ctx):
        pass

    @staticmethod
    def cleanup(ctx):
        pass


class ModalContext(Context):
    @classmethod
    def remap(cls, ctx):
        assert not hasattr(ctx, '_oldmap')
        ctx._oldmap = ctx._map
        ctx._map = cls._EVENTS_MAP
