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

__all__ = ('Model', 'SimpleModel')

import _pixarray
from surface import TiledSurface, T_SIZE
from brush import Brush, DummyBrush
from stroke import StrokeRecord

class Model(object):
    """ Model() -> instance

    This class shall not be used as it, but shall be used to create drawing models.
    Subclass it and define methods marked to be defined by subclasses.
    """

    
    def __init__(self):
        self._rsurface = TiledSurface(nc=3, bpc=8) # RGB 8-bits per component surface for display
        self._brush = DummyBrush() # that gives a way to remove some 'if' sentences...

        # Some model data (Christoph... again you!)
        self.info = dict()
        self.info['ResolutionX'] = 75 # Number of pixels for 1 inch on the X-axis
        self.info['ResolutionY'] = 75 # Number of pixels for 1 inch on the Y-axis

        self.Clear()
        
    def Clear(self):
        self._rsurface.Clear()
        self._strokes = []

    def GetRenderBuffers(self, *args):
        xmin, ymin, xmax, ymax = [ int(x) for x in args ]
        for ty in xrange(ymin, ymax+T_SIZE-1, T_SIZE):
            for tx in xrange(xmin, xmax+T_SIZE-1, T_SIZE):
                yield self._rsurface.GetBuffer(tx, ty)

    def SetBrush(self, b):
        assert isinstance(b, Brush)
        self._brush = b

    def InitializeDrawAction(self, pos):
        self._stroke_rec = StrokeRecord(pos)
        self.InitBrush(pos)
        
    def FinalizeDrawAction(self, ok=True):
        self._strokes.append(self._stroke_rec)
        self._stroke_rec = None

    def RecordStroke(self, stroke):
        self._stroke_rec.Add(stroke)

    def InitBrush(self, pos):
        pass # Must be implemented by subclasses

    def RenderStroke(self, stroke):
        pass # Must be implemented by subclasses


class SimpleModel(Model):
    def __init__(self):
        self._surface = TiledSurface(nc=4, bpc=16) # ARGB surface

        # Called in last because super call Clear() at end of its __init__()
        super(SimpleModel, self).__init__()

    def Clear(self):
        super(SimpleModel, self).Clear() # clear the render surface
        self._surface.Clear() # clear the draw surface

    def InitBrush(self, pos):
        self._brush.Init(self._surface, pos)

    def RenderStroke(self, stroke):
        for buf in self._brush.DrawStroke(stroke):
            # blit on the rendering surface modified buffers from the active surface
            rbuf = self._rsurface.GetBuffer(buf.x, buf.y, read=False, clear=True)
            _pixarray.bltalpha_argb15x_to_rgb8(buf, rbuf);
            buf.Damaged = False    
            yield rbuf
