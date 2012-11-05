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
import re
from puremvc.patterns.proxy import Proxy
from itertools import imap

import main
import utils
import model
import model.vo as _vo

from utils import _T
from .document import Document
from .layer import Layer
from .palette import Palette
from ._prefs import prefs, IPrefHandler


class PrefsProxy(Proxy):
    NAME = "Preferences"
    PREFS_CHANGED = 'prefs-changed'
    
    def __init__(self, data=None):
        Proxy.__init__(self, self.NAME, _prefs.prefs)

        # load saved config
        self.load('config.xml')

        # export prefs instance into model module
        model.prefs = self

    def __getitem__(self, key):
        return self.data[key]
        
    def __setitem__(self, key, value):
        self.data[key] = value
        self.sendNotification(main.PREFS_CHANGED, key)

    def set_to_defaults(self):
        self.data.set_to_defaults()
        self.sendNotification(main.PREFS_CHANGED)

    def __getattr__(self, name):
        try:
            return self.data.__getattribute__(name)
        except:
            return Proxy.__getattribute__(self, name)


class LayerProxy(Proxy):
    """LayerProxy()

    Dynamic proxy for document's layers.
    """

    NAME = "LayerProxy"

    ###
    ### Notifications
    
    LAYER_DIRTY = 'layer-dirty'

    ###
    ### Object API

    def __init__(self, docproxy):
        super(LayerProxy, self).__init__()
        self.docproxy = docproxy

    ###
    ### Public API

    def handle_dirty(self, layer, area):
        if layer.dirty:
            self.sendNotification(self.LAYER_DIRTY, (self.docproxy, layer, area))
            layer.dirty = 0

    def clear(self, layer):
        snapshot = layer.snapshot()
        layer.clear()
        self.handle_dirty(layer, snapshot.area)
        return snapshot

    def unsnapshot(self, layer, snapshot, *a):
        layer.unsnapshot(snapshot, *a)
        self.handle_dirty(layer, snapshot.dirty_area)


class DocumentProxy(Proxy):
    """DocumentProxy(document)

    Implement proxy on Document instance.
    Is responsible of:
      - provide document's API.
      - check documents unicity over names.
    """

    ### Notifications
    DOC_ADDED = 'doc-added'
    DOC_UPDATED = 'doc-updated'  # one or more document properties has been modified
    DOC_LAYER_ADDED = 'doc-layer-added'
    DOC_DIRTY = 'doc-dirty'
    DOC_BRUSH_UPDATED = 'doc-brush-updated'

    #### Private API ####
    __instances = {}  # All registered DocumentProxy instances
    profile = None    # Color profile
    docname_num_match = re.compile('(.* #)([0-9]+)').match
    layerproxy = None
    active = None
    refcnt = 0

    def __init__(self, doc):
        assert isinstance(doc, Document)
        super(DocumentProxy, self).__init__(str(id(self)), doc)
        self.facade.registerProxy(self)

    def _attach_cmd_hist(self):
        hp_name = 'HP_' + self.getProxyName()
        assert not self.facade.hasProxy(hp_name)
        hp = utils.CommandsHistoryProxy(name=hp_name, data=self)
        self.facade.registerProxy(hp)

    def _check_name(self, name):
        if name in DocumentProxy.__instances:
            raise NameError(_T('document name already exists'))

    @staticmethod
    def _new_doc(vo):
        if isinstance(vo, _vo.FileDocumentConfigVO):
            return Document.new_from(vo.name)
        elif isinstance(vo, _vo.EmptyDocumentConfigVO):
            return Document(vo.name, colorspace=vo.colorspace)

        raise TypeError("Bad vo argument type %s" % type(vo))

    #### MVC API ####
    def onRegister(self):
        self._check_name(self.data.name)
        self._attach_cmd_hist()
        DocumentProxy.__instances[self.data.name] = self
        self.layerproxy = LayerProxy(self)
        self.facade.registerProxy(self.layerproxy)

    def onRemove(self):
        del DocumentProxy.__instances[self.data.name]
        self.data = None
        hp_name = 'HP_' + self.getProxyName()
        self.facade.removeProxy(self.getProxyName())
        self.facade.removeProxy(self.layerproxy)

    #### Public API ####
    def obtain(self):
        self.refcnt += 1
    
    def release(self):
        self.refcnt -= 1
        if self.refcnt < 1:
            self.sendNotification(main.DOC_DELETE, self)
        
    def activate(self):
        DocumentProxy.active = self
        self.sendNotification(main.DOC_ACTIVATED, self)
    
    @classmethod
    def get_unique_name(cls, basename=None):
        """Return a unique document name.
        A base name can be given.
        """
        
        if not basename:
            basename = _T("New Empty Document")

        if basename in cls.__instances:
            match =  cls.docname_num_match(basename)
            if match:
                basename, n = match.groups()
                basename += str(int(n) + 1)
            else:
                basename += ' #2'

        return basename

    @classmethod
    def from_doc_name(cls, name):
        return cls.__instances.get(name)

    @classmethod
    def iternames(cls):
        return cls.__instances.iterkeys()

    @classmethod
    def proxies(cls):
        return cls.__instances.itervalues()

    @classmethod
    def has_modified(cls):
        return any(imap(lambda dp: dp.document.modified and not dp.document.empty, cls.__instances.itervalues()))

    @classmethod
    def new_proxy(cls, vo):
        """
        Helper classmethod to create DocumentProxy with document
        depending on DocumentConfigVO given.
        """

        self = cls(cls._new_doc(vo))

        # Docproxy ready to be used
        self.sendNotification(cls.DOC_ADDED, self)
        return self

    @classmethod
    def new_doc(cls, vo):
        if isinstance(vo, model.vo.EmptyDocumentConfigVO):
            vo.name = cls.get_unique_name(vo.name)
            docproxy = cls.new_proxy(vo)
        else:
            # FileDocumentConfigVO
            # Search first if document isn't created yet,
            # if is it, the existing document is just activated.
            # New document are created/loaded then activated.

            docproxy = cls.from_doc_name(vo.name)
            if not docproxy:
                # If the active docproxy is in 'safe' state (empty or
                # untouched), it's going to be used as container for the
                # wanted document. Otherwise a new docproxy is created.
                docproxy = vo.docproxy
                if not docproxy or not docproxy.document.close_safe:
                    docproxy = cls.new_proxy(vo)
                else:
                    docproxy.load(vo.name)
        return docproxy

    def load(self, filename):
        """Replace current document by loading a new one.
        """

        # New document from file
        vo = _vo.FileDocumentConfigVO(filename)
        doc = self._new_doc(vo)
        
        # Replace
        proxy = DocumentProxy.__instances.pop(self.docname)
        self.data = doc
        DocumentProxy.__instances[doc.name] = self

        # Notify
        self.sendNotification(self.DOC_UPDATED, self)

    def create_default_doc(self):
        path = model.prefs.get('default-document')
        if docpath is None:
            vo = model.vo.EmptyDocumentConfigVO()
        else:
            vo = model.vo.FileDocumentConfigVO(docpath)
        self.sendNotification(main.NEW_DOCUMENT, vo)

    def undo(self):
        hp = self.facade.retrieveProxy('HP_' + self.getProxyName())
        if hp.canUndo():
            hp.getPrevious().undo()

    def redo(self):
        hp = self.facade.retrieveProxy('HP_' + self.getProxyName())
        if hp.canRedo():
            hp.getNext().redo()

    def flush(self):
        self.facade.retrieveProxy('HP_' + self.getProxyName()).flush()

    #### Document access API ####
    def get_name(self):
        return self.data.name

    def set_name(self, name):
        doc = self.data

        # No-op
        if name == doc.name:
            return

        self._check_name(name)

        del DocumentProxy.__instances[doc.name]
        DocumentProxy.__instances[name] = self
        doc.name = name
        self.sendNotification(self.DOC_UPDATED, self)

    def set_background(self, value):
        self.data.fill = value
        self.sendNotification(self.DOC_DIRTY, self)

    def set_metadata(self, **kwds):
        change = False
        for k in kwds:
            if k in self.data.metadata:
                self.data.metadata[k] = kwds[k]
                change = True
                
        if change:
            self.sendNotification(self.DOC_UPDATED, self)

    #### Brush handling ####
    def set_brush(self, brush):
        self.document.brush.set_from_brush(brush)
        self.sendNotification(self.DOC_BRUSH_UPDATED, self)

    #### Painting ####
    def draw_start(self, device):
        doc = self.data
        layer = doc.active

        if layer.locked:
            # Do not record if surface is locked
            self.record = utils.idle_cb
            self._layer = None
            return

        self.record = self._record
        surface = layer.surface
        self._dev = device
        self._layer = layer
        self._snapshot = layer.snapshot()  # for undo
        state = device.current
        self._stroke = [state]
        doc.brush.start(surface, state)

    def draw_end(self):
        layer = self._layer
        doc = self.data
        area = doc.brush.stop()
        if area:
            layer.dirty = True
            area = layer.document_area(*area)
            self.layerproxy.handle_dirty(layer, area)

        ss = self._snapshot
        if ss.reduce(layer.surface):
            self.sendNotification(
                main.DOC_RECORD_STROKE,
                model.vo.LayerCmdVO(docproxy=self,
                                    layer=layer,
                                    snapshot=ss,
                                    stroke=self._stroke))
            del self._snapshot, self._layer, self._stroke, self._dev

    def _record(self):
        state = self._dev.current
        self._stroke.append(state)
        area = self.data.brush.draw_stroke(state)
        if area:
            layer = self._layer
            layer.dirty = True
            area = layer.document_area(*area)
            self.layerproxy.handle_dirty(layer, area)

    ####
    #### Document layers handling ####

    def new_layer(self, vo):
        layer = self.data.new_layer(**vo)
        self.sendNotification(self.DOC_LAYER_ADDED,
                              (self, layer,
                               self.data.index(layer)))
        return layer

    def insert_layer(self, layer, pos=None, **k):
        self.data.insert_layer(layer, pos, **k)
        self.sendNotification(self.DOC_LAYER_ADDED,
                              (self, layer,
                               self.data.index(layer)))

    def remove_layer(self, layer):
        self.data.remove_layer(layer)
        self.sendNotification(main.DOC_LAYER_DELETED, (self, layer))
        self.sendNotification(main.DOC_LAYER_ACTIVATED,
                              (self, self.active_layer))

    def copy_layer(self, layer, pos=None):
        if pos is None:
            pos = self.data.get_layer_index(layer) + 1
        new_layer = self.data.new_layer(_T('Copy of %s') % layer.name, pos)
        new_layer.copy(layer)
        self.sendNotification(main.DOC_LAYER_ADDED,
                              (self, new_layer,
                               self.data.get_layer_index(layer)))
        return new_layer

    def move_layer(self, layer, pos=None):
        self.data.move_layer(layer, pos)
        self.sendNotification(main.DOC_LAYER_STACK_CHANGED,
                              (self, layer,
                               self.data.get_layer_index(layer)))

    def set_layer_visibility(self, layer, state):
        state = bool(state)
        if layer.visible != state:
            vo = model.vo.GenericVO(docproxy=self,
                                    layer=layer,
                                    state=state)
            self.sendNotification(main.DOC_LAYER_SET_VISIBLE, vo)

    def iter_visible_layers(self):
        return (layer for layer in self.layers if layer.visible)

    def set_layer_opacity(self, layer, value):
        if value != layer.opacity:
            vo = model.vo.GenericVO(docproxy=self,
                                    layer=layer,
                                    state=value)
            self.sendNotification(main.DOC_LAYER_SET_OPACITY, vo)

    def record_layer_matrix(self, layer, old_mat):
        if not layer.empty:
            self.sendNotification(main.DOC_LAYER_MATRIX,
                                  (self, layer, old_mat,
                                   cairo.Matrix(*layer.matrix)))

    def layer_translate(self, *delta):
        layer = self.data.active
        if layer.empty:
            return
        area = layer.area
        if not area:
            return

        layer.translate(*delta)

        # Refresh the old area + the new layer area
        area = utils.join_area(area, layer.area)
        self.sendNotification(self.DOC_DIRTY, (self, area))

    def layer_rotate(self, angle, ox=0, oy=0):
        layer = self.data.active
        if layer.empty:
            return
        area = layer.area
        if not area:
            return

        matrix = layer.matrix
        matrix.translate(ox, oy)
        matrix.rotate(angle)
        matrix.translate(-ox, -oy)

        layer.matrix = matrix

        # Refresh the old area + the new layer area
        area = utils.join_area(area, layer.area)
        self.sendNotification(self.DOC_DIRTY, (self, area))

    def get_layer_pos(self, *pos):
        layer = self.data.active
        return layer.inv_matrix.transform_point(*pos)

    def get_layer_dist(self, *dist):
        layer = self.data.active
        return layer.inv_matrix.transform_distance(*dist)

    def clear_layer(self, layer=None):
        vo = _vo.LayerCmdVO(docproxy=self, layer=self.active_layer)
        self.sendNotification(main.LAYER_CLEAR, vo)

    ####
    #### Properties ###

    document = property(fget=lambda self: self.data)
    docname = property(fget=lambda self: self.data.name, fset=set_name)
    brush = property(fget=lambda self: self.data.brush, fset=set_brush)
    active_layer = property(fget=lambda self: self.data.active)
    

class BrushProxy(Proxy):
    NAME = "BrushProxy"

    BRUSH_PROP_CHANGED = "brush-prop-changed"

    __instances = set()

    def __init__(self):
        super(BrushProxy, self).__init__(data=brush)
        self.facade.registerProxy(self)

    @staticmethod
    def add_brush(brush):
        BrushProxy.__instances.add(brush)

    @staticmethod
    def remove_brush(brush):
        BrushProxy.__instances.remove(brush)

    @staticmethod
    def has_brush(name):
        return any(lambda b: b.name == name, BrushProxy.__instances)

    @staticmethod
    def get_brush(name, group=None):
        if group is None:
            brush_ok = lambda b: b.name == name
        else:
            brush_ok = lambda b: b.group == group and b.name == name

        for brush in self.__instances:
            if brush_ok(brush):
                return brush

    def set_attr(self, brush, name, v):
        setattr(brush, name, v)
        self.sendNotification(self.BRUSH_PROP_CHANGED, (brush, name))

    def set_color_hsv(self, brush, *hsv):
        if brush.hsv != hsv:
            brush.hsv = hsv
            self.sendNotification(self.BRUSH_PROP_CHANGED, (brush, 'color'))

    def set_color_rgb(self, brush, *rgb):
        if brush.rgb != rgb:
            brush.rgb = rgb
            self.sendNotification(self.BRUSH_PROP_CHANGED, (brush, 'color'))

    def set_radius(self, brush, r):
        r = brush.bound_radius(r)
        r = min(max(r, brush.RADIUS_MIN), brush.RADIUS_MAX)
        if brush.radius_max != r:
            brush.radius_max = r
            self.sendNotification(self.BRUSH_PROP_CHANGED,
                                  (brush, 'radius_max'))
        if brush.radius_min != r:
            brush.radius_min = r
            self.sendNotification(self.BRUSH_PROP_CHANGED,
                                  (brush, 'radius_min'))

    def add_to_radius(self, brush, dr):
        r = min(max(0.5, dr + max(brush.radius_min, brush.radius_max)),
                brush.RADIUS_MAX)
        if brush.radius_max != r:
            brush.radius_max = r
            self.sendNotification(self.BRUSH_PROP_CHANGED,
                                  (brush, 'radius_max'))
        if brush.radius_min != r:
            brush.radius_min = r
            self.sendNotification(self.BRUSH_PROP_CHANGED,
                                  (brush, 'radius_min'))

    def set_max_radius(self, brush, r):
        r = min(max(r, 0.5), brush.RADIUS_MAX)
        if brush.radius_max != r:
            brush.radius_max = r
            self.sendNotification(self.BRUSH_PROP_CHANGED,
                                  (brush, 'radius_max'))

    def add_to_max_radius(self, brush, dr):
        r = min(max(0.5, brush.radius_max + dr), brush.RADIUS_MAX)
        if brush.radius_max != r:
            brush.radius_max = r
            self.sendNotification(brush.BRUSH_PROP_CHANGED,
                                  (brush, 'radius_max'))

    def set_min_radius(self, brush, r):
        r = min(max(r, 0.5), brush.RADIUS_MAX)
        if brush.radius_min != r:
            brush.radius_min = r
            self.sendNotification(self.BRUSH_PROP_CHANGED,
                                  (brush, 'radius_min'))

    def add_to_radius_min(self, brush, dr):
        r = min(max(0.5, brush.radius_min + dr), brush.RADIUS_MAX)
        if brush.radius_min != r:
            brush.radius_min = r
            self.sendNotification(self.BRUSH_PROP_CHANGED,
                                  (brush, 'radius_min'))

    def add_to_color(self, brush, *factors):
        hsv = [c + f for c, f in zip(self.get_brush_color_hsv(brush), factors)]
        self.set_brush_color_hsv(brush, *hsv)

    def multiply_color(self, brush, *factors):
        hsv = [c * f for c, f in zip(self.get_brush_color_hsv(brush), factors)]
        self.set_brush_color_hsv(brush, *hsv)
