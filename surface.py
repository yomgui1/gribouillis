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

import PIL.Image as Image
import _pixarray

T_SIZE = 64

class Tile:
    def __init__(self, nc, bpc, clear=True):
        # pixel buffer, 'bpc' bit per composent, nc composent
        self.pixels = _pixarray.PixelArray(T_SIZE, T_SIZE, nc, bpc)
        if clear:
            self.Clear()

    def Clear(self):
        self.pixels.zero()

    def Copy(self):
        return self.pixels.copy()


class Surface(object):
    def GetBuffer(self, x, y, read=True, bg=None):
        pass # subclass implemented
    
    def Clear(self):
        pass # subclass implemented

    bbox = property() # subclass implemented


class TiledSurface(Surface):
    def __init__(self, nc=4, bpc=16, bg=None):
        super(TiledSurface, self).__init__()
        self.tiles = {}
        self._nc = nc
        self._bpc = bpc
        if bg:
            assert isinstance(bg, Tile)
            assert bg.pixels.BitsPerComponent == bpc
            assert bg.pixels.ComponentNumber == nc
            self._ro_tile = bg
        else:
            self._ro_tile = Tile(nc, bpc)

    def GetBuffer(self, x, y, read=True, clear=True):
        """GetBuffer(x, y, read=True, clear=True) -> pixel array

        Returns the pixel buffer and its left-top corner, containing the point p=(x, y).
        If no tile exist yet, return a read only buffer if read is True,
        otherwhise create a new tile and returns it.
        If clear, new created tiles are cleared before given.
        """

        x = int(x // T_SIZE)
        y = int(y // T_SIZE)

        tile = self.tiles.get((x, y))
        if tile:
            return tile.pixels
        elif read:
            self._ro_tile.pixels.x = x*T_SIZE
            self._ro_tile.pixels.y = y*T_SIZE
            return self._ro_tile.pixels
        else:
            tile = Tile(self._nc, self._bpc, clear=clear)
            tile.pixels.x = x*T_SIZE
            tile.pixels.y = y*T_SIZE
            self.tiles[(x, y)] = tile
            return tile.pixels

    def IterPixelArray(self):
        for tile in self.tiles.itervalues():
            yield tile.pixels

    def Clear(self):
        self.tiles.clear()

    @property
    def bbox(self):
        if not self.tiles:
            return (0,)*4
        minx = miny = 2<<31
        maxx = maxy = -2<<31
        for buf in self.IterPixelArray():
            minx = min(buf.x, minx)
            miny = min(buf.y, miny)
            maxx = max(buf.x+buf.Width, maxx)
            maxy = max(buf.y+buf.Height, maxy)
        return minx, miny, maxx-minx, maxy-miny

    def RenderAsPixelArray(self, mode='RGBA'):
        minx, miny, w, h = self.bbox
        if mode in ('RGBA', 'ARGB'):
            pa = _pixarray.PixelArray(w, h, 4, 8)
            if mode == 'RGBA':
                blit = _pixarray.argb15x_to_rgba8
            else:
                blit = _pixarray.argb15x_to_argb8
        elif mode == 'RGB':
            pa = _pixarray.PixelArray(w, h, 3, 8)
            blit = _pixarray.argb15x_to_rgb8
        else:
            raise ValueError("Unsupported mode '%s'" % mode)
            
        for buf in self.IterPixelArray():
            blit(buf, pa, buf.x-minx, buf.y-miny)
            
        return pa

    def ExportAsPILImage(self, mode='RGBA'):
        pa = self.RenderAsPixelArray(mode)
        return Image.frombuffer(mode, (pa.Width, pa.Height), pa, 'raw', mode, 0, 1)
    
    def ImportFromPILImage(self, im, w, h):
        im = im.convert('RGB') # TODO: need support of RGBA
        src = _pixarray.PixelArray(T_SIZE, T_SIZE, 3, 8)
        for ty in xrange(0, h, T_SIZE):
            for tx in xrange(0, w, T_SIZE):
                buf = self.GetBuffer(tx, ty, read=False)
                sx = min(w, tx+T_SIZE)
                sy = min(h, ty+T_SIZE)
                src.from_string(im.crop((tx, ty, sx, sy)).tostring())
                _pixarray.rgb8_to_argb8(src, buf)

