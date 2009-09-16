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
import sys

sys.path.append('Libs/python2.5/site-packages')
from _pixbuf import PixelArray
import _pixbuf

T_SIZE = 64
DEBUG = True

class Tile:
    def __init__(self, bpc):
        # ARGB buffer, 16-bits per conmposants but we'll using only 15 of them
        self.pixels = PixelArray(T_SIZE, T_SIZE, 4, bpc)
        self.pixels.one()

class Surface(object):
    pass

class TiledSurface(Surface):
    def __init__(self, bpc=16):
        Surface.__init__(self)
        self.tiles = {}
        self._bpc = bpc
        self._ro_tile = Tile(self._bpc)
        if DEBUG and bpc == 8:
            self._red = PixelArray(T_SIZE, T_SIZE, 4, 8)
            self._green = PixelArray(T_SIZE, T_SIZE, 4, 8)
            self._blue = PixelArray(T_SIZE, T_SIZE, 4, 8)
            self._red.from_string("\xff\xff\x00\x00"*T_SIZE**2)
            self._green.from_string("\xff\x00\xff\x00"*T_SIZE**2)
            self._blue.from_string("\xff\x00\x00\xff"*T_SIZE**2)

    def GetBuffer(self, x, y, read=True):
        """GetBuffer(x, y, read=True) -> (pixel buffer, bx, by)

        Returns the pixel buffer and its left-top corner, containing the point p=(x, y).
        If no tile exist yet, return a read only buffer if read is True,
        otherwhise create a new tile and returns it.
        """

        x = int(x // T_SIZE)
        y = int(y // T_SIZE)

        tile = self.tiles.get((x, y))
        if tile:
            return tile.pixels, x*T_SIZE, y*T_SIZE
        elif read:
            return self._ro_tile.pixels, x*T_SIZE, y*T_SIZE
        else:
            tile = Tile(self._bpc) 
            self.tiles[(x, y)] = tile 
            
            if DEBUG and self._bpc == 8:
                if x == y == 0:
                    tile.pixels.from_pixarray(self._blue)
                elif (x+y) % 2:
                    tile.pixels.from_pixarray(self._green)
                else:
                    tile.pixels.from_pixarray(self._red)
            
            return tile.pixels, x*T_SIZE, y*T_SIZE
    
    def ImportFromPILImage(self, im, w, h):
        im = im.convert('RGB')
        src = PixelArray(T_SIZE, T_SIZE, 3, 8)
        for ty in xrange(0, h, T_SIZE):
            for tx in xrange(0, w, T_SIZE):
                buf, _, _ = self.GetBuffer(tx, ty, read=False)
                buf.one()
                sx = min(w, tx+T_SIZE)
                sy = min(h, ty+T_SIZE)
                src.from_string(im.crop((tx, ty, sx, sy)).tostring())
                _pixbuf.rgb8_to_argb8(src, buf)
