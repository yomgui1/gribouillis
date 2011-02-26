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

import _pixbuf, os, time, sys, cairo
import PIL.Image, array
from math import ceil

from .colorspace import ColorSpace
from .layer import TiledLayer
from .brush import DrawableBrush
from .openraster import OpenRasterFileWriter, OpenRasterFileReader

__all__ = [ 'Document' ]

class Document(object):
    """User drawing document.

    Document groups layers and handle their order.
    A document can be loaded, saved and has a name depending on load/save file.
    Document known colorspace used for all its layers.
    By default a document has one background layer fully transparent.
    But fill argument can be used to fill this layer with a default pattern.
    """

    BACKGROUND_PATH = 'backgrounds'

    _debug = 0

    #### Private API ####

    def __init__(self, name, colorspace='RGB', fill='black'):
        self.name = name
        self._colorspace = (colorspace if isinstance(colorspace, ColorSpace) else ColorSpace.from_name(colorspace))
        self._layer_fmt = _pixbuf.format_from_colorspace(self._colorspace.type,
                                                         _pixbuf.FLAG_15X | _pixbuf.FLAG_ALPHA_FIRST)
        self._fill = (self._colorspace.get_color(fill) if isinstance(fill, basestring) else fill)
        self.__active = None # active layer

        # Create the drawing brush with default properties
        self.brush = DrawableBrush()

        # set default values
        self.clear()

    def __len__(self):
        "Return the number of document's layers"
        return len(self._layers)

    #### Public API ####

    @classmethod
    def isBackgroundFile(cls, name):
        return (not os.path.isabs(name) and
                os.path.isfile(os.path.join(cls.BACKGROUND_PATH, name))) or \
                os.path.isfile(name)

    @staticmethod
    def _load_image(filename):
        print '*DBG* loading %s' % filename
        im = PIL.Image.open(filename)
        if im.format != 'RGBA':
            im = im.convert('RGBA')

        a = array.array('B', im.tostring())
        w, h = im.size
        stride = w * 4
        del im

        return a,w,h,stride

    ### Document methods ###

    @classmethod
    def new_from(cls, filename):
        doc = cls(name=filename)
        doc.load_from(filename)
        return doc

    def load_from(self, filename):
        ext = os.path.splitext(filename)[1][1:].lower()
        if ext:
            loader = getattr(self, 'load_from_' + ext, self.load_from_unknown)
        else:
            loader = self.load_from_unknown

        ## Save temporary current document state
        layers = self._layers
        try:
            self._clear()
            loader(filename)
            self.name = filename
            self.active = self._layers[-1]
        except:
            ## restore old document state
            self._layers = layers
            raise

    def load_from_unknown(self, filename):
        layer = self.new_layer(os.path.basename(filename))
        data = self._load_image(filename)
        if data:
            data, w, h, stride = data
            layer.surface.from_buffer(_pixbuf.FORMAT_RGBA8_NOA, data, stride, 0, 0, w, h)

    def load_from_ora(self, filename):
        with OpenRasterFileReader(filename) as ora:
            for name, operator, area, data in ora.GetLayersContents():
                layer = self._new_layer(name, operator=operator)
                if data:
                    layer.surface.from_buffer(_pixbuf.FORMAT_RGBA8_NOA, data, area[2]*4, *area)
                self._layers.insert(0, layer)

    def save_as(self, filename=None):
        # First be sure to have a clean document
        for layer in self.layers:
            layer.surface.cleanup()
            
        filename = filename or self.name
        ext = os.path.splitext(filename)[1].lower()
        if ext:
            saver = getattr(self, 'save_as_' + ext[1:], None)
            if saver:
                saver(filename)
                return
            raise TypeError("Unknown extension")
        raise TypeError("No extension given")

    def save_as_ora(self, filename):
        with OpenRasterFileWriter(self, filename) as ora:
            layers = self.layers
            layers.reverse() # ORA first layer is the top layer in stack
            map(ora.AddLayer, layers)

    def save_as_png(self, filename):
        surface = self.as_cairo_surface()
        if surface:
            surface.write_to_png(filename)

    def _clear(self):
        self._layers = []

    def clear(self):
        self._clear()

        # Empty document = one background layer
        self.new_layer(name='background', fill=self._fill)

    @staticmethod
    def _add_area(area1, area2):
        return min(area1[0], area2[0]), min(area1[1], area2[1]), \
               max(area1[2], area2[2]), max(area1[3], area2[3])

    def _flush_motions(self):
        area = None
        a = sys.maxint, sys.maxint, -sys.maxint, -sys.maxint
        for stroke in self._motions:
            if not self._debug:
                area = self.brush.draw_stroke(stroke)
            else:
                area = self.brush.drawdab_solid((stroke.sx, stroke.sy), stroke.pressure, 2.0, 1.0)
            if area: a = self._add_area(a, area)
        self._motions = []
        self._stime = time.time()
        if area: return (a[0],a[1],a[2]-a[0]+1,a[3]-a[1]+1), self._snapshot
        return None, self._snapshot

    ### Document's layer methods ###

    def _new_layer(self, name, pos=None, **options):
        return TiledLayer(self._layer_fmt, name, **options)

    def new_layer(self, name, pos=None, **options):
        layer = self._new_layer(name, pos, **options)
        self.insert_layer(layer, pos)
        self.active = layer
        return layer

    def insert_layer(self, layer, pos=None, activate=False):
        if layer in self._layers:
            raise KeyError("Already inserted layer '%s'" % layer.name)
        if pos is None:
            self._layers.append(layer)
        else:
            self._layers.insert(pos, layer)
        if activate:
            self.active = layer

    def remove_layer(self, layer):
        i=self._layers.index(layer)
        self._layers.remove(layer)
        if self.active is layer:
            self.active = self._layers[max(0, i-1)]

    def move_layer(self, layer, pos):
        self._layers.remove(layer)
        self._layers.insert(pos, layer)

    def get_layer_index(self, layer=None):
        layer = layer or self.active
        if layer:
            return self._layers.index(layer)

    def clear_layer(self, layer=None):
        layer = layer or self.active
        layer.clear()

    def get_bbox(self):
        empty = True
        for layer in self._layers:
            if not layer.visible: continue
            a = layer.get_bbox()
            if a:
                if empty:
                    empty = False
                    xmin,ymin,xmax,ymax = a
                else:
                    x1,y1,x2,y2 = a
                    if xmin > x1: xmin = x1
                    if ymin > y1: ymin = y1
                    if xmax < x2: xmax = x2
                    if ymax < y2: ymax = y2
        if empty: return
        return xmin,ymin,xmax,ymax

    def get_size(self):
        area = self.get_bbox()
        if not area: return 0,0
        return area[1]-area[0]+1, area[3]-area[2]+1

    def as_cairo_surface(self):
        area = self.get_bbox()
        if not area: return
        dx, dy, dw, dh = area
        dw -= dx-1
        dh -= dy-1

        # Destination surface/context
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, dw, dh)
        cr = cairo.Context(surface)
        
        for layer in self._layers:  
            if not layer.visible: continue
            
            area = layer.get_bbox()
            if not area: continue
            
            x,y,w,h = area
            w -= x-1
            h -= y-1
            
            rsurf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
            
            # Remove layer offset (layer.get_bbox() has added it)
            ox = x + int(layer.x)
            oy = y + int(layer.y)
            
            def cb(tile):
                tile.blit(_pixbuf.FORMAT_ARGB8,
                          rsurf.get_data(),
                          rsurf.get_stride(),
                          w, h, tile.x-ox, tile.y-oy)
            layer.surface.rasterize((x,y,w,h), cb)
            rsurf.mark_dirty()

            cr.set_source_surface(rsurf, x-dx, y-dy)
            cr.set_operator(layer.OPERATORS[layer.operator])
            cr.paint_with_alpha(layer.opacity)

        return surface

    ### Properties ###

    @property
    def empty(self):
        return not bool(self._layers) or all(layer.empty for layer in self._layers)

    @property
    def layers(self):
        "Return a copy of document's layers list"
        return list(self._layers)

    def get_active(self):
        return self.__active

    def set_active(self, layer):
        self.__active = layer
        self.brush.surface = layer.surface

    active = property(fget=get_active, fset=set_active)
