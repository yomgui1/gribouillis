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

"""
Surface object handles a group of pixels arranged in two dimensionals space.
A surface can be bounded as BoundedPlainSurface or unbounded
as UnboundedTiledSurface.
"""

import sys
import cairo

import _pixbuf
import _tilemgr

from utils import virtualmethod

__all__ = ['Surface', 'UnboundedTiledSurface', 'BoundedPlainSurface',
           'TILE_SIZE']

TILE_SIZE = 64


class Surface(object):
    def __init__(self, pixfmt, writeprotect=False):
        self.pixfmt = pixfmt

    def _set_pixel(self, buf, pos, v):
        if isinstance(v, PixelAccessorMixin) and v.format == self.pixfmt:
            buf.set_from_pixel(pos, v)
        else:
            buf.set_from_tuple(pos, v)

    #### Virtual API ####
    @property
    @virtualmethod
    def empty(self):
        pass

    @property
    @virtualmethod
    def bbox(self):
        "Returns full drawed bbox of the surface as a region."
        pass

    @virtualmethod
    def clear(self):
        pass

    @virtualmethod
    def copy(self, surface):
        "Copy contents from another surface"
        pass

    @virtualmethod
    def read_pixel(self, pos):
        pass

    @virtualmethod
    def rasterize(self, area=None, pixfmt=None):
        pass

    @virtualmethod
    def get_pixbuf(self, x, y):
        "Return the pixel buffer that store the pixel at location (x, y)"
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

    def rasterize(self, area=None, pixfmt=None):
        if area:
            if pixfmt is None:
                pixfmt = self.__buf.pixfmt
            dest = _pixbuf.Pixbuf(pixfmt, *area[2:])
            self.__buf.blit(dest, 0, 0, *area)
            return dest
        buf = self.__buf
        return _pixbuf.Pixbuf(buf.pixfmt, buf.width, buf.height, buf)

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


class TileSurfaceSnapshot(dict):
    # These values are set in order to dirty_area returns 0 sized area
    dirty_area = (0, 0, 0, 0)

    def __init__(self, tiles, area=None):
        # Fast tiles copy
        dict.__init__(self, tiles)
        self._mod = {}  # will contains added tiles after reduce()
        self.area = area

        # mark all tiles as readonly:
        # A modification on a RO tile replaces it by new one
        # with ro set to False
        for tile in tiles.itervalues():
            tile.ro = True

    def reduce(self, surface):
        "Split modified and unmodified tiles by make a difference with the given surface content"

        # Set dirty area to invalid values
        # (but usefull with min/max computations)
        xmin = ymin = sys.maxint
        xmax = ymax = -sys.maxint - 1

        # Search for modifications (and additions!)
        for pos, tile in surface.tiles.iteritems():
            if not tile.ro:
                # Move added tiles into the other dict,
                # and update the dirty area

                self._mod[pos] = tile

                x = tile.x
                if xmin > x:
                    xmin = x

                x += tile.width
                if xmax < x:
                    xmax = x

                y = tile.y
                if ymin > y:
                    ymin = y

                y += tile.height
                if ymax < y:
                    ymax = y
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

    def copy(self):
        return self.__class__(self.pixfmt, self.x, self.y, self.width, self)

    def relative_blit(self, args):
        dst, x, y = args
        self.blit(dst, self.x - x, self.y - y)


class UnboundedTiledSurface(Surface):
    def __init__(self, pixfmt):
        super(UnboundedTiledSurface, self).__init__(pixfmt)

        self.__tilemgr = _tilemgr.UnboundedTileManager(Tile, pixfmt, True)

        # Aliases
        self.get_pixbuf = self.get_tile
        self.from_buffer = self.__tilemgr.from_buffer
        self.get_tiles = self.__tilemgr.get_tiles
        self.get_row_tile = self.__tilemgr.get_tile

    ### Surface implementation ###

    @property
    def empty(self):
        return not bool(self.__tilemgr.tiles)

    @property
    def bbox(self):
        return self.__tilemgr.bbox

    def clear(self):
        self.__tilemgr.tiles.clear()

    def copy(self, surface):
        assert isinstance(surface, UnboundedTiledSurface)
        src = surface.__tilemgr
        dst = self.__tilemgr
        dst.tiles.clear()
        for tile in src.tiles.itervalues():
            dst.set_tile(tile.copy(), tile.x, tile.y)

    def read_pixel(self, x, y):
        tile = self.__tilemgr.get_tile(x, y, False)
        if tile:
            return tile.get_pixel(int(x) - tile.x, int(y) - tile.y)

    def rasterize(self, area=None, pixfmt=None):
        if area is None:
            x, y, w, h = self.area
        else:
            x, y, w, h = area

        dst = _pixbuf.Pixbuf((pixfmt if pixfmt is not None else self.__tilemgr.pixfmt), w, h)
        dst.clear()

        self.foreach(Tile.relative_blit, area, (dst, x, y))

        return dst

    ### Only for UnboundedTiledSurface ###

    def foreach(self, cb, area=None, args=()):
        """Apply the given callback on tiles in given rect or all tiles.

        'cb' is a callable, called for each tile with args tuple as argument.
        'area' is a 4-tuple restricting tiles to the overlaping area.
        'args' are remaining arguments given as a tuple to 'cb' when called.
        """
        self.__tilemgr.foreach(cb, area, args)

    def snapshot(self):
        return TileSurfaceSnapshot(self.__tilemgr.tiles, self.area)

    def unsnapshot(self, snapshot, *args):
        snapshot.blit(self.__tilemgr.tiles, *args)

    def get_tile(self, *pos):
        t = self.__tilemgr.get_tile(*pos)
        if t.ro:
            t = t.copy()
            self.__tilemgr.set_tile(t, *pos)
        return t

    def from_png_buffer(self, *a, **k):
        self.from_buffer(_pixbuf.FORMAT_RGBA8_NOA, *a, **k)

    def cleanup(self):
        for k in tuple(k for k, v in self.__tilemgr.tiles.iteritems()
                       if v.empty()):
            del self.__tilemgr.tiles[k]

    def __iter__(self):
        return self.__tilemgr.tiles.itervalues()

    @property
    def area(self):
        area = self.__tilemgr.bbox
        if area:
            x, y, w, h = area
            return x, y, w-x+1, h-y+1

    @property
    def tiles(self):
        return self.__tilemgr.tiles

    @property
    def tile_size(self):
        return self.__tilemgr.tile_size
