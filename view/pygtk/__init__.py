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

import pygtk
pygtk.require('2.0')

import gtk

import main
import model
import utils

import app

from utils import _T, mvcHandler

from .docviewer import DocWindow
from .viewport import DocViewport

gdk = gtk.gdk

# Needed by view module
Application = app.Application


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


class ApplicationMediator(GenericMediator):
    NAME = "ApplicationMediator"

    document_mediator = None

    #### Private API ####

    def __init__(self, component):
        assert isinstance(component, Application)
        super(ApplicationMediator, self).__init__(ApplicationMediator.NAME, component)

    def onRegister(self):
        #self.facade.registerMediator(LayerManagerMediator(self.viewComponent.layermgr))
        #self.facade.registerMediator(CommandsHistoryListMediator(self.viewComponent.cmdhist))
        #self.facade.registerMediator(BrushHouseWindowMediator(self.viewComponent.brushhouse))
        #self.facade.registerMediator(BrushEditorWindowMediator(self.viewComponent.brusheditor))
        #self.facade.registerMediator(ColorWindowMediator(self.viewComponent.colorwin))

        self.facade.registerMediator(DocViewportMediator(self.viewComponent))

        self.document_mediator = DocumentMediator(self.viewComponent)
        self.facade.registerMediator(self.document_mediator)

        # Add a default empty document
        vo = model.vo.EmptyDocumentConfigVO()
        self.sendNotification(main.NEW_DOCUMENT, vo)

    def get_document_filename(self, parent=None):
        return self.viewComponent.get_filename(parent)

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

    #### Public API ####

    def del_doc(self, docproxy):
        # Detach the window from the appplication and destroy it
        self.document_mediator.del_doc(docproxy)

        # Close the application if no document remains.
        if not len(self.document_mediator):
            self.viewComponent.quit()


class DocumentMediator(GenericMediator):
    """DocumentMeditor()
    
    Handles document windows.
    """

    NAME = "DocumentMediator"

    __focused = None
    viewport_mediator = None
    
    #### Private API ####

    def __init__(self, component):
        assert isinstance(component, Application)
        super(DocumentMediator, self).__init__(viewComponent=component)

        self.__docmap = {}
        self.viewport_mediator = self.facade.retrieveMediator(DocViewportMediator.NAME)

    def __len__(self):
        return len(self.__docmap)

    ### UI events handlers ###

    def _on_focus_in_event(self, win, evt):
        self.__focused = win
        self.sendNotification(main.DOC_ACTIVATE, win.docproxy)

    def _on_delete_event(self, win, evt=None):
        self.sendNotification(main.DOC_DELETE, win.docproxy)

    def _on_menu_quit(self, win):
        self.sendNotification(main.QUIT)

    def _on_menu_new_doc(self, win):
        "Interactive new document opening (ask for doc type)"
        vo = model.vo.EmptyDocumentConfigVO()
        if self.viewComponent.get_new_document_type(vo, parent=win):
            self.sendNotification(main.NEW_DOCUMENT, vo)

    def _on_menu_load_doc(self, win):
        self.load_new_doc(win)

    def _on_menu_save_doc(self, win):
        filename = self.viewComponent.get_document_filename(parent=win, read=False)
        if filename:
            self.sendNotification(main.DOC_SAVE, (win.docproxy, filename))

    def _on_menu_clear_layer(self, win):
        self.sendNotification(main.DOC_LAYER_CLEAR,
                              model.vo.LayerCommandVO(win.docproxy, win.docproxy.active_layer))

    def _on_menu_undo(self, win):
        self.sendNotification(main.UNDO)

    def _on_menu_redo(self, win):
        self.sendNotification(main.REDO)

    def _on_menu_flush(self, win):
        self.sendNotification(main.FLUSH)

    def _on_menu_load_image_as_layer(self, win):
        self.load_image_as_layer()

    ### notification handlers ###

    @mvcHandler(main.DOC_SAVE_RESULT)
    def _on_doc_save_result(self, docproxy, result, err=None):
        win = self.get_win(docproxy)
        print win
        if not result:
            self.show_error_dialog("%s:\n'%s'\n\n%s:\n\n%s" % (_T("Failed to save document"),
                                                         docproxy.docname,
                                                         _T("Reason"), err),
                                   parent=win)
        else:
            self.show_info_dialog(_T("Document saved"), parent=win)

    @mvcHandler(model.DocumentProxy.DOC_ADDED)
    def _on_doc_added(self, docproxy):
        self.add_new_doc(docproxy)

    @mvcHandler(model.DocumentProxy.DOC_UPDATED)
    def _on_doc_updated(self, docproxy):
        win = self.get_win(docproxy)
        if win:
            win.proxy_updated()

    @mvcHandler(main.DOC_ACTIVATED)
    def _on_activate_document(self, docproxy):
        win = self.get_win(docproxy)
        # present() causes a focus-in GTK event
        # and focus-in event trigs DOC_ACTIVATE.
        # So __focused is checked to break the loop
        if win and win is not self.__focused:
            win.present()

    @mvcHandler(main.BRUSH_PROP_CHANGED)
    def _on_brush_prop_changed(self, brush, name, docproxy=None):
        if name is 'color':
            return

        # synchronize storage brushes with drawing brushes.
        v = getattr(brush, name)
        for docproxy in self.__docmap.iterkeys():
            if docproxy.brush is brush:
                setattr(docproxy.document.brush, name, v)

    #### Public API ####

    def has_doc(self, docproxy):
        return docproxy in self.__docmap

    def get_win(self, docproxy):
        return self.__docmap[docproxy]

    def add_new_doc(self, docproxy):
        "Register and associate a document proxy to a new document window"

        win = DocWindow(docproxy)
        self.__docmap[docproxy] = win

        # Associate Window's events to callbacks
        win.connect("delete-event", self._on_delete_event)
        win.connect("focus-in-event", self._on_focus_in_event)
        win.connect("menu_quit", self._on_menu_quit)
        win.connect("menu_new_doc", self._on_menu_new_doc)
        win.connect("menu_load_doc", self._on_menu_load_doc)
        win.connect("menu_close_doc", self._on_delete_event)
        win.connect("menu_save_doc", self._on_menu_save_doc)
        win.connect("menu_clear_layer", self._on_menu_clear_layer)
        win.connect("menu_load_image_as_layer", self._on_menu_load_image_as_layer)

        # Attach viewports to mediators
        map(self.viewport_mediator.add_viewport, win.viewports)

    def del_doc(self, docproxy):
        win = self.__docmap.pop(docproxy)
        win.destroy()

    def load_new_doc(self, win):
        filename = self.viewComponent.get_document_filename(parent=win)
        if filename:
            vo = model.vo.FileDocumentConfigVO(filename, win.docproxy)
            self.sendNotification(main.NEW_DOCUMENT, vo)


class DocViewportMediator(GenericMediator):
    NAME = "DocViewportMediator"

    #### Private API ####

    def __init__(self, component):
        assert isinstance(component, Application)
        super(DocViewportMediator, self).__init__(viewComponent=component)
        self.__vpmap = {}

    ### public API ####

    def add_viewport(self, viewport):
        dp = viewport.docproxy
        vpl = self.__vpmap.get(dp)
        if vpl:
            vpl.append(viewport)
        else:
            self.__vpmap[dp] = [viewport]

    ### notification handlers ###

    @mvcHandler(model.DocumentProxy.DOC_UPDATED)
    def _on_doc_updated(self, docproxy, area=None):
        """Called when specific document area need to be rasterized.
        If area is None, full visible area is considered.
        Rasterization is processed on whole document,
        for all viewports.
        """

        repaint = DocViewport.repaint

        if area:
            for vp in self.__vpmap[docproxy]:
                repaint(vp.get_view_area(*area))
        else:
            map(repaint, self.__vpmap[docproxy])

    @mvcHandler(model.LayerProxy.LAYER_DIRTY)
    def _on_doc_dirty(self, docproxy, layer, area=None):
        "Redraw given area. If area is None => full redraw."
        repaint = DocViewport.repaint
        if area:
            for vp in self.__vpmap[docproxy]:
                repaint(vp, vp.get_view_area(*area))
        else:
            map(repaint, self.__vpmap[docproxy])

    @mvcHandler(model.DocumentProxy.DOC_LAYER_ADDED)
    @mvcHandler(main.DOC_LAYER_STACK_CHANGED)
    @mvcHandler(main.DOC_LAYER_UPDATED)
    @mvcHandler(main.DOC_LAYER_DELETED)
    def _on_layer_dirty(self, docproxy, layer, *args):
        "Specific layer repaint, limited to its area."
        if not layer.empty:
            area = layer.area
            for vp in self.__vpmap[docproxy]:
                vp.repaint(vp.get_view_area(*area))

    @mvcHandler(main.BRUSH_PROP_CHANGED)
    def _on_brush_prop_changed(self, brush, name, docproxy=None):
        if name is 'radius_max' and docproxy:
            r = getattr(brush, name)
            for vp in self.__vpmap[docproxy]:
                vp.set_cursor_radius(r)


class BrushEditorWindowMediator(GenericMediator):
    NAME = "BrushEditorWindowMediator"

    #### Private API ####

    def __init__(self, component):
        assert isinstance(component, BrushEditorWindow)
        super(BrushEditorWindowMediator, self).__init__(viewComponent=component)

        component.mediator = self

    def _set_docproxy(self, docproxy):
        #print "[BE] using brush BH=%s" % docproxy.brush
        self.viewComponent.brush = docproxy.brush

    ### notification handlers ###

    @mvcHandler(main.DOC_ACTIVATED)
    def _on_activate_document(self, docproxy):
        if docproxy.brush:
            self._set_docproxy(docproxy)

    @mvcHandler(main.DOC_BRUSH_UPDATED)
    def _on_activate_document(self, docproxy):
        self._set_docproxy(docproxy)


class BrushHouseWindowMediator(GenericMediator):
    NAME = "BrushHouseWindowMediator"

    #### Private API ####

    def __init__(self, component):
        assert isinstance(component, BrushHouseWindow)
        super(BrushHouseWindowMediator, self).__init__(viewComponent=component)

        self._docproxy = None  # active document
        component.set_current_cb(self._on_brush_selected)

    def _on_brush_selected(self, brush):
        #print "[BH] active brush:", brush
        self._docproxy.brush = brush  # this cause docproxy to copy brush data to the document drawable brush

    ### notification handlers ###

    @mvcHandler(main.DOC_ACTIVATED)
    def _on_activate_document(self, docproxy):
        # keep silent if no change
        if docproxy is self._docproxy:
            return
        self._docproxy = docproxy

        # Check if the document has a default brush, assign current default one if not
        if not docproxy.brush:
            #print "[BH] new doc, default brush is %s" % self.viewComponent.active_brush
            docproxy.brush = self.viewComponent.active_brush
        else:
            # change current active brush by the docproxy one
            self.viewComponent.active_brush = docproxy.brush

    @mvcHandler(main.DOC_DELETE)
    def _on_delete_document(self, docproxy):
        if docproxy is self._docproxy:
            self._docproxy = None

    @mvcHandler(main.BRUSH_PROP_CHANGED)
    def _on_brush_prop_changed(self, brush, name, *a):
        if name is 'color':
            return
        setattr(self._docproxy.brush, name, getattr(brush, name))


class CommandsHistoryListMediator(GenericMediator):
    NAME = "CommandsHistoryListMediator"

    cmdhistproxy = None

    #### Private API ####

    def __init__(self, component):
        assert isinstance(component, CommandsHistoryList)
        super(CommandsHistoryListMediator, self).__init__(CommandsHistoryListMediator.NAME, component)

        self.__cur_hp = None

        component.btn_undo.connect('clicked', self._on_undo)
        component.btn_redo.connect('clicked', self._on_redo)
        component.btn_flush.connect('clicked', self._on_flush)

    #### Protected API ####

    def _on_undo(self, *a):
        self.sendNotification(main.UNDO)

    def _on_redo(self, *a):
        self.sendNotification(main.REDO)

    def _on_flush(self, *a):
        self.sendNotification(main.FLUSH)

    ### notification handlers ###

    @mvcHandler(main.DOC_ACTIVATED)
    def _on_doc_activated(self, docproxy):
        self.viewComponent.set_doc_name(docproxy.docname)
        self.__cur_hp = utils.CommandsHistoryProxy.get_active()
        self.viewComponent.from_stacks(self.__cur_hp.undo_stack, self.__cur_hp.redo_stack)

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

    #### Private API ####

    def __init__(self, component):
        assert isinstance(component, ColorWindow)
        super(ColorWindowMediator, self).__init__(ColorWindowMediator.NAME, component)

        component.colorsel.connect('color-changed', self._on_color_changed)

    def _on_color_changed(self, widget):
        color = widget.get_current_color()
        model.DocumentProxy.get_active().set_brush_color_rgb(color.red_float, color.green_float, color.blue_float)

    ### notification handlers ###

    @mvcHandler(main.DOC_ACTIVATED)
    def _on_activate_document(self, docproxy):
        brush = docproxy.document.brush
        self.viewComponent.set_color_rgb(brush.rgb)


class LayerManagerMediator(GenericMediator):
    NAME = "LayerManagerMediator"

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
        component.connect('layer-visibility-event', self._on_layer_visibility_event)
        component.connect('layer-operator-event', self._on_layer_operator_event)

    #### UI event handlers ####

    def _on_layer_active_event(self, w, layer):
        self.__docproxy.document.active = layer
        self.sendNotification(main.DOC_LAYER_ACTIVATE, (self.__docproxy, layer))

    def _on_layer_name_changed(self, w, data):
        layer, name = data
        if layer.name != name:
            vo = model.vo.LayerCommandVO(docproxy=self.__docproxy, layer=layer, name=name)
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
        vo = model.vo.LayerConfigVO(docproxy=self.__docproxy, pos=pos)
        self.sendNotification(main.DOC_LAYER_ADD, vo)

    def _on_delete_layer(self, *a):
        layer = self.viewComponent.active
        vo = model.vo.LayerCommandVO(docproxy=self.__docproxy, layer=layer)
        self.sendNotification(main.DOC_LAYER_DEL, vo)

    def _on_up_layer(self, *a):
        self.sendNotification(main.DOC_LAYER_STACK_CHANGE,
                              (self.__docproxy, self.viewComponent.active, self.viewComponent.get_active_position() + 1))

    def _on_down_layer(self, *a):
        self.sendNotification(main.DOC_LAYER_STACK_CHANGE,
                              (self.__docproxy, self.viewComponent.active, self.viewComponent.get_active_position() - 1))

    def _on_top_layer(self, *a):
        self.sendNotification(main.DOC_LAYER_STACK_CHANGE,
                              (self.__docproxy, self.viewComponent.active, len(self.viewComponent) - 1))

    def _on_bottom_layer(self, *a):
        self.sendNotification(main.DOC_LAYER_STACK_CHANGE,
                              (self.__docproxy, self.viewComponent.active, 0))

    def _on_duplicate_layer(self, *a):
        layer = self.viewComponent.active
        vo = model.vo.LayerCommandVO(docproxy=self.__docproxy, layer=layer)
        self.sendNotification(main.DOC_LAYER_DUP, vo)

    def _on_merge_layer(self, *a):
        self.sendNotification(main.DOC_LAYER_MERGE_DOWN,
                              (self.__docproxy, self.viewComponent.get_active_position()))

    #### notification handlers ####

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
            self.viewComponent.set_layers(docproxy.layers, docproxy.document.active)

    @mvcHandler(main.DOC_ACTIVATED)
    def _on_doc_activated(self, docproxy):
        if self.__docproxy is not docproxy:
            self.__docproxy = docproxy
            self.viewComponent.set_layers(docproxy.layers, docproxy.document.active)

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
        if self.__docproxy is docproxy and layer is not self.viewComponent.active:
            self.viewComponent.active = layer

