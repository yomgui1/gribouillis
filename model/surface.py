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

"""
The surface module gives API to create different types of surfaces and convert
pixels data between them.

Surface: composite object representing a 2D pixels array.
Each pixel are represented by one or more channels, a number (integer or float).
All these pixels are grouped under a pixel buffer. Surface is a proxy to manipulate
this buffer because this one may have different access model: plain, tileable, bound
or not, etc.

Surfaces are responsible to know how pixels are stored in memory and manage them.
Surface class hides this memory mapping to higher levels.

The surface class brings methods to access to one pixel or a rectangular region,
in order to get/set pixel channel values.
It gives also method to manipulate channels as sub-planes of the pixel surface.

Channel: logical view of one component of a 2D pixels array surface.

Pixel: a object to represent one surface's pixel color in the 2D pixels array.
"""

import _pixbuf, _tilemgr, cairo, sys

from utils import virtualmethod

__all__ = [ 'Surface', 'UnboundedTiledSurface', 'BoundedPlainSurface', 'TILE_SIZE' ]

TILE_SIZE = 64

class TileSurfaceSnapshot(dict):
    # These values are set in order to dirty_area returns 0 sized area
    dirty_area = (0, 0, 0, 0)
    
    def __init__(self, tiles):
        dict.__init__(self, tiles)
        self._mod = {} # will contains added tiles after reduce()
        
        # mark all tiles as readonly:
        # any modifications will replace this tiles by new ones with ro set to False
        for tile in tiles.itervalues():
            tile.ro = True

    def reduce(self, surface):
        "Split modified and unmodified tiles by make a difference with the given surface content"
                
        # Set dirty area to invalid values (but usefull with min/max computations)
        xmin = ymin = sys.maxint
        xmax = ymax = -sys.maxint - 1
    
        # Search for modifications (and additions!)
        for pos, tile in surface.tiles.iteritems():
            if not tile.ro:
                # Move added tiles into the other dict,
                # and update the dirty area
                
                self._mod[pos] = tile

                x = tile.x
                if xmin > x: xmin = x
                
                x += tile.width
                if xmax < x: xmax = x
                
                y = tile.y
                if ymin > y: ymin = y
                
                y += tile.height
                if ymax < y: ymax = y
            else:
                del self[pos]

        if self._mod or self:
            self.dirty_area = xmin, ymin, xmax-xmin+1, ymax-ymin+1
            return True

    def blit(self, tiles, redo):
        if redo:
            # Redo: remove touched tiles and restore modified/added ones
            map(tiles.pop, self)
            tiles.update(self._mod)
        else:
            # Undo: remove modified tiles and restore old contents
            map(tiles.pop, self._mod)
            tiles.update(self)

    @property
    def size(self):
        return sum(t.memsize for t in self.itervalues()) + \
               sum(t.memsize for t in self._mod.itervalues())
        
class Tile(_pixbuf.Pixbuf):
    def __new__(cls, pixfmt, x, y, s, *args):
        return super(Tile, cls).__new__(cls, pixfmt, s, s, *args)

    def __init__(self, pixfmt, x, y, s, src=None):
        super(Tile, self).__init__()
        if src is None:
            self.clear()
        self.x = x
        self.y = y
        self.ro = False

    def __hash__(self):
        return 0

    def copy(self):
        return self.__class__(self.pixfmt, self.x, self.y, self.width, self)

    def as_cairo_surface(self, cfmt=cairo.FORMAT_ARGB32, pfmt=_pixbuf.FORMAT_ARGB8):
        s = cairo.ImageSurface(cfmt, *self.size)
        assert 0 # need a row blit
        #self.blit(pfmt, s.get_data(), s.get_stride(), *self.size)
        s.mark_dirty()
        return s

class Surface(object):
    def __init__(self, pixfmt, writeprotect=False):
        self.pixfmt = pixfmt

    def _set_pixel(self, buf, pos, v):
        if isinstance(v, PixelAccessorMixin) and v.format == self.pixfmt:
            buf.set_from_pixel(pos, v)
        else:
            buf.set_from_tuple(pos, v)

    #### Virtual API ####

    @virtualmethod
    def clear(self):
        pass

    @property
    @virtualmethod
    def empty(self):
        pass

    @virtualmethod
    def rasterize(self, area, *args):
        pass

    @virtualmethod
    def from_buffer(self, pixfmt, data, stride, xoff, yoff, width, height):
        pass

    @virtualmethod
    def as_buffer(self, pixfmt, data, stride, xoff, yoff, width, height):
        pass

    @property
    @virtualmethod
    def bbox(self):
        "Returns full drawed bbox of the surface as a region."
        pass

    @virtualmethod
    def read_pixel(self, pos):
        pass

    @virtualmethod
    def copy(self, surface):
        "Copy content from another surface"
        pass
        
    @virtualmethod
    def get_pixbuf(self, x, y):
        "Return the pixel buffer at given location"
        pass

class BoundedPlainSurface(Surface):
    """BoundedPlainSurface class.

    Surface subclass handling the whole 2D pixels array as a unique and linerar
    memory block, bounded in space.

    Reserved to create small but fast rendering surfaces as all pixels data
    may reside in the user RAM, like preview or picture thumbnails.
    """
    
    def __init__(self, pixfmt, width, height):
        super(BoundedPlainSurface, self).__init__(pixfmt)
        self.__buf = _pixbuf.Pixbuf(pixfmt, width, height)
        self.clear = self.__buf.clear
        self.clear_white = self.__buf.clear_white
        self.clear_value = self.__buf.clear_value
        self.clear()
        
    def rasterize(self, area, *args):
        args[0](self.__buf, *args[1:])
        
    def get_pixbuf(self, x, y):
        buf = self.__buf
        if x >= buf.x and y >= buf.y and x < buf.width and y < buf.height:
            return buf

    def get_rawbuf(self):
        return self.__buf

    @property
    def size(self):
        """Give the total size of the surface as 2-tuple (width, height).

        Values are given in the surface units.
        """
        return self.__buf.size

class UnboundedTiledSurface(Surface): 
    def __init__(self, pixfmt):
        super(UnboundedTiledSurface, self).__init__(pixfmt)
            
        self.__tilemgr = _tilemgr.UnboundedTileManager(Tile, pixfmt, True)
        self.from_buffer = self.__tilemgr.from_buffer
        self.get_tiles = self.__tilemgr.get_tiles
        self.get_pixbuf = self.get_tile
        self.get_row_tile = self.__tilemgr.get_tile
        
    def clear(self):
        self.__tilemgr.tiles.clear()
        
    @property
    def empty(self):
        return not bool(self.__tilemgr.tiles)

    def snapshot(self):
        return TileSurfaceSnapshot(self.__tilemgr.tiles)

    def unsnapshot(self, snapshot, *args):
        return snapshot.blit(self.__tilemgr.tiles, *args)

    def rasterize(self, area, *args):
        self.__tilemgr.rasterize(area, args)

    def get_tile(self, *pos):
        t = self.__tilemgr.get_tile(*pos)
        if t.ro:
            t = t.copy()
            self.__tilemgr.set_tile(t, *pos)
        return t
        
    def from_png_buffer(self, *a, **k):
        self.from_buffer(_pixbuf.FORMAT_RGBA8_NOA, *a, **k)

    def as_buffer(self, pfmt=_pixbuf.FORMAT_RGBA8):
        x,y,w,h = self.area
        if not (w and h): return

        buf = _pixbuf.Pixbuf(pfmt, w, h)
        buf.clear()
        
        def blit(tile):
            tile.blit(buf, tile.x-x, tile.y-y)
        self.rasterize((x,y,w,h), blit)
        
        return buf

    def read_pixel(self, x, y):
        tile = self.__tilemgr.get_tile(x, y, False)
        if tile: return tile.get_pixel(int(x)-tile.x, int(y)-tile.y)

    def copy(self, surface):
        assert isinstance(surface, UnboundedTiledSurface)
        src = surface.__tilemgr
        dst = self.__tilemgr
        dst.tiles.clear()
        for tile in src.tiles.itervalues():
            dst.set_tile(tile.copy(), tile.x, tile.y)
            
    def cleanup(self):
        for k in tuple(k for k,v in self.__tilemgr.tiles.iteritems() if v.empty()):
            del self.__tilemgr.tiles[k]

    def __iter__(self):
        return self.__tilemgr.tiles.itervalues()

    @property
    def bbox(self):
        return self.__tilemgr.bbox

    @property
    def area(self):
        area = self.__tilemgr.bbox
        if area:
            x,y,w,h = area
            return x,y,w-x+1,h-y+1

    @property
    def tiles(self):
        return self.__tilemgr.tiles

    @property
    def tile_size(self):
        return self.__tilemgr.tile_size
