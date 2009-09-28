##############################################################################
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

import zipfile, itertools, os, png
import xml.etree.ElementTree as ET
from cStringIO import StringIO

__all__ = ('OpenRasterFile',)

def ienumerate(iterable):
    return itertools.izip(itertools.count(), iterable)

class IntegerBuffer(object):
    def __init__(self, buf):
        self.b = buffer(buf)
        
    def __getslice__(self, start, stop):
        return list(ord(c) for c in self.b[start:stop])


class OpenRasterFile:
    def __init__(self, filename, write=False, **kwds):
        if write:
            self.init_write(filename, **kwds)
        else:
            self.init_read(filename, **kwds)

    def init_write(self, filename, **kwds):
        if os.path.isfile(filename):
            tmpname = filename+'@'
        else:
            tmpname = filename
        self.filename = filename
        self.tmpname = tmpname
        self.z = zipfile.ZipFile(tmpname, 'w', compression=zipfile.ZIP_STORED)
        self.z.writestr('mimetype', 'image/openraster')
        self.stack_list = []
        self.comp = kwds.get('compression', 6)
        self.extra = kwds.get('extra', {})
                
    def AddSurface(self, name, surface):
        assert name
        
        sx, sy, w, h = surface.bbox
        stack = ET.Element('stack', {}, x=str(sx), y=str(sy), name=name)
        self.stack_list.append((stack, sx, sy, w, h))
        
        for i, buf in ienumerate(surface.IterRenderedPixelArray()):
            src = 'data/'+name+'/buf_%lu.png' % i
            x = buf.x-sx
            y = buf.y-sy
            ET.SubElement(stack, 'layer', {},
                          name='PixArray@%lux%lu' % (x, y),
                          x=str(x), y=str(y), src=src)

            outfile = StringIO()
            writer = png.Writer(buf.Width, buf.Height, alpha=True, bitdepth=8, compression=self.comp)
            writer.write_array(outfile, IntegerBuffer(buf))
            self.z.writestr(src, outfile.getvalue())
            del writer

    def Close(self):
        if not self.stack_list:
            self.z.close()
            os.remove(self.tmpname)
            return

        image = ET.Element('image')
        top_stack = ET.SubElement(image, 'stack')

        # compute image bbox
        _, ix, iy, iw, ih = self.stack_list[0]
        for _, x, y, w, h in self.stack_list[1:]:
            if x < ix:
                ix = x
            if y < iy:
                iy = y
            if ix+iw < x+w:
                iw = w
            if iy+ih < y+h:
                ih = h

        a = image.attrib
        a.update((k, str(v)) for k,v in self.extra.iteritems())
        a['name'] = os.path.basename(self.filename)
        a['w'] = str(iw)
        a['h'] = str(ih)

        print "Image bbox:", (ix, iy, iw, ih)
        
        for stack, sx, sy, _, _ in self.stack_list:
            a = stack.attrib
            a['x'] = str(sx-ix)
            a['y'] = str(sy-iy)
            top_stack.append(stack)
            
        xml = ET.tostring(image, encoding='UTF-8')
        self.z.writestr('stack.xml', xml)
        self.z.close()
        
        if self.filename != self.tmpname:
            os.remove(self.filename)
            os.rename(self.tmpname, self.filename)
