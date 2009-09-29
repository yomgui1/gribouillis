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

class Tile(_pixarray.PixelArray):
    # Saving memory, don't create a __dict__ object per instance
    #__slots__ = ('saved', 'clear')
    
    def __new__(cl, nc=4, bpc=16, clear=True):
        return _pixarray.PixelArray.__new__(cl, T_SIZE, T_SIZE, nc, bpc)

    def __init__(self, nc=4, bpc=16, clear=True):
        self.clear = self.zero
        self.ro = False

        if clear:
            self.clear()

    def copy(self):
        o = Tile(self.ComponentNumber, self.BitsPerComponent, clear=False)
        o.from_pixarray(self)
        o.clear = o.zero
        o.ro = self.ro
        return o


class Surface(object):
    def GetBuffer(self, x, y, read=True, bg=None):
        pass # subclass implemented
    
    def Clear(self):
        pass # subclass implemented

    bbox = property() # subclass implemented


class TiledSurface(Surface):
    def __init__(self, nc=4, bpc=16, bg=None):
        super(TiledSurface, self).__init__()
        self._nc = nc
        self._bpc = bpc
        self.tiles = {}
        if bg:
            assert isinstance(bg, Tile)
            assert bg.BitsPerComponent == bpc
            assert bg.ComponentNumber == nc
            self._ro_tile = bg
        else:
            self._ro_tile = Tile(nc, bpc)
        self._ro_tile.ro = True       

    def GetMemoryUsed(self):
        return len(self.tiles) * self._nc * self._bpc * T_SIZE**2 / 8

    def GetBuffer(self, x, y, read=True, clear=True):
        """GetBuffer(x, y, read=True, clear=True) -> pixel array

        Returns the pixel buffer and its left-top corner, containing the point p=(x, y).
        If no tile exist yet, return a read only buffer if read is True,
        otherwhise create a new tile and returns it.
        If clear, new created tiles are cleared before given.
        """

        x = int(x // T_SIZE)
        y = int(y // T_SIZE)
        k = (x, y)

        tile = self.tiles.get(k)
        if tile:
            return tile
        elif read:
            self._ro_tile.x = x*T_SIZE
            self._ro_tile.y = y*T_SIZE
            return self._ro_tile
        else:
            tile = Tile(self._nc, self._bpc, clear=clear)
            tile.x = x*T_SIZE
            tile.y = y*T_SIZE
            self.tiles[k] = tile
            return tile

    def IterPixelArray(self):
        return self.tiles.itervalues()

    def InitWrite(self):
        pass

    def TermWrite(self, kill):
        pass

    def Undo(self):
        pass

    def Redo(self):
        pass

    def Clear(self): # Destructive operation, destroy the undo historic
        self.tiles.clear()

    @property
    def bbox(self):
        if not self.tiles:
            return (0,)*4
        minx = miny = 1<<31
        maxx = maxy = -1<<31
        for buf in self.IterPixelArray():
            minx = min(buf.x, minx)
            miny = min(buf.y, miny)
            maxx = max(buf.x+buf.Width, maxx)
            maxy = max(buf.y+buf.Height, maxy)
        return minx, miny, maxx-minx, maxy-miny

    def IterRenderedPixelArray(self, mode='RGBA'):
        if mode in ('RGBA', 'ARGB'):
            pa = _pixarray.PixelArray(T_SIZE, T_SIZE, 4, 8)
            if mode == 'RGBA':
                blit = _pixarray.argb15x_to_rgba8
            else:
                blit = _pixarray.argb15x_to_argb8
        elif mode == 'RGB':
            pa = _pixarray.PixelArray(T_SIZE, T_SIZE, 3, 8)
            blit = _pixarray.argb15x_to_rgb8
        else:
            raise ValueError("Unsupported mode '%s'" % mode)
  
        for buf in self.IterPixelArray():
            blit(buf, pa)
            pa.x = buf.x
            pa.y = buf.y
            yield pa

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

        pa.zero()

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

