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

__all__ = ["command", "Context", "ModalContext"]

def command(name):
    def wrapper(func):
        func._cmdname = name
        return func
    return wrapper


class MetaContext(type):
    def __new__(meta, name, bases, dct):
        d = {}

        # Inherit commands map
        for cls in bases:
            if hasattr(cls, '_cmdmap'):
                d.update(cls._cmdmap)

        # Update with local commands
        for v in dct.itervalues():
            if hasattr(v, '_cmdname'):
                d[v._cmdname] = v
                del v._cmdname

        dct['_cmdmap'] = d
        return type.__new__(meta, name, bases, dct)

    @staticmethod
    def setup(ctx):
        pass

    @staticmethod
    def cleanup(ctx):
        pass

class Context(dict):
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
    __ctx = MetaContext

    def __init__(self, **data):
        self.__dict__.update(data)
        self.switch(self.__class__)

    @classmethod
    def remap(cls, d):
        omap = d.get('_oldmap')
        if omap:
            d.clear()
            d.update(omap)
            del d._oldmap
        d.update(cls.EVENTS_MAP)

    def switch(self, ctx):
        print "CTX: %s" % ctx.__name__
        self.__ctx.cleanup(self)
        self.__ctx = ctx
        ctx.remap(self)
        ctx.setup(self)

    def execute(self, evt):
        cmd = self[str(evt)]
        if not self.__ctx._cmdmap[cmd](self, evt):
            return True

    @property
    def ctx(self):
        return self.__ctx

    @staticmethod
    def setup(ctx):
        pass

    @staticmethod
    def cleanup(ctx):
        pass

class ModalContext(Context):
    @classmethod
    def remap(cls, d):
        assert not hasattr(d, '_oldmap')
        d._oldmap = d.copy()
        d.clear()
        d.update(cls.EVENTS_MAP)
