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

__all__ = ('OpenRasterFileWriter', 'OpenRasterFileReader', 'IntegerBuffer')

def ienumerate(iterable):
    return itertools.izip(itertools.count(), iterable)


class IntegerBuffer(object):
    def __init__(self, buf):
        self.b = buffer(buf)
        
    def __getslice__(self, start, stop):
        return tuple(ord(c) for c in self.b[start:stop])


class OpenRasterFileReader:
    def __init__(self, filename, **kwds):
        self.filename = filename
        self.z = zipfile.ZipFile(filename, 'r')
        s = self.z.read('mimetype').strip()
        xml = self.z.read('stack.xml')
        self.image = ET.fromstring(xml)
        a = self.image.attrib
        self.ix = int(a.get('x', 0))
        self.iy = int(a.get('y', 0))
        self.top_stack = image.find('stack')

    def GetImageAttributes(self):
        return self.image.attrib

    def GetSurfacePixels(self, name, waited_width, waited_height):
        for item in self.top_stack:
            if item.tag != 'stack':
                print "[*DBG*] Warning: ignoring item %s in top stack" % item.tag
                continue

            a = item.attrib
            if a.get('name') != name: continue
            
            sx = int(a.get('x', 0)) + self.ix
            sy = int(a.get('y', 0)) + self.iy
            for layer in item:
                if item.tag != 'layer':
                    print "[*DBG*] Warning: ignoring item %s in stack %s" % (item.tag, name)
                    continue
                
                a = item.attrib
                src = a.get(src, '')
                if not src.lowers().endswith('.png'):
                    print "[*DBG*] Warning: ignoring layer src %s" % src
                    continue

                x = int(a.get('x', 0)) + sx
                y = int(a.get('y', 0)) + sy

                # return string of PNG data
                reader = png.Reader(bytes=z.read(src))
                w, h, pixels, meta = reader.asRGBA8()
                if w != waited_width or h != waited_height:
                    print "[*DBG*] Warning: ignoring unwanted tile size (%lux%lu)" % (w, h)
                    continue
                yield x, y, (chr(v) for v in pixels)

    def close(self):
        self.z.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

        
class OpenRasterFileWriter:
    def __init__(self, filename, **kwds):
        self.filename = filename
        self.z = zipfile.ZipFile(filename, 'w', compression=zipfile.ZIP_STORED)
        self.z.writestr('mimetype', 'image/openraster')
        self.stack_list = []
        self.comp = kwds.get('compression', 6)
        self.extra = kwds.get('extra', {})
        self.ix = self.iy = 1<<32
        self.iw = self.ih = 0

    def AddSurface(self, name, surface):
        assert name
        
        sx, sy, w, h = surface.bbox

        # Update image size
        if sx < self.ix:
            self.ix = sx
        if sy < self.iy:
            self.iy = sy
        if self.ix+self.iw < sx+w:
            self.iw = w
        if self.iy+self.ih < sy+h:
            self.ih = h

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

    def close(self):
        if not self.stack_list:
            self.z.close()
            os.remove(self.filename)
            return

        image = ET.Element('image')
        top_stack = ET.SubElement(image, 'stack')

        a = image.attrib
        a.update((k, str(v)) for k,v in self.extra.iteritems())
        a['name'] = os.path.basename(self.filename) # ORA optional
        a['w'] = str(self.iw) # ORA mandatory
        a['h'] = str(self.ih) # ORA mandatory
        a['x'] = str(self.ix) # extra for Gribouillis
        a['y'] = str(self.iy) # extra for Gribouillis
        
        for stack, sx, sy, _, _ in self.stack_list:
            a = stack.attrib
            a['x'] = str(sx-self.ix)
            a['y'] = str(sy-self.iy)
            top_stack.append(stack)
            
        xml = ET.tostring(image, encoding='UTF-8')
        self.z.writestr('stack.xml', xml)
        self.z.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
