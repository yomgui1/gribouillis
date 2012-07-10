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
import random
from math import floor, ceil

from model.surface import *
from model import _pixbuf
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
                  'mask':       cairo.OPERATOR_ATOP,
                  'darken':     17,
                  'lighten':    18,
                  'dodge':      19,
                  'burn':       20,
                  'hard-light': 21,
                  'soft-light': 22,
                  'clear':      cairo.OPERATOR_CLEAR,
                  'add':        cairo.OPERATOR_ADD,
                  'xor':        cairo.OPERATOR_XOR,
                  'difference': 23,
                  'exclusion':  24,
                }

    OPERATORS_LIST  = "normal multiply screen overlay clear mask add difference exclusion"
    OPERATORS_LIST += " darken lighten dodge burn hard-light soft-light xor"
    OPERATORS_LIST  = OPERATORS_LIST.split()

    _visible = True
    locked = False
    dirty = False
    
    def __init__(self, surface, name, alpha=1.0, alphamask=None, operator='normal', opacity=1.0, **options):
        self._surface   = surface # drawing surface
        self._alpha     = alpha # global transparency of the layer
        self._alphamask = alphamask # surface to use as global transparency of the layer (* _alpha)
        self._name      = name
        self.operator   = operator
        self.opacity    = opacity
        self._matrix     = cairo.Matrix() # display matrix
        self.inv_matrix = cairo.Matrix()
        
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
        self._matrix = layer._matrix.multiply(cairo.Matrix())
        self.inv_matrix = layer.inv_matrix.multiply(cairo.Matrix())
        self._surface.copy(layer._surface)
        self._dirty = True

    def snapshot(self):
        # TODO: and alpha/alphamask
        return self._surface.snapshot()

    def unsnapshot(self, snapshot, redo=False):
        self.dirty = True
        return self._surface.unsnapshot(snapshot, redo)


    def translate(self, *delta):
        x, y = self.inv_matrix.transform_distance(*delta)
        self._matrix.translate(x,y)
        self.inv_matrix.translate(-x,-y)
        self._dirty = True

    @property
    def surface(self):
        return self._surface

    @property
    def empty(self):
        return self._surface.empty

    def _set_name(self, name):
        self._name = name
        self._dirty = True

    def _set_visible(self, value):
        self._visible = value
        self._dirty = True

    def get_bbox(self):
        bbox = self._surface.bbox
        if bbox:
            x1, y1, x2, y2 = bbox
            ope = self._matrix.transform_point
            
            c = [ ope(x1,y1), ope(x2,y2), ope(x1, y2), ope(x2, y1) ]
            lx = sorted(x for x,y in c)
            ly = sorted(y for x,y in c)

            return int(floor(lx[0])), int(floor(ly[0])), int(ceil(lx[-1])), int(ceil(ly[-1]))

    def document_area(self, x, y, w, h):
        w += x - 1
        h += y - 1
        ope = self._matrix.transform_point

        c = [ ope(x, y), ope(w, h), ope(x, h), ope(w, y) ]
        lx = sorted(x for x,y in c)
        ly = sorted(y for x,y in c)

        x = int(floor(lx[0]))
        y = int(floor(ly[0]))
        return x, y, int(ceil(lx[-1])) - x + 1, int(ceil(ly[-1])) - y + 1

    def get_size(self):
        area = self.get_bbox()
        if not area: return 0,0
        return area[1]-area[0]+1, area[3]-area[2]+1

    def set_matrix(self, matrix):
        self._matrix = matrix
        self.inv_matrix = cairo.Matrix(*matrix)
        self.inv_matrix.invert()
        self._dirty = True
        
    matrix = property(lambda self: self._matrix, fset=set_matrix)
    
    @property
    def area(self):
        area = self.get_bbox()
        if area:
            return area[0], area[1], area[2]-area[0]+1, area[3]-area[1]+1
            
    @property
    def extends(self):
        return self._surface.bbox

    @virtualmethod
    def merge_to(self, dst):
        pass

    @property
    def modified(self):
        return self._dirty
        
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
        """Merging the layer on a given layer (dst).
        
        Operation takes care of layers opactity. After the operation
        the destination is marked as modified, but opacity is kept unchanged.
        """
        
        matrix = dst.inv_matrix * self._matrix
        inv_matrix = cairo.Matrix(*matrix)
        inv_matrix.invert()
        ope = matrix.transform_point
        new_surface = cairo.ImageSurface.create_for_data
        operator = self.OPERATORS[self.operator]
        
        src_opa = self.opacity
        dst_opa = dst.opacity
        
        # Pixbuf to do the pixel format convertion GB3 -> cairo
        tmp = _pixbuf.Pixbuf(_pixbuf.FORMAT_ARGB8, TILE_SIZE, TILE_SIZE)
        tmp_surf = cairo.ImageSurface.create_for_data(tmp, cairo.FORMAT_ARGB32, TILE_SIZE, TILE_SIZE)
        
        # rendering surface used during destination blit
        # Created on a Pixbuf surface for clearing speedup and dest copy
        rsurf_pb = _pixbuf.Pixbuf(_pixbuf.FORMAT_ARGB8, TILE_SIZE, TILE_SIZE)
        rsurf = cairo.ImageSurface.create_for_data(rsurf_pb, cairo.FORMAT_ARGB32, TILE_SIZE, TILE_SIZE)
        cr = cairo.Context(rsurf)
        
        if dst_opa != 1.0:
            # Note: if dst tiles are marked as readonly, we'll get new tile
            # => perfect if layer has been snapshot'ed.
            for dst_tile in dst.surface.get_tiles(dst.surface.area):
                dst_tile.blit(tmp) # format convertion: GB3 -> cairo
                
                # Blit the destination first using its opacity
                rsurf_pb.clear()
                cr.set_source_surface(tmp_surf, 0, 0)
                cr.paint_with_alpha(dst_opa)
                
                # Copy the result into destionation tile (+ format convertion)
                rsurf_pb.blit(dst_tile)
        
        for tile in self.surface:
            # change tile boundary from its layer origin into global origin
            x1 = tile.x
            y1 = tile.y
            x2 = x1 + tile.width - 1
            y2 = y1 + tile.height - 1
            c = [ ope(x1, y1), ope(x2, y2), ope(x1, y2), ope(x2, y1) ]
            lx = sorted(x for x,y in c)
            ly = sorted(y for x,y in c)
            del c, x2, y2
            x1 = int(floor(lx[0]))
            y1 = int(floor(ly[0]))
            w = int(ceil(lx[-1])) - x1 + 1
            h = int(ceil(ly[-1])) - y1 + 1
            del lx, ly
            
            # Create a cairo surface for the transformed source tile
            pb_trans = _pixbuf.Pixbuf(tile.pixfmt, w, h)
            pb_trans.x = x1
            pb_trans.y = y1
            
            # do the affine transformation
            tile.slow_transform_affine(self.surface.get_row_tile, pb_trans, *inv_matrix)
            
            # convert buffers to cairo buffer and use cairo to do compositing (operators needed!)
            # TODO: replace this code by an internal compositor when operators/opacity are supported!
            
            rpb = _pixbuf.Pixbuf(_pixbuf.FORMAT_ARGB8, w, h)
            rpb.clear()
            pb_trans.blit(rpb)
            del pb_trans
            
            # Surface for cairo compositing
            src_surf = cairo.ImageSurface.create_for_data(rpb, cairo.FORMAT_ARGB32, w, h)
                        
            for dst_tile in dst.surface.get_tiles([ x1, y1, w, h ], True):
                # Make a copy of destination tile
                dst_tile.blit(rsurf_pb)
                
                # Blit the transformed source now with its opacity and layer compositing operation.
                cr.set_source_surface(src_surf, x1-dst_tile.x, y1-dst_tile.y)
                cr.set_operator(operator)
                cr.paint_with_alpha(src_opa)
                
                # Copyback the result into destination tile
                rsurf_pb.blit(dst_tile)
                                
            # Finalisation
            dst._dirty = True
            
    def get_pixel(self, brush, *pt):
        brush.surface = self.surface
        return brush.get_pixel(*self.inv_matrix.transform_point(*pt))
