###############################################################################
# Copyright (c) 2009-2012 Guillaume Roguez
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

import sys

try:
    import pygtk
except ImportError:
    print("PyGTK not installed on this platform")
    sys.exit(-1)

pygtk.require('2.0')

import gtk
import gtk.gdk as gdk

import main
import utils

import model
import model.brush

import view.context as ctx
import view.operator as operator

import app
import operators
import keymaps

from utils import _T, mvcHandler

from .docviewer import DocWindow
from .viewport import DocViewport
from .colorwindow import ColorWindow
from .layermgr import LayerManager
from .cmdhistoric import CommandsHistoryList
from .brushhouse import BrushHouseWindow
from .brusheditor import BrushEditorWindow

# Needed by view module
Application = app.Application

ctx.app_mediator = None # ApplicationMediator
ctx.application = None # ApplicationMediator
ctx.viewports = set() # DocViewportMediator


class GenericMediator(utils.Mediator):
    """Base class for all PyGTK mediators.
    Gives framework to display text dialog.
    """

    def show_dialog(self, tp, msg, parent=None):
        dlg = gtk.MessageDialog(parent=parent,
                                type=tp,
                                buttons=gtk.BUTTONS_OK,
                                message_format=msg)
        dlg.run()
        dlg.destroy()

    def show_error_dialog(self, msg, **k):
        self.show_dialog(gtk.MESSAGE_ERROR, msg, **k)

    def show_warning_dialog(self, msg, **k):
        self.show_dialog(gtk.MESSAGE_WARNING, msg, **k)

    def show_info_dialog(self, msg, **k):
        self.show_dialog(gtk.MESSAGE_INFO, msg, **k)

    def exec_op(self, obj, name):
        operator.execute(name)


class ApplicationMediator(GenericMediator):
    NAME = "ApplicationMediator"

    document_mediator = None

    #### Private API ####

    def __init__(self, component):
        assert isinstance(component, Application)
        super(ApplicationMediator, self).__init__(viewComponent=component)
        ctx.app_mediator = self
        ctx.application = component

    def onRegister(self):
        self.document_mediator = DocumentMediator(self.viewComponent)
        self.facade.registerMediator(self.document_mediator)
        m = ColorWindowMediator(ctx.windows['ColorManager'])
        self.facade.registerMediator(m)
        m = LayerManagerMediator(ctx.windows['LayerManager'])
        self.facade.registerMediator(m)
        m = CommandsHistoryListMediator(ctx.windows['CmdHist'])
        self.facade.registerMediator(m)
        m = BrushHouseWindowMediator(ctx.windows['BrushHouse'])
        self.facade.registerMediator(m)
        m = BrushEditorWindowMediator(ctx.windows['BrushEditor'])
        self.facade.registerMediator(m)

        # Add a default empty document
        vo = model.vo.EmptyDocumentConfigVO()
        self.sendNotification(main.NEW_DOCUMENT, vo)

    def get_document_filename(self, parent=None):
        return self.viewComponent.get_filename(parent)

    def quit(self):
        self.sendNotification(main.QUIT)

    ### notification handlers ###

    @mvcHandler(main.SHOW_ERROR_DIALOG)
    def _on_show_error(self, msg, **k):
        self.show_error_dialog(msg, **k)

    @mvcHandler(main.SHOW_WARNING_DIALOG)
    def _on_show_warn(self, msg, **k):
        self.show_warning_dialog(msg, **k)

    @mvcHandler(main.SHOW_INFO_DIALOG)
    def _on_show_info(self, msg, **k):
        self.show_info_dialog(msg, **k)

    @mvcHandler(main.QUIT)
    def _on_quit(self, note):
        # TODO: check for modified documents
        self.viewComponent.quit()


class DocumentMediator(GenericMediator):
    """DocumentMeditor()

    Handles document windows.
    """

    NAME = "DocumentMediator"

    focused = None
    __count = 0

    # private API
    def __init__(self, component):
        assert isinstance(component, Application)
        super(DocumentMediator, self).__init__(viewComponent=component)

    def __len__(self):
        return self.__count

    # UI events handlers
    def _on_focus_in_event(self, win, evt):
        self.focused = win

    def _on_delete_event(self, win, evt=None):
        #FIXME: self.sendNotification(main.DOC_DELETE, win.docproxy)

        # quit application if last document window is closed
        self.__count -= 1
        if self.__count == 0:
            self.sendNotification(main.QUIT)

    def _on_menu_new_doc(self, win):
        "Interactive new document opening (ask for doc type)"
        vo = model.vo.EmptyDocumentConfigVO()
        if self.viewComponent.get_new_document_type(vo, parent=win):
            self.sendNotification(main.NEW_DOCUMENT, vo)

    def _on_menu_load_doc(self, win):
        self.load_new_doc(win)

    def _on_menu_save_doc(self, win):
        filename = self.viewComponent.get_document_filename(parent=win,
                                                            read=False)
        if filename:
            self.sendNotification(main.DOC_SAVE, (win.docproxy, filename))

    def _on_menu_load_image_as_layer(self, win):
        self.load_image_as_layer()

    def _on_menu_open_window(self, win, name):
        self.viewComponent.open_window(name)

    # notification handlers
    @mvcHandler(main.DOC_SAVE_RESULT)
    def _on_doc_save_result(self, docproxy, result, err=None):
        if not result:
            msg = "%s:\n'%s'\n\n%s:\n\n%s" % (_T("Failed to save document"),
                                              docproxy.docname,
                                              _T("Reason"), err)
            self.show_error_dialog(msg)
        else:
            self.show_info_dialog(_T("Document saved"))

    @mvcHandler(model.DocumentProxy.DOC_ADDED)
    def _on_doc_added(self, docproxy):
        self.new_window(docproxy)

    @mvcHandler(main.DOC_ACTIVATED)
    def _on_activate_document(self, docproxy):
        ctx.active_docproxy = docproxy
        return
        win = self.get_win(docproxy)
        # present() causes a focus-in GTK event
        # and focus-in event trigs DOC_ACTIVATE.
        # So `focused` is checked to break the loop
        if win and win is not self.focused:
            win.present()

    # public API

    def register_viewport(self, viewport):
        self.facade.registerMediator(DocViewportMediator(viewport))

    def unregister_viewport(self, viewport):
        mediator = self.facade.retrieveMediator(hex(id(viewport)))
        self.facade.removeMediator(mediator)

    def new_window(self, docproxy):
        "Register and associate a document proxy to a new document window"

        win = DocWindow(docproxy, self.register_viewport,
                        self.unregister_viewport, ctx.application.keymap_mgr)

        # associate Window's events to callbacks
        win.connect("delete-event", self._on_delete_event)
        win.connect("focus-in-event", self._on_focus_in_event)
        win.connect("menu_new_doc", self._on_menu_new_doc)
        win.connect("menu_load_doc", self._on_menu_load_doc)
        win.connect("menu_close_doc", self._on_delete_event)
        win.connect("menu_save_doc", self._on_menu_save_doc)
        win.connect("menu_open_window", self._on_menu_open_window)
        win.connect("menu_load_image_as_layer",
                    self._on_menu_load_image_as_layer)
        self.__count += 1

    def load_new_doc(self, win):
        filename = self.viewComponent.get_document_filename(parent=win)
        if filename:
            vo = model.vo.FileDocumentConfigVO(filename, win.docproxy)
            self.sendNotification(main.NEW_DOCUMENT, vo)


class DocViewportMediator(GenericMediator):
    NAME = "DocViewportMediator"

    # private API
    def __init__(self, component):
        assert isinstance(component, DocViewport)
        self.NAME = hex(id(component))
        super(DocViewportMediator, self).__init__(viewComponent=component)

    def onRegister(self):
        self.viewComponent.mediator = self
        ctx.viewports.add(self.viewComponent)

    def onRemove(self):
        self.viewComponent.mediator = None
        ctx.viewports.remove(self.viewComponent)

    # notification handlers

    @mvcHandler(model.DocumentProxy.DOC_UPDATED)
    def _on_doc_updated(self, docproxy, area=None):
        if area:
            area = self.viewComponent.get_view_area(*area)
        self.viewComponent.repaint(area)

    @mvcHandler(model.LayerProxy.LAYER_DIRTY)
    def _on_layer_dirty(self, docproxy, layer, area=None):
        "Redraw given area. If area is None => full redraw."

        if area:
            area = self.viewComponent.get_view_area(*area)
        self.viewComponent.repaint(area)

    @mvcHandler(model.DocumentProxy.DOC_LAYER_ADDED)
    @mvcHandler(main.DOC_LAYER_STACK_CHANGED)
    @mvcHandler(main.DOC_LAYER_UPDATED)
    @mvcHandler(main.DOC_LAYER_DELETED)
    def _on_layer_repaint(self, docproxy, layer, *args):
        "Specific layer repaint, limited to its area."

        if not layer.empty:
            area = layer.area
            vp = self.viewComponent
            vp.repaint(vp.get_view_area(*area))

    @mvcHandler(model.BrushProxy.BRUSH_PROP_CHANGED)
    def _on_brush_prop_changed(self, brush, name):
        "Update viewport brush rendering"

        if name is 'radius_max':
            self.viewComponent.set_cursor_radius(getattr(brush, name))


class BrushEditorWindowMediator(GenericMediator):
    NAME = "BrushEditorWindowMediator"

    # private API
    def __init__(self, component):
        assert isinstance(component, BrushEditorWindow)
        super(BrushEditorWindowMediator, self).__init__(viewComponent=component)
        component.mediator = self

    # notification handlers
    @mvcHandler(model.DocumentProxy.DOC_BRUSH_UPDATED)
    def _on_use_brush(self, docproxy):
        self.viewComponent.brush = docproxy.brush


class BrushHouseWindowMediator(GenericMediator):
    NAME = "BrushHouseWindowMediator"

    # private API
    def __init__(self, component):
        assert isinstance(component, BrushHouseWindow)
        super(BrushHouseWindowMediator, self).__init__(viewComponent=component)
        component.set_current_cb(self._on_brush_selected)

        # Add brushes
        l = model.brush.Brush.load_brushes()
        for brush in l:
            component.add_brush(brush, brush.group)
        component.active_brush = l[0]

    # UI events handlers
    def _on_brush_selected(self, brush):
        ctx.brush = brush
        self.sendNotification(main.USE_BRUSH, brush)

    # notification handlers
    @mvcHandler(main.USE_BRUSH)
    def _on_use_brush(self, brush):
        if ctx.brush != brush:
            self.viewComponent.brush = brush


class CommandsHistoryListMediator(GenericMediator):
    NAME = "CommandsHistoryListMediator"

    cmdhistproxy = None

    # private API
    def __init__(self, component):
        assert isinstance(component, CommandsHistoryList)
        name = CommandsHistoryListMediator.NAME
        super(CommandsHistoryListMediator, self).__init__(name, component)

        self.__cur_hp = None

        component.btn_undo.connect('clicked', self.exec_op, 'hist_undo')
        component.btn_redo.connect('clicked', self.exec_op, 'hist_redo')
        component.btn_flush.connect('clicked', self.exec_op, 'hist_flush')

    # notification handlers
    @mvcHandler(main.DOC_ACTIVATED)
    def _on_doc_activated(self, docproxy):
        self.viewComponent.set_doc_name(docproxy.docname)
        self.__cur_hp = utils.CommandsHistoryProxy.get_active()
        self.viewComponent.from_stacks(self.__cur_hp.undo_stack,
                                       self.__cur_hp.redo_stack)

    @mvcHandler(utils.CommandsHistoryProxy.CMD_HIST_ADD)
    def _on_cmd_add(self, hp, cmd):
        if hp is self.__cur_hp:
            self.viewComponent.add_cmd(cmd)

    @mvcHandler(utils.CommandsHistoryProxy.CMD_HIST_FLUSHED)
    def _on_cmd_flush(self, hp):
        if hp is self.__cur_hp:
            self.viewComponent.flush()

    @mvcHandler(utils.CommandsHistoryProxy.CMD_HIST_UNDO)
    def _on_cmd_undo(self, hp, cmd):
        if hp is self.__cur_hp:
            self.viewComponent.undo(cmd)

    @mvcHandler(utils.CommandsHistoryProxy.CMD_HIST_REDO)
    def _on_cmd_redo(self, hp, cmd):
        if hp is self.__cur_hp:
            self.viewComponent.redo(cmd)


class ColorWindowMediator(GenericMediator):
    NAME = "ColorWindowMediator"

    brushproxy = None

    # private API
    def __init__(self, component):
        assert isinstance(component, ColorWindow)
        super(ColorWindowMediator, self).__init__(ColorWindowMediator.NAME,
                                                  component)
        self.brushproxy = self.facade.retrieveProxy(model.BrushProxy.NAME)
        component.colorsel.connect('color-changed', self._on_color_changed)

    def _on_color_changed(self, widget):
        color = widget.get_current_color()
        self.brushproxy.set_color_rgb(ctx.active_docproxy.brush,
                                      color.red_float,
                                      color.green_float,
                                      color.blue_float)

    # notification handlers
    @mvcHandler(main.DOC_ACTIVATED)
    def _on_doc_activated(self, docproxy):
        brush = docproxy.document.brush
        self.viewComponent.set_color_rgb(brush.rgb)


class LayerManagerMediator(GenericMediator):
    NAME = "LayerManagerMediator"

    # private API
    def __init__(self, component):
        assert isinstance(component, LayerManager)
        super(LayerManagerMediator, self).__init__(viewComponent=component)

        self.__docproxy = None

        component.btn['add'].connect('clicked', self._on_add_layer)
        component.btn['del'].connect('clicked', self._on_delete_layer)
        component.btn['up'].connect('clicked', self._on_up_layer)
        component.btn['down'].connect('clicked', self._on_down_layer)
        component.btn['top'].connect('clicked', self._on_top_layer)
        component.btn['bot'].connect('clicked', self._on_bottom_layer)
        component.btn['dup'].connect('clicked', self._on_duplicate_layer)
        component.btn['merge'].connect('clicked', self._on_merge_layer)

        component.connect('layer-active-event', self._on_layer_active_event)
        component.connect('layer-name-changed', self._on_layer_name_changed)
        component.connect('layer-operator-event',
                          self._on_layer_operator_event)
        component.connect('layer-visibility-event',
                          self._on_layer_visibility_event)

    # UI event handlers
    def _on_layer_active_event(self, w, layer):
        self.__docproxy.document.active = layer
        self.sendNotification(main.DOC_LAYER_ACTIVATE,
                              (self.__docproxy, layer))

    def _on_layer_name_changed(self, w, data):
        layer, name = data
        if layer.name != name:
            vo = model.vo.LayerCmdVO(layer=layer, docproxy=self.__docproxy,
                                     name=name)
            self.sendNotification(main.DOC_LAYER_RENAME, vo)

    def _on_layer_visibility_event(self, w, data):
        layer, state = data
        self.__docproxy.set_layer_visibility(layer, state)

    def _on_layer_operator_event(self, w, ctrl):
        layer = ctrl.layer
        layer.operator = ctrl.operator.get_active_text()
        self.sendNotification(main.DOC_LAYER_UPDATED, (self.__docproxy, layer))

    def _on_add_layer(self, *a):
        pos = self.viewComponent.get_active_position() + 1
        vo = model.vo.GenericVO(docproxy=self.__docproxy, pos=pos)
        self.sendNotification(main.DOC_LAYER_ADD, vo)

    def _on_delete_layer(self, *a):
        layer = self.viewComponent.active
        vo = model.vo.LayerCmdVO(layer=layer, docproxy=self.__docproxy)
        self.sendNotification(main.DOC_LAYER_DEL, vo)

    def _on_up_layer(self, *a):
        self.sendNotification(main.DOC_LAYER_STACK_CHANGE,
                              (self.__docproxy,
                               self.viewComponent.active,
                               self.viewComponent.get_active_position() + 1))

    def _on_down_layer(self, *a):
        self.sendNotification(main.DOC_LAYER_STACK_CHANGE,
                              (self.__docproxy,
                               self.viewComponent.active,
                               self.viewComponent.get_active_position() - 1))

    def _on_top_layer(self, *a):
        self.sendNotification(main.DOC_LAYER_STACK_CHANGE,
                              (self.__docproxy,
                               self.viewComponent.active,
                               len(self.viewComponent) - 1))

    def _on_bottom_layer(self, *a):
        self.sendNotification(main.DOC_LAYER_STACK_CHANGE,
                              (self.__docproxy, self.viewComponent.active, 0))

    def _on_duplicate_layer(self, *a):
        layer = self.viewComponent.active
        vo = model.vo.LayerCmdVO(layer, docproxy=self.__docproxy)
        self.sendNotification(main.DOC_LAYER_DUP, vo)

    def _on_merge_layer(self, *a):
        self.sendNotification(main.DOC_LAYER_MERGE_DOWN,
                              (self.__docproxy,
                               self.viewComponent.get_active_position()))

    # notification handlers
    @mvcHandler(main.DOC_DELETE)
    def _on_doc_delete(self, docproxy):
        if docproxy is self.__docproxy:
            self.viewComponent.clear()
            self.viewComponent.hide()
            self.__docproxy = None

    @mvcHandler(model.DocumentProxy.DOC_ADDED)
    @mvcHandler(model.DocumentProxy.DOC_UPDATED)
    def _on_new_doc_result(self, docproxy):
        if self.__docproxy is docproxy:
            doc = docproxy.document
            self.viewComponent.set_layers(doc.layers, doc.active)

    @mvcHandler(main.DOC_ACTIVATED)
    def _on_doc_activated(self, docproxy):
        if self.__docproxy is not docproxy:
            self.__docproxy = docproxy
            doc = docproxy.document
            self.viewComponent.set_layers(doc.layers, doc.active)

    @mvcHandler(model.DocumentProxy.DOC_LAYER_ADDED)
    def _on_doc_layer_added(self, docproxy, layer, pos):
        if self.__docproxy is docproxy:
            self.viewComponent.add_layer(layer, pos)

    @mvcHandler(main.DOC_LAYER_DELETED)
    def _on_doc_layer_deleted(self, docproxy, layer):
        if self.__docproxy is docproxy:
            self.viewComponent.del_layer(layer)

    @mvcHandler(main.DOC_LAYER_STACK_CHANGED)
    def _on_doc_layer_moved(self, docproxy, layer, pos):
        if self.__docproxy is docproxy:
            self.viewComponent.move_layer(layer, pos)

    @mvcHandler(main.DOC_LAYER_ACTIVATED)
    def _on_doc_layer_activated(self, docproxy, layer):
        if self.__docproxy is docproxy and \
                layer is not self.viewComponent.active:
            self.viewComponent.active = layer
