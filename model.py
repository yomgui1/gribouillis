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
from surface import TiledSurface, T_SIZE, Tile
from brush import Brush, DummyBrush
from stroke import StrokeRecord
import PIL.Image as Image

class Model(object):
    """ Model() -> instance

    This class shall not be used as it, but shall be used to create drawing models.
    Subclass it and define methods marked to be defined by subclasses.
    """

    
    def __init__(self):
        self._bg = Tile(nc=3, bpc=8) 
        self._rsurface = TiledSurface(nc=3, bpc=8, bg=self._bg) # RGB 8-bits per component surface for display

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

    def UseBrush(self, b):
        assert isinstance(b, Brush)
        self._brush = b

    def InitializeDrawAction(self, pos):
        self.InitBrush(pos)

        # Undo management at stroke level
        self._stroke_rec = StrokeRecord(pos)
        
        # Undo management at surface level
        self.InitWriteContext()
        
    def FinalizeDrawAction(self, cancelled=True):
        self.TermWriteContext(cancelled)
        
        if not cancelled and self._stroke_rec:
            self._strokes.append(self._stroke_rec)
        self._stroke_rec = None

    def Undo(self):
        # TODO: undo last stroke record
        pass

    def Redo(self):
        # TODO: redo redo stroke record
        pass

    def RecordStroke(self, stroke):
        self._stroke_rec.Add(stroke)

    def LoadBackground(self, filename):
        im = Image.open(filename).convert('RGB')
        im = im.crop((0, 0, T_SIZE, T_SIZE))
        self._bg.from_string(im.tostring())
        del im
        self._rsurface.Clear()
        self.RenderFull()

    def InitBrush(self, pos):
        pass # Must be implemented by subclasses

    def RenderFull(self):
        pass # Must be implemented by subclasses   

    def RenderStroke(self, stroke):
        pass # Must be implemented by subclasses

    def AsPILImage(self):
        pass # Must be implemented by subclasses

    def InitWriteContext(self):
        pass # Must be implemented by subclasses

    def TermWriteContext(self, ok):
        pass # Must be implemented by subclasses


class SimpleModel(Model):
    def __init__(self):
        self._surface = TiledSurface(nc=4, bpc=16) # ARGB surface

        # Called in last because super call Clear() at end of its __init__()
        super(SimpleModel, self).__init__()

    def Clear(self):
        super(SimpleModel, self).Clear() # clear the render surface
        self._surface.Clear() # clear the draw surface

    def InitWriteContext(self):
        self._surface.InitWrite()

    def TermWriteContext(self, kill=False):
        self._surface.TermWrite(kill)

    def InitBrush(self, pos):
        self._brush.InitDraw(self._surface, pos)

    def RenderFull(self):
        for buf in self._surface.IterPixelArray():
            self.RenderBuffer(buf)

    def RenderBuffer(self, buf):
        # Get a RGB buffer for rendering
        rbuf = self._rsurface.GetBuffer(buf.x, buf.y, read=False, clear=False)
        
        # Copy the background buffer
        rbuf.from_pixarray(self._bg)
        
        # blit on the rendering surface modified buffers from the active surface
        _pixarray.bltalpha_argb15x_to_rgb8(buf, rbuf)
        buf.Damaged = False
        return rbuf

    def RenderStroke(self, stroke):
        return (self.RenderBuffer(buf) for buf in self._brush.DrawStroke(stroke))

    def AsPILImage(self, mode='RGBA'):
        return self._surface.ExportAsPILImage(mode)

    def AsPixelArray(self, mode='RGBA'):
        return self._surface.RenderAsPixelArray(mode)

    def Undo(self):
        super(SimpleModel, self).Undo()
        self._surface.Undo()

    def Redo(self):
        super(SimpleModel, self).Undo()
        self._surface.Undo()

    bbox = property(fget=lambda self: self._surface.bbox)
