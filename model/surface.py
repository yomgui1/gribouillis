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

Surfaces implementation shall be thread-safe as can be accessed by multiples tasks.
So surfaces implement a lock mechanism.

Channel: logical view of one component of a 2D pixels array surface.

Pixel: a object to represent one surface's pixel color in the 2D pixels array.
"""

import _pixbuf, _tilemgr, png, cairo
from cStringIO import StringIO

from utils import virtualmethod

__all__ = [ 'Surface', 'UnboundedTiledSurface',
            'BoundedPlainSurface' ]


class _IntegerBuffer(object):
    def __init__(self, buf):
        self.b = buffer(buf)

    def __getslice__(self, start, stop):
        return tuple(ord(c) for c in self.b[start:stop])


class TileSurfaceSnapshot:
    def __init__(self, tiles):
        self.old = tiles.copy()
        self.new = {}
        for tile in tiles.itervalues():
            tile.ro = True

    def reduce(self, surface):
        # Keep only non touched tiles
        n = {}
        for k, tile in surface.tiles.iteritems():
            if tile.ro:
                del self.old[k]
            else:
                n[k] = tile
        self.new = n

    def blit(self, tiles, invert):
        if invert:
            # Redo
            for k in self.old:
                tiles.pop(k)
            for k,v in self.new.iteritems():
                tiles[k] = v
        else:
            # Undo
            for k in self.new:
                tiles.pop(k)
            for k,v in self.old.iteritems():
                tiles[k] = v

    @property
    def size(self):
        return sum(t.memsize for t in self.new.itervalues()) + \
               sum(t.memsize for t in self.old.itervalues())

        
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
        self.blit(pfmt, s.get_data(), s.get_stride(), *self.size)
        s.mark_dirty()
        return s
        

class Surface(object):
    def __init__(self, pixfmt, writeprotect=False):
        self.pixfmt = pixfmt
        self.__writable = writeprotect

    def _set_pixel(self, buf, pos, v):
        if isinstance(v, PixelAccessorMixin) and v.format == self.pixfmt:
            buf.set_from_pixel(pos, v)
        else:
            buf.set_from_tuple(pos, v)

    def __get_wp(self):
        self.lock() # READ lock
        v = self.__writable
        self.unlock()
        return v

    def __set_wp(self, v):
        self.lock(True) # WRITE lock
        self.__writable = v
        self.unlock()

    writeprotect = property(fget=__get_wp, fset=__set_wp)

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
    def lock(self, excl=False, block=True):
        """Protect the surface against read or/and write accesses.

        The lock is given per-process.

        Exclusive lock is given if no other locks (exclusive or not)
        are pending on this surface.
        Blocking lock blocks the caller if another process is owning
        exclusively the lock. Shared locks doesn't block non-exclusive
        calls.

        Use unlock() method to remove the lock.

        Locking a surface is mandatory to process dirty regions.
        """
        pass

    @virtualmethod
    def unlock(self):
        "Unlock a previously locked surface by lock()."
        pass

    @virtualmethod
    def copy(self, surface):
        "Copy content from another surface"
        pass


class BoundedPlainSurface(Surface):
    """BoundedPlainSurface class.

    Surface subclass handling the whole 2D pixels array as a unique and linerar
    memory block, bounded in space.

    Reserved to create small but fast rendering surfaces as all pixels data
    may reside in the user RAM, like preview or picture thumbnails.
    """
    
    def __init__(self, pixfmt, width, height, writeprotect=True, fill=False):
        super(BoundedPlainSurface, self).__init__(pixfmt, writeprotect)
        self.__buf = _pixbuf.Pixbuf(pixfmt, width, height)
        self.clear()

    def lock(self, *a, **k):
        self.__buf.lock(*a, **k)

    def unlock(self, *a, **k):
        self.__buf.unlock(*a, **k)
        
    def clear(self):
        self.__buf.clear()
        
    def clear_white(self):
        self.__buf.clear_white()
        
    def rasterize(self, area, *args):
        args[0](self.__buf, *args[1:])
        
    def get_pixbuf(self, x, y):
        buf = self.__buf
        if x >= buf.x and y >= buf.y and x < buf.width and y < buf.height:
            return buf

    @property
    def size(self):
        """Give the total size of the surface as 2-tuple (width, height).

        Values are given in the surface units.
        """
        return self.__buf.size


class UnboundedTiledSurface(Surface):
    def __init__(self, pixfmt, writeprotect=True, fill=False):
        super(UnboundedTiledSurface, self).__init__(pixfmt, writeprotect)

        self.__tilemgr = _tilemgr.UnboundedTileManager(Tile, pixfmt, writeprotect)
        self.from_buffer = self.__tilemgr.from_buffer

    def clear(self):
        self.__tilemgr.tiles = {}

    @property
    def empty(self):
        return not bool(self.__tilemgr.tiles)

    def snapshot(self):
        return TileSurfaceSnapshot(self.__tilemgr.tiles)

    def unsnapshot(self, snapshot, invert=False):
        return snapshot.blit(self.__tilemgr.tiles, invert)

    def rasterize(self, area, *args):
        self.__tilemgr.rasterize(area, args)

    def lock(self, *a, **k):
        self.__tilemgr.lock(*a, **k)

    def unlock(self, *a, **k):
        self.__tilemgr.unlock(*a, **k)

    def get_tile(self, *pos):
        t = self.__tilemgr.get_tile(*pos)
        if t.ro:
            t = t.copy()
            self.__tilemgr.set_tile(t, *pos)
        return t

    def get_tiles(self, area):
        return self.__tilemgr.get_tiles(area)

    def get_pixbuf(self, *pos):
        return self.get_tile(*pos)
        
    def from_png_buffer(self, *a, **k):
        self.from_buffer(_pixbuf.FORMAT_RGBA8_NOA, *a, **k)

    def as_buffer(self, pfmt=_pixbuf.FORMAT_RGBA8):
        x,y,w,h = self.area
        if not (w and h): return

        buf = _pixbuf.Pixbuf(pfmt, w, h)
        buf.clear()
        
        def blit(tile):
            tile.blit(pfmt, buf, buf.stride, w, h, tile.x-x, tile.y-y)
        self.rasterize((x,y,w,h), blit)
        
        return buf

    def as_png_buffer(self, comp=4):
        # Tiled surface -> buffer (PNG = RGBA8 format, no alpha-premul)
        pix_buf = self.as_buffer(_pixbuf.FORMAT_RGBA8_NOA)

        # Encode pixels data to PNG
        png_buf = StringIO()
        writer = png.Writer(pix_buf.width, pix_buf.height, alpha=True, bitdepth=8, compression=comp)
        writer.write_array(png_buf, _IntegerBuffer(pix_buf))
        
        return png_buf.getvalue()

    def read_pixel(self, x, y):
        tile = self.__tilemgr.get_tile(x, y, False)
        if tile: return tile.get_pixel(int(x)-tile.x, int(y)-tile.y)

    def merge_to(self, dst, operator=cairo.OPERATOR_OVER, opacity=1.0):
        # Note: this version has a low mem profile, but consumes more the CPU.
        
        assert self.tile_size == dst.tile_size
        
        w = self.tile_size
        fmt = _pixbuf.FORMAT_ARGB8 # for cairo FORMAT_ARGB32
        
        for stile in self.tiles.itervalues():
            x = stile.x
            y = stile.y
            dtile = dst.get_tile(x, y)
            
            dsurf = dtile.as_cairo_surface(pfmt=fmt)
            ssurf = stile.as_cairo_surface(pfmt=fmt)

            cr = cairo.Context(dsurf)
            cr.set_operator(operator)
            cr.set_source_surface(ssurf, 0, 0)
            cr.paint_with_alpha(opacity)

            dtile.from_buffer(fmt,
                              dsurf.get_data(),
                              dsurf.get_stride(),
                              x, y, w, w)

    def copy(self, surface):
        assert isinstance(surface, UnboundedTiledSurface)
        d = surface.__tilemgr.tiles
        self.__tilemgr.tiles = d.copy()
        for tile in d.itervalues():
            tile.ro = True
            
    def cleanup(self):
        for k in tuple(k for k,v in self.__tilemgr.tiles.iteritems() if v.empty()):
            del self.__tilemgr.tiles[k]

    def itertiles(self):
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
        return 0,0,0,0

    @property
    def tiles(self):
        return self.__tilemgr.tiles

    @property
    def tile_size(self):
        return self.__tilemgr.tile_size
