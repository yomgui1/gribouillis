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

import model._pixbuf as _pixbuf
import model._tilemgr as _tilemgr
import model._cutils as _cutils

from utils import virtualmethod

__all__ = ['Surface', 'UnboundedTiledSurface', 'BoundedPlainSurface', 'TILE_SIZE']

TILE_SIZE = 64


class Surface(object):
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
        super(BoundedPlainSurface, self).__init__()
        self.pixfmt = pixfmt
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
    dirty_area = _cutils.Area()

    def __init__(self, tiles, area=None):
        # Fast tiles copy
        dict.__init__(self, tiles)
        self._mod = {}  # will contains added tiles after reduce()
        self.area = area

        # mark all tiles as readonly:
        # A modification on a RO tile replaces it by new one
        # with ro set to False
        for tile in tiles.values():
            tile.ro = True

    def reduce(self, surface):
        "Split modified and unmodified tiles by make a difference with the given surface content"

        # Set dirty area to invalid values
        # (but usefull with min/max computations)
        xmin = ymin = sys.maxsize // 2
        xmax = ymax = -sys.maxsize // 2 - 1

        # Search for modifications (and additions!)
        for pos, tile in surface.tiles.items():
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
            self.dirty_area = _cutils.area_from_bbox(xmin, ymin, xmax, ymax)
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
        return sum(t.memsize for t in self.values()) + sum(t.memsize for t in self._mod.values())


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

    def gen_mipmap(self):
        pass


class UnboundedTiledSurface(Surface):
    def __init__(self, pixfmt, size=_tilemgr.TILE_DEFAULT_SIZE):
        Surface.__init__(self)
        self.__tilemgr = _tilemgr.UnboundedTileManager(Tile, pixfmt, True, size)

        # Aliases
        self.get_pixbuf = self.get_tile
        self.from_buffer = self.__tilemgr.from_buffer
        self.get_tiles = self.__tilemgr.get_tiles
        self.get_raw_tile = self.__tilemgr.get_tile

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
        for tile in src.tiles.values():
            dst.set_tile(tile.copy(), tile.x, tile.y)

    def read_pixel(self, x, y):
        tile = self.__tilemgr.get_tile(x, y, False)
        if tile:
            return tile.get_pixel(int(x) - tile.x, int(y) - tile.y)

    def rasterize(self, area, x0, y0, pixfmt=None, destination=None):
        if destination is None:
            destination = _pixbuf.Pixbuf((pixfmt if pixfmt is not None else self.__tilemgr.pixfmt), area.w, area.h)
        self.foreach(Tile.relative_blit, area, destination, int(x0), int(y0))
        return destination

    ### Only for UnboundedTiledSurface ###

    def foreach(self, cb, area, *args, **kwds):
        """Apply the given callback on tiles in given rect or all tiles.

        'cb' is a callable, called for each tile with args tuple as argument.
        'area' is a 4-tuple restricting tiles to the overlaping area.
        'args' are remaining arguments given as a tuple to 'cb' when called.
        """
        self.__tilemgr.foreach(cb, tuple(area), args, kwds.get("create", False))

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
        for k in tuple(k for k, v in self.__tilemgr.tiles.items() if v.empty()):
            del self.__tilemgr.tiles[k]

    def __iter__(self):
        return self.__tilemgr.tiles.values()

    @property
    def area(self):
        area = self.__tilemgr.bbox
        if area:
            x, y, w, h = area
            return x, y, w - x + 1, h - y + 1

    @property
    def tiles(self):
        return self.__tilemgr.tiles

    @property
    def tile_size(self):
        return self.__tilemgr.tile_size

    @property
    def pixfmt(self):
        return self.__tilemgr.pixfmt
