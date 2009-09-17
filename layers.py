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
import lcms

class LayerModel(object):
    def __init__(self):
        self._layers = []
        self._active = self.AddLayer()
        self._rsurface = TiledSurface(bpc=8) # ARGB 8-bits per component surface for display
        self.tmpbuf = _pixbuf.PixelArray(T_SIZE, T_SIZE, 3, 8) # can used externaly for rendering
        self._brush = None
        self.cms_transform = None
        
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
            self._brush.InitDraw(self._rsurface, *a)

    def BrushDraw(self, *a, **kwds):
        if self._brush:
            return self._brush.Draw(*a, **kwds)

    def GetRenderBuffers(self, xmin, ymin, xmax, ymax):
        xmin = int(xmin)
        xmax = int(xmax)
        ymin = int(ymin)
        ymax = int(ymax)
        for ty in xrange(ymin, ymax+T_SIZE-1, T_SIZE):
            for tx in xrange(xmin, xmax+T_SIZE-1, T_SIZE):
                yield self._rsurface.GetBuffer(tx, ty)

    def PreRenderProcessing(self, buf):
        if self.cms_transform:
            self.model.CMS_ApplyTransform(buf, self.tmpbuf)
            return self.tmpbuf
        return buf

    ## CMS ##

    def CMS_SetInputProfile(self, profile):
        self.cms_ip = profile

    def CMS_SetOutputProfile(self, profile):
        self.cms_op = profile

    def CMS_InitTransform(self):
        del self.cms_transform
        self.cms_transform = lcms.TransformHandler(self.cms_in, lcms.TYPE_RGB_8,
                                                   self.cms_op, lcms.TYPE_RGB_8,
                                                   lcms.INTENT_PERCEPTUAL)

    def CMS_ApplyTransform(self, inbuf, outbuf):
        self.cms_transform.apply(inbuf, outbuf, outbuf.Width * outbuf.Height)
