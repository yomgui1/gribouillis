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

import pygtk
pygtk.require('2.0')
import gtk

import main, model, utils
from utils import Mediator, mvcHandler, RECORDABLE_COMMAND, _T
from model import vo
from view.contexts import action

from app import Application
#from docviewer import DocWindow
#from brusheditor import BrushEditorWindow
#from layermgr import LayerManager
#from cmdhistoric import CommandsHistoryList
#from colorwindow import ColorWindow
#from brushhouse import BrushHouseWindow

gdk = gtk.gdk

class DialogMediator(Mediator):
    NAME = "DialogMediator"

    def show_dialog(self, type, msg):
        dlg = gtk.MessageDialog(self.viewComponent,
                                type=type,
                                buttons=gtk.BUTTONS_OK,
                                message_format=msg)
        dlg.run()
        dlg.destroy()

    #### notification handlers ####

    @mvcHandler(main.Gribouillis.SHOW_ERROR_DIALOG)
    def on_show_error(self, msg):
        self.show_dialog(gtk.MESSAGE_ERROR, msg)

    @mvcHandler(main.Gribouillis.SHOW_WARNING_DIALOG)
    def on_show_warning(self, msg):
        self.show_dialog(gtk.MESSAGE_WARNING, msg)

    @mvcHandler(main.Gribouillis.SHOW_INFO_DIALOG)
    def on_show_info(self, msg):
        self.show_dialog(gtk.MESSAGE_INFO, msg)

class ApplicationMediator(Mediator):
    NAME = "ApplicationMediator"

    document_mediator = None
    viewport_mediator = None

    #### Private API ####

    def __init__(self, component):
        assert isinstance(component, Application)
        super(ApplicationMediator, self).__init__(ApplicationMediator.NAME, component)

    def onRegister(self):
        self.facade.registerMediator(DialogMediator(self.viewComponent))
        #self.facade.registerMediator(LayerManagerMediator(self.viewComponent.layermgr))
        #self.facade.registerMediator(CommandsHistoryListMediator(self.viewComponent.cmdhist))
        #self.facade.registerMediator(BrushHouseWindowMediator(self.viewComponent.brushhouse))
        #self.facade.registerMediator(BrushEditorWindowMediator(self.viewComponent.brusheditor))
        #self.facade.registerMediator(ColorWindowMediator(self.viewComponent.colorwin))

        #self.viewport_mediator = DocViewPortMediator(self.viewComponent)
        #self.facade.registerMediator(self.viewport_mediator)

        #self.document_mediator = DocumentMediator(self.viewComponent)
        #self.facade.registerMediator(self.document_mediator)

    def get_document_filename(self, parent=None):
        return self.viewComponent.get_filename(parent)

    ### notification handlers ###

    @mvcHandler(main.Gribouillis.NEW_DOCUMENT_RESULT)
    def _on_new_document_result(self, docproxy):
        if not docproxy:
            self.sendNotification(main.Gribouillis.SHOW_ERROR_DIALOG,
                                  "Failed to create document.")
            return
        print docproxy
        self.new_doc(docproxy)

    @mvcHandler(main.Gribouillis.DOC_ACTIVATED)
    def _on_activate_document(self, docproxy):
        return
        if not self.document_mediator.has_doc(docproxy):
            self.new_doc(docproxy)

    @mvcHandler(main.Gribouillis.QUIT)
    def _on_quit(self, note):
        # TODO: check for modified documents
        self.viewComponent.quit()

    #### Public API ####

    def new_doc(self, docproxy):
        # Create and attach a window to view/edit the document
        component = DocWindow(docproxy)
 
        # Register it to document mediator
        self.document_mediator.add_doc(docproxy, component)

    def del_doc(self, docproxy):
        # Detach the window from the appplication and destroy it
        win = self.document_mediator.del_doc(docproxy)
        win.destroy()

        # Close the application if no document remains.
        if not len(self.document_mediator):
            self.viewComponent.quit()

class BrushEditorWindowMediator(Mediator):
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

    @mvcHandler(main.Gribouillis.DOC_ACTIVATED)
    def _on_activate_document(self, docproxy):
        if docproxy.brush:
            self._set_docproxy(docproxy)

    @mvcHandler(main.Gribouillis.DOC_BRUSH_UPDATED)
    def _on_activate_document(self, docproxy):
        self._set_docproxy(docproxy)

class BrushHouseWindowMediator(Mediator):
    NAME = "BrushHouseWindowMediator"

    #### Private API ####

    def __init__(self, component):
        assert isinstance(component, BrushHouseWindow)
        super(BrushHouseWindowMediator, self).__init__(viewComponent=component)

        self._docproxy = None # active document
        component.set_current_cb(self._on_brush_selected)

    def _on_brush_selected(self, brush):
        #print "[BH] active brush:", brush
        self._docproxy.brush = brush # this cause docproxy to copy brush data to the document drawable brush

    ### notification handlers ###

    @mvcHandler(main.Gribouillis.DOC_ACTIVATED)
    def _on_activate_document(self, docproxy):
        # keep silent if no change
        if docproxy is self._docproxy: return
        self._docproxy = docproxy

        # Check if the document has a default brush, assign current default one if not
        if not docproxy.brush:
            #print "[BH] new doc, default brush is %s" % self.viewComponent.active_brush
            docproxy.brush = self.viewComponent.active_brush
        else:
            # change current active brush by the docproxy one
            self.viewComponent.active_brush = docproxy.brush

    @mvcHandler(main.Gribouillis.DOC_DELETE)
    def _on_delete_document(self, docproxy):
        if docproxy is self._docproxy:
            self._docproxy = None

    @mvcHandler(main.Gribouillis.BRUSH_PROP_CHANGED)
    def _on_brush_prop_changed(self, brush, name):
        if name is 'color': return
        setattr(self._docproxy.brush, name, getattr(brush, name))

class CommandsHistoryListMediator(Mediator):
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
        self.sendNotification(main.Gribouillis.UNDO)

    def _on_redo(self, *a):
        self.sendNotification(main.Gribouillis.REDO)

    def _on_flush(self, *a):
        self.sendNotification(main.Gribouillis.FLUSH)

    ### notification handlers ###

    @mvcHandler(main.Gribouillis.DOC_ACTIVATED)
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

class ColorWindowMediator(Mediator):
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

    @mvcHandler(main.Gribouillis.DOC_ACTIVATE)
    def _on_activate_document(self, docproxy):
        brush = docproxy.document.brush
        self.viewComponent.set_color_rgb(brush.rgb)

class DocumentMediator(Mediator):
    """
    This class creates one instance for the application.
    This instance handles creation/destruction of document viewer components.
    This instance connects events from these components to its methods
    in a way to do actions on the model/controller.
    """

    NAME = "DocumentMediator"

    #### Private API ####

    def __init__(self, component):
        assert isinstance(component, Application)
        super(DocumentMediator, self).__init__(viewComponent=component)

        self.__docmap = {}
        self.__focused = None

        self.viewport_mediator = self.facade.retrieveMediator(DocViewPortMediator.NAME)

    def __len__(self):
        return len(self.__docmap)

    def _safe_close_viewer(self, win):
        #if not win.docproxy.document.empty and not win.confirm_close():
        #    return
        self.sendNotification(main.Gribouillis.DOC_DELETE, win.docproxy)

    ### UI events handlers ###

    def _on_focus_in_event(self, win, evt):
        self.__focused = win
        self.sendNotification(main.Gribouillis.DOC_ACTIVATE, win.docproxy)

    def _on_delete_event(self, win, evt):
        self.sendNotification(main.Gribouillis.DOC_DELETE, win.docproxy)

    def _on_menu_close_doc(self, win):
        self.sendNotification(main.Gribouillis.DOC_DELETE, win.docproxy)

    def _on_menu_quit(self, win):
        self.sendNotification(main.Gribouillis.QUIT)

    def _on_menu_new_doc(self, win):
        vo = model.vo.EmptyDocumentConfigVO('New document')
        if self.viewComponent.get_new_document_type(vo, parent=win):
            self.sendNotification(main.Gribouillis.NEW_DOCUMENT, vo)

    def _on_menu_load_doc(self, win):
        self._load_new_doc(win)

    def _on_menu_save_doc(self, win):
        filename = self.viewComponent.get_document_filename(parent=win, read=False)
        if filename:
            self.sendNotification(main.Gribouillis.DOC_SAVE, (win.docproxy, filename))
            win.set_doc_name(win.docproxy.document.name)

    def _on_menu_clear_layer(self, win):
        self.sendNotification(main.Gribouillis.DOC_LAYER_CLEAR,
                              model.vo.LayerCommandVO(win.docproxy, win.docproxy.active_layer),
                              type=utils.RECORDABLE_COMMAND)

    def _on_menu_undo(self, *a):
        self.sendNotification(main.Gribouillis.UNDO)

    def _on_menu_redo(self, *a):
        self.sendNotification(main.Gribouillis.REDO)

    def _on_menu_flush(self, *a):
        self.sendNotification(main.Gribouillis.FLUSH)

    def _on_menu_load_image_as_layer(self, *a):
        self.load_image_as_layer()

    ### notification handlers ###

    @mvcHandler(main.Gribouillis.DOC_SAVE_RESULT)
    def _on_save_document_result(self, *args):
        pass

    @mvcHandler(main.Gribouillis.DOC_ACTIVATED)
    def _on_activate_document(self, docproxy):
        win = self.get_win(docproxy)
        if win is not self.__focused:
            win.present()
            #Application().brusheditor.set_transient_for(win)

    @mvcHandler(main.Gribouillis.BRUSH_PROP_CHANGED)
    def _on_brush_prop_changed(self, brush, name):
        if name is 'color': return

        # synchronize storage brushes with drawing brushes.
        v = getattr(brush, name)
        for docproxy in self.__docmap.iterkeys():
            if docproxy.brush is brush:
                setattr(docproxy.document.brush, name, v)

        # For the cursor
        if name == 'radius_max':
            self.get_win(docproxy).set_cursor_radius(v)

    #### Public API ####

    def load_new_doc(self, win):
        filename = self.viewComponent.get_document_filename(parent=win)
        if filename:
            vo = model.vo.FileDocumentConfigVO(filename)
            self.sendNotification(main.Gribouillis.NEW_DOCUMENT, vo)

    def has_doc(self, docproxy):
        return docproxy in self.__docmap

    def get_win(self, docproxy):
        return self.__docmap[docproxy]

    def add_doc(self, docproxy, component):
        self.__docmap[docproxy] = component

        # Create document's ViewPort mediators
        for viewport in component.viewports:
            self.viewport_mediator.add_viewport(viewport)

        component.connect("delete-event", lambda wd, *a: self._safe_close_viewer(wd))
        component.connect("focus-in-event", self._on_focus_in_event)
        component.connect("menu_quit", self._on_menu_quit)
        component.connect("menu_new_doc", self._on_menu_new_doc)
        component.connect("menu_load_doc", self._on_menu_load_doc)
        component.connect("menu_close_doc", self._on_menu_close_doc)
        component.connect("menu_save_doc", self._on_menu_save_doc)
        component.connect("menu_undo", self._on_menu_undo)
        component.connect("menu_redo", self._on_menu_redo)
        component.connect("menu_flush", self._on_menu_flush)
        component.connect("menu_clear_layer", self._on_menu_clear_layer)
        component.connect("menu_load_image_as_layer", self._on_menu_load_image_as_layer)

    def del_doc(self, docproxy):
        component = self.__docmap.pop(docproxy)
        return component

    def load_image_as_layer(self):
        docproxy = model.DocumentProxy.get_active()
        dv = self._get_viewer(docproxy)
        filename = self.viewComponent.get_image_filename(parent=dv)
        if filename:
            self.sendNotification(main.Gribouillis.DOC_LOAD_IMAGE_AS_LAYER,
                                  model.vo.LayerConfigVO(docproxy=docproxy, filename=filename),
                                  type=utils.RECORDABLE_COMMAND)

class LayerManagerMediator(Mediator):
    NAME = "LayerManagerMediator"

    def __init__(self, component):
        assert isinstance(component, LayerManager)
        super(LayerManagerMediator, self).__init__(viewComponent=component)

        self.__docproxy = None

        component.btn['add'   ].connect('clicked', self._on_add_layer)
        component.btn['del'   ].connect('clicked', self._on_delete_layer)
        component.btn['up'    ].connect('clicked', self._on_up_layer)
        component.btn['down'  ].connect('clicked', self._on_down_layer)
        component.btn['top'   ].connect('clicked', self._on_top_layer)
        component.btn['bot'   ].connect('clicked', self._on_bottom_layer)
        component.btn['dup'   ].connect('clicked', self._on_duplicate_layer)
        component.btn['merge' ].connect('clicked', self._on_merge_layer)

        component.connect('layer-active-event', self._on_layer_active_event)
        component.connect('layer-name-changed', self._on_layer_name_changed)
        component.connect('layer-visibility-event', self._on_layer_visibility_event)
        component.connect('layer-operator-event', self._on_layer_operator_event)

    #### UI event handlers ####

    def _on_layer_active_event(self, w, layer):
        self.__docproxy.document.active = layer
        self.sendNotification(main.Gribouillis.DOC_LAYER_ACTIVATE, (self.__docproxy, layer))

    def _on_layer_name_changed(self, w, data):
        layer, name = data
        if layer.name != name:
            vo = model.vo.LayerCommandVO(docproxy=self.__docproxy, layer=layer, name=name)
            self.sendNotification(main.Gribouillis.DOC_LAYER_RENAME, vo, type=utils.RECORDABLE_COMMAND)

    def _on_layer_visibility_event(self, w, data):
        layer, state = data
        self.__docproxy.set_layer_visibility(layer, state)

    def _on_layer_operator_event(self, w, ctrl):
        layer = ctrl.layer
        layer.operator = ctrl.operator.get_active_text()
        self.sendNotification(main.Gribouillis.DOC_LAYER_UPDATED, (self.__docproxy, layer))

    def _on_add_layer(self, *a):
        pos = self.viewComponent.get_active_position() + 1
        vo = model.vo.LayerConfigVO(docproxy=self.__docproxy, pos=pos)
        self.sendNotification(main.Gribouillis.DOC_LAYER_ADD, vo, type=utils.RECORDABLE_COMMAND)

    def _on_delete_layer(self, *a):
        layer = self.viewComponent.active
        vo = model.vo.LayerCommandVO(docproxy=self.__docproxy, layer=layer)
        self.sendNotification(main.Gribouillis.DOC_LAYER_DEL, vo, type=utils.RECORDABLE_COMMAND)

    def _on_up_layer(self, *a):
        self.sendNotification(main.Gribouillis.DOC_LAYER_STACK_CHANGE,
                              (self.__docproxy, self.viewComponent.active, self.viewComponent.get_active_position()+1),
                              type=utils.RECORDABLE_COMMAND)

    def _on_down_layer(self, *a):
        self.sendNotification(main.Gribouillis.DOC_LAYER_STACK_CHANGE,
                              (self.__docproxy, self.viewComponent.active, self.viewComponent.get_active_position()-1),
                              type=utils.RECORDABLE_COMMAND)

    def _on_top_layer(self, *a):
        self.sendNotification(main.Gribouillis.DOC_LAYER_STACK_CHANGE,
                              (self.__docproxy, self.viewComponent.active, len(self.viewComponent)-1),
                              type=utils.RECORDABLE_COMMAND)

    def _on_bottom_layer(self, *a):
        self.sendNotification(main.Gribouillis.DOC_LAYER_STACK_CHANGE,
                              (self.__docproxy, self.viewComponent.active, 0),
                              type=utils.RECORDABLE_COMMAND)

    def _on_duplicate_layer(self, *a):
        layer = self.viewComponent.active
        vo = model.vo.LayerCommandVO(docproxy=self.__docproxy, layer=layer)
        self.sendNotification(main.Gribouillis.DOC_LAYER_DUP, vo, type=utils.RECORDABLE_COMMAND)

    def _on_merge_layer(self, *a):
        self.sendNotification(main.Gribouillis.DOC_LAYER_MERGE_DOWN,
                              (self.__docproxy, self.viewComponent.get_active_position()),
                              type=utils.RECORDABLE_COMMAND)

    #### notification handlers ####

    @mvcHandler(main.Gribouillis.DOC_DELETE)
    def _on_doc_delete(self, docproxy):
        if docproxy is self.__docproxy:
            self.viewComponent.clear()
            self.viewComponent.hide()
            self.__docproxy = None

    @mvcHandler(main.Gribouillis.NEW_DOCUMENT_RESULT)
    @mvcHandler(main.Gribouillis.DOC_UPDATED)
    def _on_new_doc_result(self, docproxy):
        if self.__docproxy is docproxy:
            self.viewComponent.set_layers(docproxy.layers, docproxy.document.active)

    @mvcHandler(main.Gribouillis.DOC_ACTIVATED)
    def _on_doc_activated(self, docproxy):
        if self.__docproxy is not docproxy:
            self.__docproxy = docproxy
            self.viewComponent.set_layers(docproxy.layers, docproxy.document.active)

    @mvcHandler(main.Gribouillis.DOC_LAYER_ADDED)
    def _on_doc_layer_added(self, docproxy, layer ,pos):
        if self.__docproxy is docproxy:
            self.viewComponent.add_layer(layer, pos)

    @mvcHandler(main.Gribouillis.DOC_LAYER_DELETED)
    def _on_doc_layer_deleted(self, docproxy, layer):
        if self.__docproxy is docproxy:
            self.viewComponent.del_layer(layer)

    @mvcHandler(main.Gribouillis.DOC_LAYER_STACK_CHANGED)
    def _on_doc_layer_moved(self, docproxy, layer, pos):
        if self.__docproxy is docproxy:
            self.viewComponent.move_layer(layer, pos)

    @mvcHandler(main.Gribouillis.DOC_LAYER_ACTIVATED)
    def _on_doc_layer_activated(self, docproxy, layer):
        if self.__docproxy is docproxy and layer is not self.viewComponent.active:
            self.viewComponent.active = layer

class DocViewPortMediator(Mediator):
    NAME = "DocViewPortMediator"

    #### Private API ####

    def __init__(self, component):
        assert isinstance(component, Application)
        super(DocViewPortMediator, self).__init__(viewComponent=component)
        self.__vpmap = {}
        self._vp = None # viewport with focus

    ### public API ####

    def add_viewport(self, viewport):
        dp = viewport.docproxy
        if dp in self.__vpmap:
            self.__vpmap[dp].append(viewport)
        else:
            self.__vpmap[dp] = [viewport]
        self._vp = viewport

    def reset_view(self, vp=None):
        if vp is None:
            vp = self._vp
        vp.reset_view()

    def _get_active(self):
        return self._vp

    def _set_active(self, vp):
        self._vp = vp

    active = property(fget=_get_active, fset=_set_active)

    ### notification handlers ###

    @mvcHandler(main.Gribouillis.DOC_UPDATED)
    @mvcHandler(main.Gribouillis.DOC_DIRTY)
    def _on_doc_dirty(self, docproxy, area=None):
        "Redraw given area. If area is None => full redraw."
        for vp in self.__vpmap[docproxy]:
            if area:
                vp.repaint(vp.get_view_area(*area))
            else:
                vp.repaint()

    @mvcHandler(main.Gribouillis.DOC_LAYER_ADDED)
    @mvcHandler(main.Gribouillis.DOC_LAYER_STACK_CHANGED)
    @mvcHandler(main.Gribouillis.DOC_LAYER_UPDATED)
    @mvcHandler(main.Gribouillis.DOC_LAYER_DELETED)
    def _on_layer_dirty(self, docproxy, layer, *args):
        "Specific layer repaint, limited to its area."
        if not layer.empty:
            area = layer.area
            for vp in self.__vpmap[docproxy]:
                vp.repaint(vp.get_view_area(*area))

# Actions
#

@action(_T('open document'))
def action_open_document(context, evt):
    docmediator = main.Gribouillis.getInstance().retrieveMediator("DocumentMediator")
    docmediator.load_new_doc(docmediator.get_win(evt.viewport.docproxy))
