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

import functools
import view.context as ctx


__OPERATORS = {}
ope_globals = dict(ctx=ctx)


def decorate(func, text=None):
    fname = func.__name__
    func.__translation = text or fname
    __OPERATORS[fname] = func
    ope_globals[fname] = func
    return functools.partial(func, ctx)

def operator(translation):
    return functools.partial(decorate, text=translation)

def get_translation(func):
    return func.__translation

def get_operators():
    return sorted(__OPERATORS.keys())

def get_event_op(name):
    return __OPERATORS[name]

def execute(name, *args, **kwds):
    return eval(name+"(ctx, *a, **k)", ope_globals, dict(a=args, k=kwds))
