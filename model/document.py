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
import sys
import cairo
import PIL.Image
import array

from cStringIO import StringIO
from math import floor, ceil

try:
    import png
except:
    pass

import _pixbuf

try:
    import _savers
except:
    pass

from .colorspace import ColorSpace
from .layer import TiledLayer
from .brush import DrawableBrush
from .openraster import OpenRasterFileWriter, OpenRasterFileReader

from utils import _T, join_area

__all__ = [ 'Document' ]

if os.name == 'morphos':
    LASTS_FILENAME = 'ENVARC:Gribouillis/lasts'
elif os.name == 'posix':
    LASTS_FILENAME = os.path.expanduser('~/.gribouillis/lasts')
else:
    raise SystemError(_T("LASTS_FILENAME not defined on your platform"))

# DEPRECATED
class _IntegerBuffer(object):
    def __init__(self, buf):
        self.b = buffer(buf)

    def __getslice__(self, start, stop):
        return tuple(ord(c) for c in self.b[start:stop])

class Document(list):
    """User drawing document.

    Document groups layers and handle their order.
    A document can be loaded, saved and has a name depending on load/save file.
    Document known colorspace used for all its layers.
    By default a document has one background layer fully transparent.
    But fill argument can be used to fill this layer with a default pattern.
    """

    BACKGROUND_PATH = 'backgrounds'

    __fill = None
    __active = None
    _dirty = False
    filename = None

    #### Private API ####

    def __init__(self, name, colorspace='RGB', fill='white'):
        self.name = name
        self._colorspace = (colorspace if isinstance(colorspace, ColorSpace) else ColorSpace.from_name(colorspace))
        self._layer_fmt = _pixbuf.format_from_colorspace(self._colorspace.type, _pixbuf.FLAG_15X | _pixbuf.FLAG_ALPHA_FIRST)
        self.fill = fill

        # Create the drawing brush with default properties
        self.brush = DrawableBrush()

        # Default state
        self.clear()

    #### Public API ####

    @classmethod
    def isBackgroundFile(cls, name):
        return (not os.path.isabs(name) and
                os.path.isfile(os.path.join(cls.BACKGROUND_PATH, name))) or \
                os.path.isfile(name)

    @staticmethod
    def load_image(filename, mode='RGBA'):
        """load_image(filename) -> 4-tuple
        
        Load given image by filename using PIL.Image.open method.
        Convert it to given mode colorspace (default to RGBA).
        
        Returns 4-tuple: (image data as an array, width, height, row stride)
        """
        im = PIL.Image.open(filename)
        if im.format != mode:
            im = im.convert(mode)

        a = array.array('B', im.tostring())
        w, h = im.size
        stride = w * len(mode)
        del im

        return a,w,h,stride

    def add_to_lasts(self, path):
        try:
            os.mkdir(os.path.dirname(LASTS_FILENAME))
        except:
            pass
            
        try:
            data = [ path + '\n' ]
            with open(LASTS_FILENAME) as fd:
                for i in xrange(5):
                    line = fd.readline()
                    if line[:-1].strip() != path:
                        data.append(line)
        except:
            pass

        with open(LASTS_FILENAME, 'w') as fd:
            fd.writelines(data[:5])

    ### Document methods ###

    @classmethod
    def new_from(cls, filename):
        doc = cls(name=filename)
        doc.load(filename)
        return doc

    def load(self, filename):
        filename = os.path.abspath(filename)
        ext = os.path.splitext(filename)[1][1:].lower()
        if ext:
            loader = getattr(self, 'load_from_' + ext, self.load_from_unknown)
        else:
            loader = self.load_from_unknown

        ## Save temporary current document layers list
        layers = list(self)
        active = self.active
        name = self.name
        metadata = self.metadata.copy()
        try:
            self._clear()
            loader(filename)
            self.name = filename
            self.filename = filename
            self.active = self[0]
            self.add_to_lasts(filename)
            self._dirty = False
        except:
            ## restore old document layers
            self[:] = layers
            self.active = active
            self.name = name
            self.metadata = metadata
            raise

    def load_from_unknown(self, filename):
        layer = self.new_layer(os.path.basename(filename))
        data = self.load_image(filename)
        if data:
            data, w, h, stride = data
            layer.surface.from_buffer(_pixbuf.FORMAT_RGBA8_NOA, data, stride, 0, 0, w, h)

    def load_from_ora(self, filename):
        with OpenRasterFileReader(filename) as ora:
            for name, operator, area, visible, opa, data in ora.GetLayersContents():
                layer = self._create_layer(name, operator=operator, opacity=opa)
                layer.visible = visible
                if data:
                    layer.surface.from_buffer(_pixbuf.FORMAT_RGBA8_NOA, data, area[2]*4, *area)
                self.insert(0, layer)

    def save_as(self, filename=None):
        # First be sure to have a clean document
        for layer in self.layers:
            layer.surface.cleanup()
            
        filename = os.path.abspath(filename or self.name)
        ext = os.path.splitext(filename)[1].lower()
        if ext:
            saver = getattr(self, 'save_as_' + ext[1:], None)
            if saver:
                saver(filename)
                self.add_to_lasts(filename)
                self.filename = filename
                self._dirty = False
                return
            raise TypeError("Unknown extension")
        raise TypeError("No extension given")

    def save_as_ora(self, filename):
        with OpenRasterFileWriter(self, filename) as ora:
            layers = list(self)
            layers.reverse() # ORA uses FG-to-BG layers order convention
            for layer in layers:
                ora.AddLayer(layer, self.as_png_buffer)

    def save_as_png(self, filename):
        surface = self.as_cairo_surface()
        if surface:
            surface.write_to_png(filename)

    def _clear(self):
        del self[:]
        self.metadata = {
            'dimensions': None,
            'densities': [300, 300],
            }
        
    def clear(self):
        self._clear()

        # Empty document = one background layer
        self.new_layer(name='background')
        self._dirty = False
    
    def get_fill(self):
        return self.__fill
        
    def set_fill(self, fill):
        if isinstance(fill, basestring):
            if self.isBackgroundFile(fill):
                surface = cairo.ImageSurface.create_from_png(fill)
                self.__fill = cairo.SurfacePattern(surface)
                self.__fill.set_extend(cairo.EXTEND_REPEAT)
                self.__fill.set_filter(cairo.FILTER_FAST)
            else: 
                self.__fill = self._colorspace.get_color(fill)
        else:
            self.__fill = fill
        self._dirty = True
       
    def get_pixel(self, *pt):
        brush = self.brush
        # search for a valid color from top to bottom layer
        for layer in reversed(self):
            color = layer.get_pixel(brush, *pt)
            if color is not None:
                return color
        return (0.0,)*3
        
    ### Document's layer methods ###
    # Layers are ordered using a list using BG-to-FG convention
    # Last item is the foreground layer
    # First item is the background layer
    # This converntion is easier for rastering

    def _create_layer(self, name, **options):
        return TiledLayer(self._layer_fmt, name, **options)

    def new_layer(self, name, pos=None, **options):
        layer = self._create_layer(name, **options)
        self.insert_layer(layer, pos)
        self.active = layer
        return layer

    def insert_layer(self, layer, pos=None, activate=False):
        if pos is None:
            if self:
                pos = len(self)
            else:
                pos = 0
        assert pos >= 0
        if layer in self:
            raise KeyError("Already inserted layer '%s'" % layer.name)
        self.insert(pos, layer)
        if activate:
            self.active = layer
        self._dirty = True

    def remove_layer(self, layer):
        i = self.index(layer)
        self.remove(layer)
        self._dirty = True
        
        if self.active is layer:
            # Activate the layer just before this one
            self.active = self[min(i, len(self)-1)]

    def move_layer(self, layer, pos):
        self.remove(layer)
        self.insert(pos, layer)

    def get_layer_index(self, layer=None):
        return self.index(layer or self.active)

    def clear_layer(self, layer=None):
        (layer or self.active).clear()

    def get_bbox(self, layers=None, all=False):
        empty = True
        for layer in (layers or self):
            if not layer.visible and not all:
                continue
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

    def get_active(self):
        return self.__active

    def set_active(self, layer):
        self.__active = layer
        self.brush.surface = layer.surface

    ### Rendering API ###

    def rasterize(self, cr, dst, filter=cairo.FILTER_BEST, layers=None, all=False, back=True):
        """Rasterize document on given cairo context.
        
        The context must have its matrix and clip set before calling this function.
        Note: the clip must be set before setting the viewing matrix.
        """

        # Paint visible layers on the transparent raster
        if layers:
            if all:
                for layer in layers:
                    self.rasterize_layer(layer, cr, dst, filter)
            else:
                for layer in layers:
                    if layer.visible:
                        self.rasterize_layer(layer, cr, dst, filter)
        else:
            if all:
                for layer in self:
                    self.rasterize_layer(layer, cr, dst, filter, layer.OPERATORS[layer.operator])
            else:
                for layer in self:
                    if layer.visible:
                        self.rasterize_layer(layer, cr, dst, filter, layer.OPERATORS[layer.operator])

        # Finish by rendering the background
        if back and self.__fill:
            cr.identity_matrix()
            cr.set_operator(cairo.OPERATOR_DEST_OVER)
            if isinstance(self.__fill, cairo.Pattern):
                cr.set_source(self.__fill)
            else:
                cr.set_source_rgb(*self.__fill)
            cr.paint()

    def rasterize_layer(self, layer, cr, dst, filter, ope=cairo.OPERATOR_OVER,
            fmt=_pixbuf.FORMAT_ARGB8, new_surface = cairo.ImageSurface.create_for_data):
        # FORMAT_ARGB8 => cairo uses alpha-premul pixels buffers
        
        clip = layer.area
        if clip is None:
            return
        
        cr.save()
        
        # XXX: pycairo < 1.8.8 has inverted matrix multiply operation
        # when done using '*' operator.
        # So I use the multiply method here.
        cr.transform(layer.matrix)
        
        # Reduce again the clipping area to the layer area
        cr.rectangle(*clip)
        cr.clip()
        
        x,y,w,h = cr.clip_extents()
        #if x == w or y == h:
        #    return
        
        # Convert to integer and add an extra border pixel
        # due to the cairo filtering.
        x = int(floor(x)-1)
        y = int(floor(y)-1)
        w = int(ceil(w)+1) - x + 1
        h = int(ceil(h)+1) - y + 1
        model_area = x,y,w,h
        
        # render temporary buffer (sized by the model redraw area)
        pb = _pixbuf.Pixbuf(fmt, w, h)
        pb.clear()
        
        # Blit layer's tiles using over ope mode on the render surface
        def blit(tile):
            tile.blit(pb, tile.x - x, tile.y - y)
                      
        layer.surface.rasterize(model_area, blit)
        
        rsurf = new_surface(pb, cairo.FORMAT_ARGB32, w, h)
        
        # Now paint the render surface on the model surface
        cr.set_source_surface(rsurf, x, y)
        cr.get_source().set_filter(filter)
        cr.set_operator(ope)
        cr.paint_with_alpha(layer.opacity)
        
        cr.restore()

    def as_cairo_surface(self, layers=None, all=False, **kwds):
        rect = self.get_bbox(layers, all)
        if not rect: return
        
        dx, dy, dw, dh = rect
        dw -= dx - 1
        dh -= dy - 1

        # Destination surface/context
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, dw, dh)
        cr = cairo.Context(surface)
        cr.translate(-dx, -dy)
        self.rasterize(cr, filter=cairo.FILTER_FAST, layers=layers, all=all, **kwds)
        
        return surface

    def as_png_buffer(self, comp=4, layers=None, all=False, **kwds):
        rect = self.get_bbox(layers, all)
        if not rect: return
        
        x,y,w,h = rect
        w -= x - 1
        h -= y - 1
        
        # PNG buffer is need RGBA8 format (no alpha-premul)
        pixelbuf = _pixbuf.Pixbuf(_pixbuf.FORMAT_RGBA8_NOA, w, h)
        
        # Rendering
        surface = self.as_cairo_surface(layers, all, **kwds)
        pixelbuf.from_buffer(_pixbuf.FORMAT_ARGB8,
                             surface.get_data(),
                             surface.get_stride(),
                             0, 0,
                             surface.get_width(), surface.get_height())

        # Encode pixels data to PNG
        
        # DEPRECATED
        #pngbuf = StringIO()
        #writer = png.Writer(w, h, alpha=True, bitdepth=8, compression=comp)
        #writer.write_array(pngbuf, _IntegerBuffer(pixelbuf))
        #return pngbuf.getvalue()
        
        return _savers.save_pixbuf_as_png_buffer(pixelbuf);

    ### Properties ###

    @property
    def close_safe(self):
        return self.empty or not self.modified

    @property
    def empty(self):
        return not bool(self) or all(layer.empty for layer in self)

    @property
    def layers(self):
        return self

    @property
    def area(self):
        bbox = self.get_bbox()
        if not bbox: return 0,0,0,0
        return bbox[0], bbox[1], bbox[2]-bbox[0]+1, bbox[3]-bbox[1]+1

    @property
    def modified(self):
        return self._dirty or any(layer.modified for layer in self)

    active = property(fget=get_active, fset=set_active)
    fill = property(fget=get_fill, fset=set_fill)
