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

# Python 2.5 compatibility
from __future__ import with_statement

import os
import array

from utils import virtualmethod

debug = 0

def _DBG(msg):
    print msg

DBG = (_DBG if debug else lambda x: None)
del debug, _DBG

SUPPORTED_EXTENSIONS = []

class Palette(list):
    MAX_COLORS = 256

    def __init__(self, name, filename=None):
        list.__init__(self)
        for i in xrange(self.MAX_COLORS):
            self.append(PaletteValue())

        self.name = name

        if filename:
            self.loadfromfile(filename)

    def loadfromfile(self, filename):
        for handler in _MetaPaletteHandler.HANDLERS:
            if handler.ishandled(filename):
                DBG("File '%s' accepted as '%s' palette, loading..." % (filename, handler.NAME ))
                try:
                    handler.load(filename, self)
                    return
                except:
                    pass
        raise NotImplementedError("Unable to recognize as palette the file '%s'" % filename)

    def savetofile(self, filename):
        for handler in _MetaPaletteHandler.HANDLERS:
            if handler.ishandled(filename):
                DBG("File '%s' accepted as '%s' palette, saving..." % (filename, handler.NAME ))
                try:
                    handler.save(filename, self)
                    return
                except:
                    pass
        raise NotImplementedError("Unable to recognize as palette the file '%s'" % filename)

class PaletteValue(object):
    __slots__ = ('value', 'colorspace', 'rgb')

    def __init__(self):
        self.value = None
        self.colorspace = None

    def __del_value(self):
        self.value = None
        self.colorspace = None

    def __set_rgb(self, rgb):
        self.colorspace = 'RGB'
        self.value = tuple(rgb)

    def __get_rgb(self):
        if self.colorspace is None:
            return

        if self.colorspace == 'RGB':
            return self.value

        raise NotImplementedError("Convertion from %s to RGB not supported" % self.colorspace)

    rgb = property(fget=__get_rgb, fset=__set_rgb, fdel=__del_value)

class _MetaPaletteHandler(type):
    HANDLERS = set()

    def __init__(cl, name, bases, dct):
        type.__init__(cl, name, bases, dct)
        if name != 'PaletteHandler':
            _MetaPaletteHandler.HANDLERS.add(cl)
            SUPPORTED_EXTENSIONS.append(cl.EXT)

class PaletteHandler(object):
    __metaclass__ = _MetaPaletteHandler

    @classmethod
    def getext(cl, filename):
        return os.path.splitext(filename)[1].lower()

    @classmethod
    @virtualmethod
    def load(cl, filename, palette): pass

    @classmethod
    @virtualmethod
    def save(cl, filename, palette): pass

    @classmethod
    def ishandled(cl, filename):
        return cl.getext(filename) == cl.EXT

class PaintShopProHandler(PaletteHandler):
    NAME = "PaintShopPro"
    EXT = '.pal'

    @classmethod
    def load(cl, filename, palette):
        with open(filename, 'Ur') as fd:
            # Check validity
            assert fd.readline() == "JASC-PAL\n", "Invalid %s palette file" % cl.NAME
            ver = fd.readline()
            assert ver == "0100\n", "Invalid %s palette file version: '%s'" % (c.NAME, ver[:-1])

            # Clamp number of available colors
            count = max(0, min(int(fd.readline()), Palette.MAX_COLORS))

            # Read RGB values
            for i in xrange(count):
                line = fd.readline()[:-1]
                rgb = map(lambda x: int(x)/255., line.split())
                assert len(rgb) == 3, "Invalid RGB value: '%s'" % line
                palette[i].rgb = rgb

    @classmethod
    def save(cl, filename, palette):
        with open(filename, 'w') as fd:
            fd.write('JASC-PAL\r\n')
            fd.write('0100\r\n')

            values = [ pv.rgb for pv in palette if pv.value != None ]
            fd.write('%u\r\n' % len(values))

            for rgb in values:
                fd.write("%u %u %u\r\n" % tuple(int(x*255) for x in rgb))

class AdobeColorSwatchHandler(PaletteHandler):
    NAME = "Adobe Photoshop Color"
    EXT = '.aco'

    @classmethod
    def load(cl, filename, palette):
        a = array.array('H')
        with open(filename, 'r') as fd:
            # Check version
            a.fromstring(fd.read())
            ver = a[0]
            assert ver in (1, 2), "Invalid %s palette file version: '%s'" % (cl.NAME, ver)

            # Clamp number of available colors
            count = max(0, min(a[1], Palette.MAX_COLORS))

            # Laod value
            for i in xrange(count):
                off = 2+i*5
                cs, w, x, y, _ = a[off:off+5]
                if cs == 0:
                    # RGB
                    palette[i].rgb = (w/65280., x/65280., y/65280.)

                if ver == 2:
                    # Read name
                    len = data[off+6] - 1
                    #name = unicode(data[off+7:off+len+7].tostring(), 'utf-16')
                    i += off+len+8

    @classmethod
    def save(cl, filename, palette):
        a = array.array('H')
        a.append(1)
        values = [ pv.rgb for pv in palette if pv.value != None ]
        a.append(len(values))
        for r, g, b in values:
            a.append(0)
            a.append(int(r*65280))
            a.append(int(g*65280))
            a.append(int(b*65280))
            a.append(0)

        with open(filename, 'w') as fd:
            a.tofile(fd)

DefaultPalette = Palette('default')
DefaultPalette[0].rgb = (0,0,0)
DefaultPalette[1].rgb = (1,1,1)
DefaultPalette[2].rgb = (1,0,0)
DefaultPalette[3].rgb = (0,1,0)
DefaultPalette[4].rgb = (0,0,1)
