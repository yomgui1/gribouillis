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

import cairo

from model.surface import *
from utils import virtualmethod

__all__ = [ 'Layer', 'PlainLayer', 'TiledLayer' ]

class Layer(object):
    """Layer() -> Layer object instance

    As surfaces are polymorphs, a document never handles
    directly a surface, it uses layers.
    So a layer is a container of one or more surfaces,
    grouped as channels.

    As a document groups layers, these last have a compositing mode property
    to explain how each layer are composited between them to render
    the final image.

    Layer represent a single 2D surface made of pixels.
    A layer is not responsible to know in which colorspace pixels are defined.
    This is the role of surfaces.
    So layer is only responsible to define how to composite it which another layer,
    how to
    """

    OPERATORS = { 'normal':     cairo.OPERATOR_OVER,
                  'multiply':   14,
                  'screen':     15,
                  'overlay':    16,
                  'darken':     17,
                  'lighten':    18,
                  'dodge':      19,
                  'burn':       20,
                  'hard-light': 21,
                  'soft-light': 22,
                }

    OPERATORS_LIST = "normal multiply screen overlay darken lighten dodge burn hard-light soft-light"
    OPERATORS_LIST = tuple(OPERATORS_LIST.split())

    def __init__(self, surface, name, alpha=1.0, alphamask=None, operator='normal', **options):
        self._surface   = surface # drawing surface
        self._alpha     = alpha # global transparency of the layer
        self._alphamask = alphamask # surface to use as global transparency of the layer (* _alpha)
        self._name      = name
        self._visible   = True
        self.operator   = operator
        self.opacity    = 1.0
        self.x          = 0
        self.y          = 0

    def __repr__(self):
        return "'%s'" % self._name

    def clear(self):
        self._surface.clear()

    def copy(self, layer):
        self._alpha = layer._alpha
        self._alphamask = layer._alphamask
        self._visible = layer._visible
        self.opacity = layer.opacity
        self.operator = layer.operator
        self.x = layer.x
        self.y = layer.y
        self._surface.copy(layer._surface)

    def snapshot(self):
        # TODO: and alpha/alphamask
        return self._surface.snapshot()

    def unsnapshot(self, snapshot, invert=False):
        self._surface.unsnapshot(snapshot, invert)

    def record_stroke(self, stroke):
        pass # TODO

    @property
    def surface(self):
        return self._surface

    @property
    def empty(self):
        return self._surface.empty

    def _set_name(self, name):
        self._name = name

    def _set_visible(self, value):
        self._visible = value

    def get_bbox(self):
        x1, y1, x2, y2 = self._surface.bbox
        lx = int(self.x)
        ly = int(self.y)
        return x1+lx, y1+ly, x2+lx, y2+ly

    def get_size(self):
        area = self._surface.bbox
        if not area: return 0,0
        return area[1]-area[0]+1, area[3]-area[2]+1

    @virtualmethod
    def merge_to(self, dst):
        pass

    name = property(fget=lambda self: self._name, fset=_set_name)
    visible = property(fget=lambda self: self._visible, fset=_set_visible)


class PlainLayer(Layer):
    def __init__(self, pixfmt, name, **options):
        surface = None # TODO
        super(PlainLayer, self).__init__(surface, name, **options)


class TiledLayer(Layer):
    def __init__(self, pixfmt, name, **options):
        surface = UnboundedTiledSurface(pixfmt)
        super(TiledLayer, self).__init__(surface, name, **options)

    @property
    def empty(self):
        return len(self._surface.tiles) == 0

    def merge_to(self, dst):
        self.surface.merge_to(dst.surface, Layer.OPERATORS[self.operator], self.opacity)
