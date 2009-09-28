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

import zlib, itertools, os, png
import xml.etree.ElementTree as ET
from CStringIO import StringIO

def ienumerate(iterable):
    return itertools.izip(itertools.count(), iterable)

class OpenRasterFile:
    def __init__(self, filename, write=False):
        if write:
            self.init_write(filename)
        else:
            self.init_read(filename)

    def init_write(self, filename):
        if os.path.isfile(filename):
            tmpname = self.fp.name+'@'
        else:
            tmpname = filename
        self.filename = filename
        self.tmpname = tmpname
        self.z = zipfile.ZipFile(tmpname, 'w', compression=zipfile.ZIP_STORED)
        self.z.writestr('mimetype', 'image/openraster')
        self.stack_list = []
        
    def AddSurface(self, name, surface):
        assert name
        
        sx, sy, w, h = surface.bbox
        stack = ET.Element('stack', None, x=sx, y=sy, name=name)
        self.stack_list.append((stack, sx, sy, w, h))
        
        for i, buf in ienumerate(surface.IterPixelArray()):
            src = 'data/'+name+'/buf_%lu.png' % i
            rbuf = surface.RenderAsPixelArray(mode='RGBA')
            x = buf.x-sx
            y = buf.y-sy
            ET.SubElement(stack, 'layer', None,
                          name='PixArray@%lux%lu' % (x, y),
                          x=x, y=y, src=src)

            outfile = StringIO()
            writer = png.Writer(buf.Width, buf.Height, alpha=True, bitdepth=8, compression=6)
            class IntegerBuffer(buf):
                def __init__(self, buf):
                    self.b = buffer(buf)
                    
                def __getslice__(self, start, stop):
                    return (ord(c) for c in self.b[start:stop])
                
            writer.write(outfile, IntegerBuffer(buf))
            self.z.write(outfile.getvalue(), src)
            write.close()

    def Close(self, attrib={}):
        if not stack_list:
            self.z.close()
            os.remove(self.tmpname)
            
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
        a.update(attrib)
        a['name'] = os.path.basename(self.filename)
        a['w'] = iw
        a['h'] = ih

        print "Image bbox:", (ix, iy, iw, ih)
        
        for stack, sx, sy, _, _ in self.stack_list:
            a = stack.attrib
            a['x'] = sx-ix
            a['y'] = sy-iy
            top_stack.append(stack)
            
        xml = ET.tostring(image, encoding='UTF-8')
        self.z.writestr('stack.xml', xml)
        self.z.close()
        
        if self.filename != self.tmpname:
            os.remove(self.filename)
            os.rename(self.tmpname, self.filename)
