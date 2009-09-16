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
from _raster import PixelArray

T_SIZE = 64
DEBUG = True

class Tile:
    def __init__(self):
        # ARGB buffer, 16-bits per conmposants but we'll using only 15 of them
        self.pixels = PixelArray(T_SIZE, T_SIZE, 4, 16)
        self.pixels.one()

class Surface(object):
    pass

class TiledSurface(Surface):
    def __init__(self):
        Surface.__init__(self)
        self.tiles = {}

    def GetTileBuffer(self, x, y, create=False):
        """GetTileBuffer(x, y, create=False) -> Tile buffer

        Returns the tile buffer containing the point p=(x, y).
        If no tile exist yet, return None if create is False,
        otherwhise create a new tile and returns it.
        """

        p = (int(x // T_SIZE), int(y // T_SIZE))
        tile = self.tiles.get(p)
        if tile:
            return tile.pixels
        elif create:
            tile = Tile()
            self.tiles[p] = tile
            return tile.pixels
    
    def ImportFromPILImage(self, im, w, h):
        im = im.convert('RGB')
        src = PixelArray(T_SIZE, T_SIZE, 3, 8)
        for ty in xrange(0, h, T_SIZE):
            for tx in xrange(0, w, T_SIZE):
                buf = self.GetTileBuffer(tx, ty, create=True)
                buf.one()
                sx = min(w, tx+T_SIZE)
                sy = min(h, ty+T_SIZE)
                src.from_string(im.crop((tx, ty, sx, sy)).tostring())
                buf.rgb8_to_argb15x(src)
