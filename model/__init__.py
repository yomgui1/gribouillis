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

import puremvc.patterns.proxy
from math import log, exp

import main, utils, model
from utils import UndoableCommand

from .document import Document
from .layer import Layer
from vo import *

__all__ = [ 'DocumentProxy' ]

class DocumentProxy(puremvc.patterns.proxy.Proxy):
    """
    A DocumentProxy instance is responsible to:
      - handle one document at time.
      - check that doesn't exist two document with same name.

    Instances are created by the view when needed.
    Instances are not re-usable (setData raise exception)
    """

    #### Private API ####

    __instances = {}
    __active = None # current active docproxy
    _brush = None # Brush instance owned by the Brush House.

    def __init__(self, doc):
        assert isinstance(doc, Document)
        super(DocumentProxy, self).__init__(str(id(self)), None)
        self.__doc = doc

        self.facade.registerProxy(self)
        self.__attach_cmd_hist()

    def __attach_cmd_hist(self):
        hp_name = 'HP_' + self.getProxyName()
        assert not self.facade.hasProxy(hp_name)
        hp = utils.CommandsHistoryProxy(name=hp_name, data=self)
        self.facade.registerProxy(hp)

    #### Public API ####

    def onRegister(self):
        docname = self.__doc.name
        assert docname  not in DocumentProxy.__instances
        DocumentProxy.__instances[docname] = self

    def onRemove(self):
        del DocumentProxy.__instances[self.document.name]
        self.__doc = None # invalide the proxy doc, in case of ref kept somewhere
        if DocumentProxy.__active is self:
            DocumentProxy.__active = None

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

    #### Document general handling ####

    def load_from(self, filename):
        del DocumentProxy.__instances[self.__doc.name]
        doc = self.__doc
        try:
            doc.load_from(filename)
        finally:
            DocumentProxy.__instances[doc.name] = self

    def set_docname(self, name):
        if name == self.__doc.name:
            return

        if name in DocumentProxy.__instances:
            assert NameError('document name already exists')

        del DocumentProxy.__instances[self.__doc.name]
        DocumentProxy.__instances[name] = self
        self.__doc.name = name

    def read_pixel_rgb(self, pos, layer=None):
        if layer is None:
            layer = self.active_layer
        return layer.surface.read_pixel(pos)

    #### Brush handling ####

    def _set_brush(self, brush):
        #print "[DP] copy/use brush %s" % brush
        self._brush = brush
        self.document.brush.set_from_brush(brush)
        self.sendNotification(main.Gribouillis.DOC_BRUSH_UPDATED, self)

    def set_brush_color_hsv(self, *hsv):
        b = self.__doc.brush
        if b.hsv != hsv:
            b.hsv = hsv
            self.sendNotification(main.Gribouillis.BRUSH_PROP_CHANGED, (b, 'color'))

    def set_brush_color_rgb(self, *rgb):
        b = self.__doc.brush
        if b.rgb != rgb:
            b.rgb = rgb
            self.sendNotification(main.Gribouillis.BRUSH_PROP_CHANGED, (b, 'color'))

    def set_brush_radius(self, r):
        brush = self.brush
        r = max(r, 0.5)
        if brush.radius_max != r:
            brush.radius_max = r
            self.sendNotification(main.Gribouillis.BRUSH_PROP_CHANGED, (self.brush, 'radius_max'))
        if brush.radius_min != r:
            brush.radius_min = r
            self.sendNotification(main.Gribouillis.BRUSH_PROP_CHANGED, (self.brush, 'radius_min'))

    def add_brush_radius(self, dr):
        brush = self.brush
        r = min(max(0.1, max(brush.radius_min, brush.radius_max)+dr), 200)
        if brush.radius_max != r:
            brush.radius_max = r
            self.sendNotification(main.Gribouillis.BRUSH_PROP_CHANGED, (self.brush, 'radius_max'))
        if brush.radius_min != r:
            brush.radius_min = r
            self.sendNotification(main.Gribouillis.BRUSH_PROP_CHANGED, (self.brush, 'radius_min'))

    def draw_start(self, device):
        doc = self.__doc
        self._snapshot = doc.active.snapshot()
        doc.brush.start(doc.active.surface, device)

    def draw_end(self):
        doc = self.__doc
        doc.brush.stop()
        self.sendNotification(main.Gribouillis.DOC_RECORD_STROKE,
                              LayerCommandVO(self, doc.active, snapshot=self._snapshot, stroke=[]),
                              type=utils.RECORDABLE_COMMAND)
        del self._snapshot

    def draw_stroke(self):
        return self.__doc.brush.record()

    #### Document layers handling ####

    def new_layer(self, vo):
        layer = self.__doc.new_layer(**vo)
        self.sendNotification(main.Gribouillis.DOC_LAYER_ADDED, (self, layer, self.__doc.get_layer_index(layer)))
        return layer

    def insert_layer(self, layer, pos=0, **k):
        self.__doc.insert_layer(layer, pos, **k)
        self.sendNotification(main.Gribouillis.DOC_LAYER_ADDED, (self, layer, self.__doc.get_layer_index(layer)))

    def remove_layer(self, layer):
        self.__doc.remove_layer(layer)
        self.sendNotification(main.Gribouillis.DOC_LAYER_DELETED, (self, layer))
        self.sendNotification(main.Gribouillis.DOC_LAYER_ACTIVATED, (self, self.__doc.active))

    def copy_layer(self, layer, pos=None):
        if pos is None:
            pos = self.__doc.get_layer_index(layer)+1
        new_layer = self.__doc.new_layer('Copy of %s' % layer.name, pos)
        new_layer.copy(layer)
        self.sendNotification(main.Gribouillis.DOC_LAYER_ADDED, (self, new_layer, self.__doc.get_layer_index(layer)))
        return new_layer

    def move_layer(self, layer, pos):
        self.__doc.move_layer(layer, pos)
        self.sendNotification(main.Gribouillis.DOC_LAYER_MOVED, (self, layer, self.__doc.get_layer_index(layer)))

    def set_layer_visibility(self, layer, state):
        state = bool(state)
        if layer.visible != state:
            vo = model.vo.LayerCommandVO(docproxy=self, layer=layer, state=state)
            self.sendNotification(main.Gribouillis.DOC_LAYER_SET_VISIBLE, vo, type=utils.RECORDABLE_COMMAND)

    def iter_visible_layers(self):
        return ( layer for layer in self.layers if layer.visible )

    def set_layer_opacity(self, layer, state):
        if state != layer.opacity:
            vo = model.vo.LayerCommandVO(docproxy=self, layer=layer, state=state)
            self.sendNotification(main.Gribouillis.DOC_LAYER_SET_OPACITY, vo)

    def scroll_layer(self, dx, dy):
        layer = self.__doc.active
        layer.x += dx
        layer.y += dy
        self.sendNotification(main.Gribouillis.DOC_LAYER_UPDATED, (self, layer))

    @staticmethod
    def rename_layer(layer, name):
        old = layer.name
        layer.name = name
        return old

    @property
    def active_layer(self):
        return self.__doc.active

    #### Properties ###

    active = property(fget=lambda self: self.get_active(),
                      fset=lambda self, v: self.set_active(v))
    document = property(fget=lambda self: self.__doc)
    docname = property(fget=lambda self: self.__doc.name, fset=set_docname)
    brush = property(fget=lambda self: self._brush, fset=_set_brush)

    @property
    def layers(self):
        return self.__doc.layers

    @property
    def modified(self):
        return self.__doc.modified
