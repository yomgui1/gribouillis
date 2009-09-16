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

from surface import TiledSurface, T_SIZE
from brush import Brush

class LayerModel(object):
    def __init__(self):
        self._layers = []
        self._active = self.AddLayer()
        self._rsurface = TiledSurface()
        self._brush = None

        from PIL.Image import open

        im = open("backgrounds/03_check1.png")
        im.load()
        _, _, w, h = im.getbbox()
        self._rsurface.ImportFromPILImage(im, w, h)

    def SetBrush(self, b):
        assert isinstance(b, Brush)
        self._brush = b

    def AddLayer(self):
        s = TiledSurface()
        self._layers.append(s)
        return s

    def BrushMove(self, *a):
        if self._brush:
            self._brush.Move(self._rsurface, *a)

    def BrushDraw(self, *a, **kwds):
        if self._brush:
            self._brush.Draw(self._rsurface, *a, **kwds)

    def GetBuffers(self, xmin, ymin, xmax, ymax):
        xmin = int(xmin)
        xmax = int(xmax)
        ymin = int(ymin)
        ymax = int(ymax)
        for ty in xrange(ymin, ymax+1, T_SIZE):
            for tx in xrange(xmin, xmax+1, T_SIZE):
                buf = self._rsurface.GetTileBuffer(tx, ty, create=True)
                yield buf, tx, ty
