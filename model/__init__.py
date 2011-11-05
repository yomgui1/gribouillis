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

import cairo
import puremvc.patterns.proxy
from math import log, exp

import main, utils, model
from utils import UndoableCommand

from .document import Document
from .layer import Layer
from .palette import Palette
from vo import *

__all__ = [ 'DocumentProxy' ]

class DocumentProxy(puremvc.patterns.proxy.Proxy):
    """
    A DocumentProxy instance is responsible to:
      - handle one document at time.
      - check that doesn't exist two document with same name.
      - give access to Document's methods.

    Instances are created by the view when needed.
    Instances are not re-usable (setData raise exception)
    """

    #### Private API ####

    __instances = {}
    __active = None # Current working docproxy
    __brush = None # Brush instance owned by the Brush House.
    profile = None # Color profile

    def __init__(self, doc):
        assert isinstance(doc, Document)
        super(DocumentProxy, self).__init__(str(id(self)), None)
        self.__doc = doc

        self.facade.registerProxy(self)
        self._attach_cmd_hist()

    def _attach_cmd_hist(self):
        hp_name = 'HP_' + self.getProxyName()
        assert not self.facade.hasProxy(hp_name)
        hp = utils.CommandsHistoryProxy(name=hp_name, data=self)
        self.facade.registerProxy(hp)

    #### MVC API ####

    def onRegister(self):
        # Check if the document's name is unique
        docname = self.__doc.name
        if docname in DocumentProxy.__instances:
            raise NameError('document name already exists')
        DocumentProxy.__instances[docname] = self

    def onRemove(self):
        del DocumentProxy.__instances[self.document.name]
        self.__doc = None # invalide the proxy doc, in case of ref kept somewhere
        if DocumentProxy.__active is self:
            DocumentProxy.__active = None

    #### Public API ####
    
    @classmethod
    def from_doc_name(cls, name):
        return cls.__instances.get(name)

    @classmethod
    def iternames(cls):
        return cls.__instances.iterkeys()

    @classmethod
    def new_proxy(cls, vo):
        """
        Helper classmethod to create DocumentProxy with document
        depending on DocumentConfigVO given.
        """

        if isinstance(vo, FileDocumentConfigVO):
            doc = Document.new_from(vo.name)
        elif isinstance(vo, EmptyDocumentConfigVO):
            doc = Document(name=vo.name, colorspace=vo.colorspace)
        else:
            raise TypeError("Bad vo argument type %s" % type(vo))

        if doc:
            self = cls(doc)

            # Docproxy ready to be used
            self.sendNotification(main.Gribouillis.NEW_DOCUMENT_RESULT, self)
            return self

    @staticmethod
    def get_active():
        return DocumentProxy.__active

    @staticmethod
    def set_active(proxy):
        assert isinstance(proxy, DocumentProxy)
        assert proxy.docname in DocumentProxy.__instances
        DocumentProxy.__active = proxy

    def activate(self):
        self.active = self

    def load(self, filename):
        doc = self.__doc
        del DocumentProxy.__instances[doc.name]
        try:
            doc.load(filename)
        finally:
            DocumentProxy.__instances[doc.name] = self

    #### Document access API ####

    def get_name(self):
        return self.__doc.name
        
    def set_name(self, name):
        doc = self.__doc
        if name == doc.name:
            return

        if name in DocumentProxy.__instances:
            assert NameError('document name already exists')

        del DocumentProxy.__instances[doc.name]
        DocumentProxy.__instances[name] = self
        doc.name = name
        self.sendNotification(main.Gribouillis.DOC_UPDATED, self)

    def set_background(self, value):
        self.__doc.fill = value
        self.sendNotification(main.Gribouillis.DOC_DIRTY, self)
        
    def set_metadata(self, **kwds):
        change = False
        for k in kwds:
            if k in self.__doc.metadata:
                self.__doc.metadata[k] = kwds[k]
                change = True
        if change:
            self.sendNotification(main.Gribouillis.DOC_UPDATED, self)
    
    #### Brush handling ####

    def set_brush(self, brush):
        self.__brush = brush
        self.document.brush.set_from_brush(brush)
        self.sendNotification(main.Gribouillis.DOC_BRUSH_UPDATED, self)
        
    def get_brush_color_rgb(self):
        return self.__doc.brush.rgb

    def get_brush_color_hsv(self):
        return self.__doc.brush.hsv
            
    def set_brush_color_hsv(self, *hsv):
        brush = self.__doc.brush
        if brush.hsv != hsv:
            brush.hsv = hsv
            self.sendNotification(main.Gribouillis.BRUSH_PROP_CHANGED, (brush, 'color'))

    def set_brush_color_rgb(self, *rgb):
        brush = self.__doc.brush
        if brush.rgb != rgb:
            brush.rgb = rgb
            self.sendNotification(main.Gribouillis.BRUSH_PROP_CHANGED, (brush, 'color'))

    def set_brush_radius(self, r):
        brush = self.__brush
        r = min(max(r, 0.5), 150)
        if brush.radius_max != r:
            brush.radius_max = r
            self.sendNotification(main.Gribouillis.BRUSH_PROP_CHANGED, (brush, 'radius_max'))
        if brush.radius_min != r:
            brush.radius_min = r
            self.sendNotification(main.Gribouillis.BRUSH_PROP_CHANGED, (brush, 'radius_min'))
            
    def add_brush_radius(self, dr):
        brush = self.__brush
        r = min(max(0.5, max(brush.radius_min, brush.radius_max)+dr), 150)
        if brush.radius_max != r:
            brush.radius_max = r
            self.sendNotification(main.Gribouillis.BRUSH_PROP_CHANGED, (brush, 'radius_max'))
        if brush.radius_min != r:
            brush.radius_min = r
            self.sendNotification(main.Gribouillis.BRUSH_PROP_CHANGED, (brush, 'radius_min'))
            
    def set_brush_radius_max(self, r):
        brush = self.__brush
        r = min(max(r, 0.5), 150)
        if brush.radius_max != r:
            brush.radius_max = r
            self.sendNotification(main.Gribouillis.BRUSH_PROP_CHANGED, (brush, 'radius_max'))
            
    def add_brush_radius_max(self, dr):
        brush = self.__brush
        r = min(max(0.5, brush.radius_max+dr), 150)
        if brush.radius_max != r:
            brush.radius_max = r
            self.sendNotification(main.Gribouillis.BRUSH_PROP_CHANGED, (brush, 'radius_max'))

    def set_brush_radius_min(self, r):
        brush = self.__brush
        r = min(max(r, 0.5), 150)
        if brush.radius_min != r:
            brush.radius_min = r
            self.sendNotification(main.Gribouillis.BRUSH_PROP_CHANGED, (brush, 'radius_min'))
            
    def add_brush_radius_min(self, dr):
        brush = self.__brush
        r = min(max(0.5, brush.radius_min+dr), 150)
        if brush.radius_min != r:
            brush.radius_min = r
            self.sendNotification(main.Gribouillis.BRUSH_PROP_CHANGED, (brush, 'radius_min'))

    def add_color(self, *factors):
        hsv = [ c+f for c, f in zip(self.get_brush_color_hsv(), factors) ]
        self.set_brush_color_hsv(*hsv)
        
    def multiply_color(self, *factors):
        hsv = [ c*f for c, f in zip(self.get_brush_color_hsv(), factors) ]
        self.set_brush_color_hsv(*hsv)
        
    #### Painting ####
    
    def draw_start(self, device):
        doc = self.__doc
        surface = doc.active.surface
        if surface.lock:
            # Do not record if surface is locked
            self.record = utils.idle
        else:
            self.record = self._record
        self._dev = device
        self._layer = doc.active
        self._snapshot = doc.active.snapshot() # for undo
        state = device.current
        self._stroke = [ state ]
        doc.brush.start(surface, state)

    def draw_end(self):
        doc = self.__doc
        area = doc.brush.stop()
        if area:
            doc._dirty = True
            self.sendNotification(main.Gribouillis.DOC_DIRTY, (self, self._layer.document_area(*area)))
        ss = self._snapshot
        if ss.reduce(self._layer.surface):
            self.sendNotification(main.Gribouillis.DOC_RECORD_STROKE,
                                  LayerCommandVO(self, self._layer, snapshot=ss, stroke=self._stroke),
                                  type=utils.RECORDABLE_COMMAND)
        del self._snapshot, self._layer, self._stroke, self._dev

    def _record(self, state):
        self._stroke.append(state)
        area = self.__doc.brush.draw_stroke(state)
        if area:
            self._layer._dirty = True
            self.sendNotification(main.Gribouillis.DOC_DIRTY, (self, self._layer.document_area(*area)))

    #### Document layers handling ####

    def new_layer(self, vo):
        layer = self.__doc.new_layer(**vo)
        self.sendNotification(main.Gribouillis.DOC_LAYER_ADDED, (self, layer, self.__doc.get_layer_index(layer)))
        return layer

    def insert_layer(self, layer, pos=None, **k):
        self.__doc.insert_layer(layer, pos, **k)
        self.sendNotification(main.Gribouillis.DOC_LAYER_ADDED, (self, layer, self.__doc.get_layer_index(layer)))

    def remove_layer(self, layer):
        self.__doc.remove_layer(layer)
        self.sendNotification(main.Gribouillis.DOC_LAYER_DELETED, (self, layer))
        self.sendNotification(main.Gribouillis.DOC_LAYER_ACTIVATED, (self, self.active_layer))

    def clear_layer(self, layer):
        self.sendNotification(main.Gribouillis.DOC_LAYER_CLEAR,
                              LayerCommandVO(self, layer),
                              type=utils.RECORDABLE_COMMAND)
                              
    def copy_layer(self, layer, pos=None):
        if pos is None:
            pos = self.__doc.get_layer_index(layer) + 1
        new_layer = self.__doc.new_layer('Copy of %s' % layer.name, pos)
        new_layer.copy(layer)
        self.sendNotification(main.Gribouillis.DOC_LAYER_ADDED, (self, new_layer, self.__doc.get_layer_index(layer)))
        return new_layer

    def move_layer(self, layer, pos=None):
        self.__doc.move_layer(layer, pos)
        self.sendNotification(main.Gribouillis.DOC_LAYER_STACK_CHANGED, (self, layer, self.__doc.get_layer_index(layer)))

    def set_layer_visibility(self, layer, state):
        state = bool(state)
        if layer.visible != state:
            vo = model.vo.LayerCommandVO(docproxy=self, layer=layer, state=state)
            self.sendNotification(main.Gribouillis.DOC_LAYER_SET_VISIBLE, vo, type=utils.RECORDABLE_COMMAND)

    def iter_visible_layers(self):
        return (layer for layer in self.layers if layer.visible)

    def set_layer_opacity(self, layer, value):
        if value != layer.opacity:
            vo = model.vo.LayerCommandVO(docproxy=self, layer=layer, state=value)
            self.sendNotification(main.Gribouillis.DOC_LAYER_SET_OPACITY, vo)

    def record_layer_matrix(self, layer, old_mat):
        if not layer.empty:
            self.sendNotification(main.Gribouillis.DOC_LAYER_MATRIX, (self, layer, old_mat, cairo.Matrix(*layer.matrix)), type=utils.RECORDABLE_COMMAND)
        
    def layer_translate(self, *delta):
        layer = self.__doc.active
        if layer.empty: return
        area = layer.area
        if not area: return
        
        layer.translate(*delta)
        
        # Refresh the old area + the new layer area
        area = utils.join_area(area, layer.area)
        self.sendNotification(main.Gribouillis.DOC_DIRTY, (self, area))

    def layer_rotate(self, angle, ox=0, oy=0):
        layer = self.__doc.active
        if layer.empty: return
        area = layer.area
        if not area: return

        matrix = layer.matrix
        matrix.translate(ox, oy)
        matrix.rotate(angle)
        matrix.translate(-ox, -oy)
        
        layer.matrix = matrix
        
        # Refresh the old area + the new layer area
        area = utils.join_area(area, layer.area)
        self.sendNotification(main.Gribouillis.DOC_DIRTY, (self, area))

    def get_layer_pos(self, *pos):
        layer = self.__doc.active
        return layer.inv_matrix.transform_point(*pos)

    def get_layer_dist(self, *dist):
        layer = self.__doc.active
        return layer.inv_matrix.transform_distance(*dist)

    #### Properties ###

    active = property(fget=lambda self: self.get_active(),
                      fset=lambda self, v: self.set_active(v))
    document = property(fget=lambda self: self.__doc)
    docname = property(fget=lambda self: self.__doc.name, fset=set_name)
    brush = property(fget=lambda self: self.__brush, fset=set_brush)
    drawbrush = property(fget=lambda self: self.__doc.brush)
    active_layer = property(fget=lambda self: self.__doc.active)

