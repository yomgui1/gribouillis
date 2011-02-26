###############################################################################
# Copyright (c) 2009-2011 Guillaume Roguez
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

import zipfile, itertools, os
import xml.etree.ElementTree as ET
import PIL.Image as pil
from StringIO import StringIO
from math import ceil

__all__ = ('OpenRasterFileWriter', 'OpenRasterFileReader')

def ienumerate(iterable):
    return itertools.izip(itertools.count(), iterable)

class OpenRasterFileWriter:
    def __init__(self, document, filename, **kwds):
        self.filename = filename
        self.z = zipfile.ZipFile(filename, 'w', compression=zipfile.ZIP_STORED)
        self.z.writestr('mimetype', 'image/openraster')
        self.layers = []
        self.comp = kwds.get('compression', 4)
        self.extra = kwds.get('extra', {})
        self.ox, self.oy, self.width, self.height = document.get_bbox()
        self.width -= self.ox - 1
        self.height -= self.oy - 1
        self.layer_cnt = 1

    def AddLayer(self, layer):
        if not layer.empty:
            lx, ly, w, h = layer.get_bbox()
            w -= lx - 1
            h -= ly - 1
            srcpath = 'data/layer_%u.png' % self.layer_cnt
        else:
            lx = self.ox
            ly = self.oy
            w=0
            h=0
            srcpath = ''

        self.layer_cnt += 1
        xml_layer = ET.Element('layer', {}, name=layer.name, src=srcpath,
                                x=str(lx-self.ox), y=str(ly-self.oy), # save position in image coordinates
                                w=str(w), h=str(h),
                                compositeOp=layer.operator)
        self.layers.append(xml_layer)

        if srcpath:
            self.z.writestr(srcpath, layer.surface.as_png_buffer(self.comp))

    def close(self):
        if not self.layers:
            self.z.close()
            os.remove(self.filename)
            return

        image = ET.Element('image')
        self.top_stack = ET.SubElement(image, 'stack')

        a = image.attrib
        a.update((k, str(v)) for k,v in self.extra.iteritems())
        a['name'] = os.path.basename(self.filename) # ORA optional
        a['w'] = str(self.width) # ORA mandatory
        a['h'] = str(self.height) # ORA mandatory
        a['x'] = str(self.ox) # extra for Gribouillis
        a['y'] = str(self.oy) # extra for Gribouillis

        for layer in self.layers:
            self.top_stack.append(layer)

        xml = ET.tostring(image, encoding='UTF-8')
        self.z.writestr('stack.xml', xml)
        self.z.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class OpenRasterFileReader:
    def __init__(self, filename, **kwds):
        self.filename = filename
        self.z = zipfile.ZipFile(filename, 'r')
        s = self.z.read('mimetype').strip()
        xml = self.z.read('stack.xml')
        self.image = ET.fromstring(xml)
        a = self.image.attrib
        
        # Document position and size
        self.ox = int(a.get('x', 0)) # optional
        self.oy = int(a.get('y', 0)) # optional
        self.width = a.get('w', 0) # mandatory
        self.height = a.get('h', 0) # mandatory
        self.top_stack = self.image.find('stack')

    def GetImageAttributes(self):
        return self.image.attrib

    def GetLayersContents(self):
        for layer in self.top_stack:
            if layer.tag != 'layer':
                print "[*DBG*] Warning: ignoring item %s in stack" % layer.tag
                continue

            a = layer.attrib
            srcpath = a.get('src')
            if srcpath:
                if not srcpath.lower().endswith('.png'):
                    print "[*DBG*] Warning: ignoring layer src %s" % srcpath
                    continue

                x = int(a.get('x', 0)) + self.ox # optional
                y = int(a.get('y', 0)) + self.oy # optional

                ### return string of PNG data
                file = StringIO(self.z.read(srcpath))
                im = pil.open(file)
                w, h = im.size
                if w != int(a.get('w', w)) or h != int(a.get('h', h)):
                    print "[*DBG*] Warning: ignoring unwanted size (%lux%lu)" % (w, h)
                    continue
                yield a['name'], a.get('compositeOp', 'normal'), (x, y, w, h), im.tostring()
            else:
                yield a['name'], a.get('compositeOp', 'normal'), (0, 0, 0, 0), None

    def close(self):
        self.z.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

