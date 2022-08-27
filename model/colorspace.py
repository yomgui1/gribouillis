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

import _pixbuf

class MetaColorSpace(type):
    __classes = {}

    def __new__(meta, name, bases, dct):
        cls = type.__new__(meta, name, bases, dct)
        if name != 'ColorSpace':
            if not any(x in dct for x in ('type', '_colors')):
                raise RuntimeError("ColorSpace subclasses must define 'type' and '_colors' attributes")
            name  = dct['_name_']
            if name in meta.__classes:
                raise KeyError("Already registered ColorSpace '%s'" % name)
            meta.__classes[name] = cls
        return cls

    @property
    def name(cls):
        return cls._name_

    @classmethod
    def from_name(meta, name):
        return meta.__classes[name]


class ColorSpace(metaclass=MetaColorSpace):
    # Given by sublasses
    # type = pixbuf colorpace type
    # _names = dict

    @classmethod
    def get_color(cls, name):
        return cls._colors[name]


class ColorSpaceRGB(ColorSpace):
    _name_ = 'RGB'
    type = _pixbuf.FLAG_RGB
    _colors = { 'black':       (0., 0., 0.),
                'white':       (1., 1., 1.),
              }


class ColorSpaceCMYK(ColorSpace):
    _name_ = 'CMYK'
    type = _pixbuf.FLAG_CMYK
    _colors = { 'black':       (0., 0., 0., 1.),
                'white':       (1., 1., 1., 0.),
              }
