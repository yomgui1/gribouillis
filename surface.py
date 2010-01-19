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
    
    def __new__(cl, pixfmt, **kwds):
        return _pixarray.PixelArray.__new__(cl, T_SIZE, T_SIZE, pixfmt)

    def __init__(self, pixfmt, clear=True):
        #self.clear = self.zero
        self.bg = False

        if clear:
            self.zero()

    def GetMemoryUsed(self):
        return self.BytesPerRow * self.Height

    def copy(self):
        o = Tile(self.pixfmt, clear=False)
        o.from_pixarray(self)
        #o.clear = o.zero
        o.bg = self.bg
        return o


class Surface(object):
    MODE2PIXFMT = {
        'RGB8'   : _pixarray.PIXFMT_RGB_8,
        'RGBA8'  : _pixarray.PIXFMT_RGBA_8,
        'CMYK8'  : _pixarray.PIXFMT_CMYK_8,
        'ARGB8'  : _pixarray.PIXFMT_ARGB_8,
        'RGBA15X': _pixarray.PIXFMT_RGBA_15X,
        'CMYK15X': _pixarray.PIXFMT_CMYKA_15X,
    }

    def __init__(self, mode):
        self.pixfmt = Surface.MODE2PIXFMT[mode]

    def GetBuffer(self, x, y, read=True, bg=None):
        pass # subclass implemented
    
    def Clear(self):
        pass # subclass implemented

    bbox = property() # subclass implemented


class BoundedSurface(Surface):
    def __init__(self, width, height, mode):
        super(BoundedSurface, self).__init__(mode) 
        self.width = width
        self.height = height
        self._buf = _pixarray.PixelArray(width, height, self.pixfmt)

    def GetBuffer(self, x, y, read=True, bg=None):
        return self._buf

    def Clear(self):
        self._buf.zero()

    @property
    def bbox(self):
        return 0, 0, self.width, self.height


class TiledSurface(Surface):
    def __init__(self, mode, bg=None):
        super(TiledSurface, self).__init__(mode)
        self.tiles = {}
        if bg:
            assert isinstance(bg, Tile)
            assert bg.pixfmt == self.pixfmt
            self._bg = bg # XXX: copy() ?
        else:
            self._bg = Tile(self.pixfmt)
        self._bg.bg = True

    @property
    def background(self):
        "It's the background tile"
        return self._bg

    def __len__(self):
        return len(self.tiles)

    def GetMemoryUsed(self):
        return len(self) * self._bg.GetMemoryUsed()

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
            self._bg.x = x*T_SIZE
            self._bg.y = y*T_SIZE
            return self._bg

        tile = Tile(self.pixfmt, clear=clear)
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

    def Cleanup(self): # Destructive operation, destroy the undo historic
        dead = [ k for k,v in self.tiles.iteritems() if not v ]
        for k in dead:
            del self.tiles[k]
        print len(self.tiles)

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

    def IterRenderedPixelArray(self, mode='RGBA8'):
        fmt = Surface.MODE2PIXFMT[mode] 
        pa = _pixarray.PixelArray(T_SIZE, T_SIZE, fmt)
        pa.zero() 
        
        if mode in ('RGBA8', 'ARGB8'):
            if mode == 'RGBA8':
                blit = _pixarray.rgba15x_to_rgba8
            else:
                blit = _pixarray.rgba15x_to_argb8
        elif mode == 'RGB8':
            blit = _pixarray.rgb15ax_to_rgb8
        else:
            raise ValueError("Unsupported mode '%s'" % mode)
  
        for buf in self.IterPixelArray():
            blit(buf, pa)
            pa.x = buf.x
            pa.y = buf.y
            yield pa

    def RenderAsPixelArray(self, mode='RGBA8'):
        minx, miny, w, h = self.bbox
        fmt = Surface.MODE2PIXFMT[mode]
        pa = _pixarray.PixelArray(w, h, fmt)
        pa.zero() 
        
        if mode in ('RGBA8', 'ARGB8'):
            if mode == 'RGBA8':
                blit = _pixarray.rgba15x_to_rgba8
            else:
                blit = _pixarray.rgba15x_to_argb8
        elif mode == 'RGB8':
            blit = _pixarray.rgba15x_to_rgb8
        else:
            raise ValueError("Unsupported mode '%s'" % mode)

        for buf in self.IterPixelArray():
            blit(buf, pa, buf.x-minx, buf.y-miny)
            
        return pa

    def ExportAsPILImage(self, mode='RGBA8'):
        pa = self.RenderAsPixelArray(mode)
        if mode == 'RGBA8':
            mode = 'RGBA'
        elif mode == 'RGB8':
            mode = 'RGB'
        else:
            raise ValueError("Unsupported mode '%s'" % mode)
        return Image.frombuffer(mode, (pa.Width, pa.Height), pa, 'raw', mode, 0, 1)

    def PickColor(self, x, y):
        buf = self.GetBuffer(x, y)
        return buf.pick_color(x - buf.x, y - buf.y)
