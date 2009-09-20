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

import _pixbuf
from surface import TiledSurface, T_SIZE
from brush import Brush

class DummyBrush:
    "Class used when no brush is set for a LayerModel"
    def InitDraw(self, *a):
        pass

    def Draw(self, *a, **k):
        return tuple()


class LayerModel(object):
    def __init__(self):
        self._layers = []
        self._active = self.AddLayer()
        self._rsurface = TiledSurface(nc=3, bpc=8) # RGB 8-bits per component surface for display
        self._brush = DummyBrush() # that gives a way to remove some 'if' sentences...

    def SetBrush(self, b):
        assert isinstance(b, Brush)
        self._brush = b

    def AddLayer(self):
        s = TiledSurface()
        self._layers.append(s)
        return s

    def MoveBrush(self, *args):
        """Move current brush on the active layer.
        This action is not supposed to draw anything, jsut prepare the brush to.
        """
        self._brush.InitBrush(self._active, *args)

    def Draw(self, *args, **kwds):
        for buf in self._brush.Draw(*args, **kwds):
            # blit on the rendering surface modified buffers from the active surface
            rbuf = self._rsurface.GetBuffer(buf.x, buf.y, read=False)
            rbuf.zero()
            _pixbuf.bltalpha_argb15x_to_rgb8(buf, rbuf);
            yield rbuf
            

    def GetRenderBuffers(self, *args):
        xmin, ymin, xmax, ymax = [ int(x) for x in args ]
        for ty in xrange(ymin, ymax+T_SIZE-1, T_SIZE):
            for tx in xrange(xmin, xmax+T_SIZE-1, T_SIZE):
                yield self._rsurface.GetBuffer(tx, ty)
