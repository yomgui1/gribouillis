###############################################################################
# Copyright (c) 2009 Guillaume Roguez
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

import PIL.Image as image
import _pixarray

T_SIZE = 64

class Tile:
    def __init__(self, nc, bpc):
        # pixel buffer, 'bpc' bit per composent, nc composent
        self.pixels = _pixarray.PixelArray(T_SIZE, T_SIZE, nc, bpc)
        self.Clear()

    def Clear(self):
        self.pixels.zero()


class Surface(object):
    def GetBuffer(self, x, y, read=True, clear=False):
        pass # subclass implemented
    
    def Clear(self):
        pass # subclass implemented

    bbox = property() # subclass implemented


class TiledSurface(Surface):
    def __init__(self, nc=4, bpc=16):
        super(TiledSurface, self).__init__()
        self.tiles = {}
        self._nc = nc
        self._bpc = bpc
        self._ro_tile = Tile(nc, bpc)

    def GetBuffer(self, x, y, read=True, clear=False):
        """GetBuffer(x, y, read=True, clear=False) -> pixel array

        Returns the pixel buffer and its left-top corner, containing the point p=(x, y).
        If no tile exist yet, return a read only buffer if read is True,
        otherwhise create a new tile and returns it.
        If clear is true and read is false, the buffer is cleared.
        """

        x = int(x // T_SIZE)
        y = int(y // T_SIZE)

        tile = self.tiles.get((x, y))
        if tile:
            if clear and not read: tile.Clear()
            return tile.pixels
        elif read:
            self._ro_tile.pixels.x = x*T_SIZE
            self._ro_tile.pixels.y = y*T_SIZE
            return self._ro_tile.pixels
        else:
            tile = Tile(self._nc, self._bpc)
            tile.pixels.x = x*T_SIZE
            tile.pixels.y = y*T_SIZE
            self.tiles[(x, y)] = tile
            return tile.pixels

    def __iter__(self):
        return self

    def next(self):
        for tile in self.tiles.itervalues():
            yield tile.pixels

    def Clear(self):
        for tile in self.tiles.itervalues():
            tile.Clear()

    @property
    def bbox(self):
        minx = maxx = miny = maxy = 0
        for buf in self:
            minx = min(buf.x, minx)
            miny = min(buf.y, miny)
            maxx = max(buf.x+buf.Width-1, maxx)
            maxy = max(buf.y+buf.Height-1, maxy)
        return minx, miny, maxx, maxy

    def RenderAsPixelArray(self, format='RGBA'):
        minx, miny, maxx, maxy = self.bbox
        w = maxx-minx+1
        h = maxy-miny+1
        if format in ('RGBA', 'ARGB'):
            pa = _pixarray.PixelArray(w, h, 4, 8)
            if format == 'RGBA':
                blit = _pixarray.argb15x_to_rgba8
            else:
                blit = _pixarray.argb15x_to_argb8
        elif format == 'RGB':
            pa = _pixarray.PixelArray(w, h, 3, 8)
            blit = _pixarray.argb15x_to_rgb8
            
        for buf in self:
            blit(buf, pa, buf.x-minx, buf.y-miny)
        return pa
    
    def ImportFromPILImage(self, im, w, h):
        im = im.convert('RGB')
        src = _pixarray.PixelArray(T_SIZE, T_SIZE, 3, 8)
        for ty in xrange(0, h, T_SIZE):
            for tx in xrange(0, w, T_SIZE):
                buf = self.GetBuffer(tx, ty, read=False)
                sx = min(w, tx+T_SIZE)
                sy = min(h, ty+T_SIZE)
                src.from_string(im.crop((tx, ty, sx, sy)).tostring())
                _pixarray.rgb8_to_argb8(src, buf)
