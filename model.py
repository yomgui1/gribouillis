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

from __future__ import with_statement

__all__ = ('TiledModel', 'SimpleTiledModel')

import _pixarray
from surface import TiledSurface, T_SIZE, Tile
from brush import Brush, DummyBrush
from stroke import StrokeRecord
import PIL.Image as Image
from openraster import *
import png, os

class TiledModel(object):
    """TiledModel(colormodel='RGB') -> instance

    This class shall not be used as it, but shall be used to create drawing models.
    Subclass it and define methods marked to be defined by subclasses.
    """

    
    def __init__(self, colormodel='RGB'):
        if colormodel == 'RGB':
            self._colormodel = 'RGBA15X'

            # TODO: pa shall detect that automatically
            self._rcompose = _pixarray.compose_rgba15x_to_rgb8
        elif colormodel == 'CMYK':
            raise NotImplementedError("CMYK model are not supported yet")

            self._colormodel = 'CMYK15X'
            def render_cmyk(src, dst, tmp=Tile(_pixarray.PIXFMT_CMYK_8)):
                # TODO: CMS for transform a CMYK8 to RGB8 pa
                pass
            self._rcompose = render_cmyk
        
        self._rsurface = TiledSurface(mode='RGB8')
        self._brush = DummyBrush() # that gives a way to remove some 'if' sentences...

        # Some model data (Christoph... again you!)
        self.info = dict()
        dpi = (72, 72)
        self.info['DPI'] = dpi
        self.info['ResolutionUnit'] = 'in'
        self.info['XResolution'] = dpi[0] # Number of pixels per ResolutionUnit on the X-axis
        self.info['YResolution'] = dpi[1] # Number of pixels per ResolutionUnit on the Y-axis
        
    def Clear(self):
        self._rsurface.Clear()
        self._strokes = []

    def Cleanup(self):
        pass # nothing to do by default

    def GetRenderBuffers(self, *args):
        """GetRenderBuffers(xmin, ymin, xmax, ymax) -> generator

        Return a generator object that give list of rendered pixels buffers
        to redraw the damaged surface under the bounding box given as parameters.

        Rendered buffers can be used by a View class for system rendering.
        """
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
        self._rsurface.background.from_string(im.tostring())
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

    def SaveAsOpenRaster(self, filename):
        pass # Must be implemented by subclasses


class SimpleTiledModel(TiledModel):
    """
    2 working color spaces supported: RGB and CMYK.
    """

    def __init__(self, *args, **kwds):
        super(SimpleTiledModel, self).__init__(*args, **kwds)
        self._surface = TiledSurface(self._colormodel)

    def Clear(self):
        super(SimpleTiledModel, self).Clear() # clear the render surface
        self._surface.Clear() # clear the draw surface

    def Cleanup(self):
        self._rsurface.Cleanup()
        self._surface.Cleanup()

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
        if not rbuf.bg:
            rbuf.from_pixarray(self._rsurface.background)
        
        # blit on the rendering surface modified buffers from the active surface
        self._rcompose(buf, rbuf)
        buf.Damaged = False
        return rbuf

    def RenderStroke(self, stroke):
        return (self.RenderBuffer(buf) for buf in self._brush.DrawStroke(stroke))

    def AsPILImage(self, mode='RGBA'):
        return self._surface.ExportAsPILImage(mode)

    def AsPixelArray(self, mode='RGBA'):
        return self._surface.RenderAsPixelArray(mode)

    def Undo(self):
        super(SimpleTiledModel, self).Undo()
        self._surface.Undo()

    def Redo(self):
        super(SimpleTiledModel, self).Undo()
        self._surface.Undo()

    def SaveAsOpenRaster(self, filename):
        with OpenRasterFileWriter(filename, extra=self.info) as ora:
            ora.AddSurface("Main", self._surface)

    def SaveAsPNG(self, filename, compression=6):
        pa = self._surface.RenderAsPixelArray(mode='RGBA8')
        writer = png.Writer(width=pa.Width, height=pa.Height, alpha=True, bitdepth=8, compression=compression)
        with open(filename, 'wb') as outfile:
            writer.write_array(outfile, IntegerBuffer(pa))

    def SaveAsJPEG(self, filename, quality=95):
        im = self.AsPILImage('RGBA')
        im.save(filename, 'JPEG', optimize=True, dpi=self.info["DPI"], quality=quality)

    def LoadFromOpenRaster(self, filename):
        self.Clear()
        with OpenRasterFileReader(filename) as ora:
            a = ora.GetImageAttributes()
            self.info = a.copy()
            w = int(self.info.pop('w'))
            h = int(self.info.pop('h'))
            y = int(self.info.pop('x'))
            x = int(self.info.pop('y'))
            self.info.pop('name')
            tmpbuf = _pixarray.PixelArray(T_SIZE, T_SIZE, self._surface.MODE2PIXFMT['RGBA8'])
            for x, y, pixels in ora.GetSurfacePixels("Main", T_SIZE, T_SIZE):
                buf = self._surface.GetBuffer(x, y, read=False, clear=False)
                tmpbuf.from_string(pixels)
                _pixarray.rgba8_to_rgba15x(tmpbuf, buf)
                self.RenderBuffer(buf)
        return x, y, w, h

    def LoadFromPIL(self, im):
        self.Clear()
        im = im.convert('RGBA')
        w, h = im.size
        tmpbuf = _pixarray.PixelArray(T_SIZE, T_SIZE, self._surface.MODE2PIXFMT['RGBA8'])
        for sy in xrange(0, h, T_SIZE):
            for sx in xrange(0, w, T_SIZE):
                tile = im.crop((sx, sy, sx+T_SIZE, sy+T_SIZE))
                tmpbuf.from_string(tile.tostring())
                buf = self._surface.GetBuffer(sx, sy, read=False, clear=False)
                _pixarray.rgba8_to_rgba15x(tmpbuf, buf)
                self.RenderBuffer(buf)
        return 0, 0, w, h

    def GetMemoryUsed(self):
        x = self._surface.GetMemoryUsed()
        return x + self._rsurface.GetMemoryUsed(), x

    def PickColor(self, x, y):
        return self._surface.PickColor(x, y)

    bbox = property(fget=lambda self: self._surface.bbox)
