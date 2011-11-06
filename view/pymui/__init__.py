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

import pymui, math

import main, model, utils

from utils import Mediator, mvcHandler, RECORDABLE_COMMAND, _T, resolve_path
from model import vo
from model.prefs import prefs

from app import Application
from docviewer import DocWindow
from brusheditor import BrushEditorWindow
from layermgr import LayerMgr
from cmdhistoric import CommandsHistoryList
from colorharmonies import ColorHarmoniesWindow
from brushhouse import BrushHouseWindow
from docinfo import DocInfoWindow

IECODE_LBUTTON = 0x68

import commands
del commands

class DialogMediator(Mediator):
    NAME = 'DialogMediator'

    def show_dialog(self, title, msg):
        pymui.DoRequest(app=self.viewComponent, title=title, format=msg, gadgets='*_Ok')

    #### notification handlers ####

    @mvcHandler(main.Gribouillis.SHOW_ERROR_DIALOG)
    def on_show_error(self, msg):
        self.show_dialog('', msg)

    @mvcHandler(main.Gribouillis.SHOW_WARNING_DIALOG)
    def on_show_warning(self, msg):
        self.show_dialog('', msg)

    @mvcHandler(main.Gribouillis.SHOW_INFO_DIALOG)
    def on_show_info(self, msg):
        self.show_dialog('', msg)

class ApplicationMediator(Mediator):
    """Application Mediator class.

    Responsible to receive and handle all notifications at Application level, like:
    - closing the application.
    - create new documents on demand.
    - etc
    """

    NAME = "ApplicationMediator"

    document_mediator = None
    viewport_mediator = None
    layermgr_mediator = None
    
    #### Private API ####

    def __init__(self, component):
        assert isinstance(component, Application)
        super(ApplicationMediator, self).__init__(ApplicationMediator.NAME, component)
        
        component.mediator = self
        
        component.menu_items['undo'].Bind(self._menu_undo)
        component.menu_items['redo'].Bind(self._menu_redo)
        component.menu_items['flush'].Bind(self._menu_flush)
        component.menu_items['new-doc'].Bind(self.new_document)
        component.menu_items['load-doc'].Bind(self.load_document)
        component.menu_items['save-doc'].Bind(self._menu_save_document)
        component.menu_items['save-as-doc'].Bind(self._menu_save_as_document)
        component.menu_items['clear_layer'].Bind(self._menu_clear_active_layer)
        component.menu_items['load-background'].Bind(self._menu_load_background)
        component.menu_items['reset-view'].Bind(self._menu_reset_view)
        component.menu_items['load-layer-image'].Bind(self._menu_load_image_as_layer)
        component.menu_items['toggle-line-guide'].Bind(self._menu_line_guide)
        component.menu_items['toggle-ellipse-guide'].Bind(self._menu_ellipse_guide)
        #component.menu_items['split-viewport-horiz'].Bind(self._menu_split_viewport_horiz)
        #component.menu_items['split-viewport-vert'].Bind(self._menu_split_viewport_vert)
        component.menu_items['color-lighten'].Bind(self._menu_color_lighten)
        component.menu_items['color-darken'].Bind(self._menu_color_darken)
        component.menu_items['color-saturate'].Bind(self._menu_color_saturate)
        component.menu_items['color-desaturate'].Bind(self._menu_color_desaturate)
        component.menu_items['toggle-rulers'].Bind(self._menu_toggle_rulers)
        component.menu_items['rotate-90-clockwise'].Bind(self._menu_rotate_90_clockwise)
        component.menu_items['rotate-90-anticlockwise'].Bind(self._menu_rotate_90_anticlockwise)
        component.menu_items['mirror-x'].Bind(self._menu_mirror_x)
        component.menu_items['mirror-y'].Bind(self._menu_mirror_y)
        
        component.menu_items['quit'].Bind(self.quit)
        
        for item in component.splash.lasts_bt:
            item.Notify('Pressed', self._on_last_sel, when=False, filename=item.path)

    def onRegister(self):
        self.facade.registerMediator(DialogMediator(self.viewComponent))
        
        self.viewport_mediator = DocViewPortMediator(self.viewComponent)
        self.facade.registerMediator(self.viewport_mediator)

        self.document_mediator = DocumentMediator(self.viewComponent)
        self.facade.registerMediator(self.document_mediator)
        
        self.layermgr_mediator = LayerMgrMediator(self.viewComponent.layermgr)
        self.facade.registerMediator(self.layermgr_mediator)
        
        self.facade.registerMediator(CommandsHistoryListMediator(self.viewComponent.cmdhist))
        self.facade.registerMediator(ColorHarmoniesWindowMediator(self.viewComponent.colorhrm))
        self.facade.registerMediator(BrushEditorWindowMediator(self.viewComponent.brusheditor))
        self.facade.registerMediator(BrushHouseWindowMediator(self.viewComponent.brushhouse))
        self.facade.registerMediator(DocInfoMediator(self.viewComponent.docinfo))
        
    def get_document_filename(self, parent=None):
        return self.viewComponent.get_document_filename(parent)

    def add_docproxy(self, docproxy):
        # Create and attach a window to view/edit the document
        component = DocWindow(self.viewComponent.ctx, docproxy)
        self.viewComponent.AddChild(component)
        
        # Register it to document mediator
        self.document_mediator.add_doc(docproxy, component)
        
        component.Open = True
        component.RootObject.contents.Redraw() # needed to force rulers to be redraw

    def rem_docproxy(self, docproxy):
        # Keep this order!
        win = self.document_mediator.get_win(docproxy)
        win.Open = False
        self.viewComponent.RemChild(win)
        self.document_mediator.del_doc(docproxy)
        del win

        # Close the application if no document remains
        if not len(self.document_mediator):
            self.viewComponent.quit()

    def _on_last_sel(self, evt, filename):
        evt.Source.WindowObject.contents.Open = False
        vo = model.vo.FileDocumentConfigVO(filename)
        self.sendNotification(main.Gribouillis.NEW_DOCUMENT, vo)
           
    ## Menu items binding
    
    def _menu_save_document(self, evt):
        self.document_mediator.save_document()
        
    def _menu_save_as_document(self, evt):
        self.document_mediator.save_as_document()
        
    def _menu_undo(self, evt):
        self.sendNotification(main.Gribouillis.UNDO)

    def _menu_redo(self, evt):
        self.sendNotification(main.Gribouillis.REDO)

    def _menu_flush(self, evt):
        self.sendNotification(main.Gribouillis.FLUSH)

    def _menu_clear_active_layer(self, evt):
        self.document_mediator.clear_active_layer()

    def _menu_load_background(self, evt):
        self.document_mediator.load_background()

    def _menu_reset_view(self, evt):
        self.viewport_mediator.view_reset(self.viewport_mediator.active)
        
    def _menu_load_image_as_layer(self, evt):
        self.layermgr_mediator.load_image_as_layer()
        
    def _menu_line_guide(self, evt):
        self.viewport_mediator.toggle_guide(self.viewport_mediator.active, 'line')

    def _menu_ellipse_guide(self, evt):
        self.viewport_mediator.toggle_guide(self.viewport_mediator.active, 'ellipse')
   
    def _menu_color_lighten(self, evt):
        model.DocumentProxy.get_active().multiply_color(1.0, 1.0, 1.1)
        
    def _menu_color_darken(self, evt):
        model.DocumentProxy.get_active().multiply_color(1.0, 1.0, 0.9)
        
    def _menu_color_saturate(self, evt):
        model.DocumentProxy.get_active().multiply_color(1.0, 1.1, 1.0)
        
    def _menu_color_desaturate(self, evt):
        model.DocumentProxy.get_active().multiply_color(1.0, 0.9, 1.0)

    def _menu_split_viewport_horiz(self, evt): pass
    def _menu_split_viewport_vert(self, evt): pass

    def _menu_toggle_rulers(self, evt):
        self.document_mediator.toggle_rulers()
    
    def _menu_rotate_90_clockwise(self, evt):
        self.viewport_mediator.rotate(self.viewport_mediator.active, math.radians(90))
        
    def _menu_rotate_90_anticlockwise(self, evt):
        self.viewport_mediator.rotate(self.viewport_mediator.active, math.radians(-90))
    
    def _menu_mirror_x(self, evt):
        self.viewport_mediator.view_swap_x(self.viewport_mediator.active)

    def _menu_mirror_y(self, evt):
        self.viewport_mediator.view_swap_y(self.viewport_mediator.active)
        
    ### notification handlers ###
    
    @mvcHandler(main.Gribouillis.NEW_DOCUMENT_RESULT)
    def _new_document_result(self, docproxy):
        if not docproxy:
            self.sendNotification(main.Gribouillis.SHOW_ERROR_DIALOG,
                                  "Failed to create document.")
            return
        self.add_docproxy(docproxy)
        
    @mvcHandler(main.Gribouillis.DOC_ACTIVATED)
    def _activate_document(self, docproxy):
        if not self.document_mediator.has_doc(docproxy):
            self.add_docproxy(docproxy)
        else:    
            self.viewComponent.on_doc_activated(docproxy)

    @mvcHandler(main.Gribouillis.QUIT)
    def _quit(self, note):
        self.quit()
            
    #### Public API ####
    
    def quit(self, *a):
        # test here if some documents need to be saved
        if any(map(lambda dp: dp.document.modified and not dp.document.empty, self.document_mediator.proxies)):
            res = pymui.DoRequest(self.viewComponent,
                                  gadgets= "_Yes|*_No",
                                  title  = "Need confirmation",
                                  format = "Some documents are not saved yet.\nSure to leave the application?")
            if not res: return
        self.viewComponent.quit()
        
    def new_document(self, *a):
        # TODO: ask for document type
        vo = model.vo.EmptyDocumentConfigVO()
        if self.viewComponent.get_new_document_type(vo):
            self.sendNotification(main.Gribouillis.NEW_DOCUMENT, vo)

    def load_document(self, *a):
        win = self.document_mediator.get_win(model.DocumentProxy.get_active())
        filename = self.viewComponent.get_document_filename(parent=win, read=False)
        if filename:
            vo = model.vo.FileDocumentConfigVO(filename)
            self.sendNotification(main.Gribouillis.NEW_DOCUMENT, vo)

class DocumentMediator(Mediator):
    NAME = "DocumentMediator"
    
    viewport_mediator = None

    #### Private API ####

    def __init__(self, component):
        assert isinstance(component, Application)
        super(DocumentMediator, self).__init__(DocumentMediator.NAME, component)
        self.__docmap = {}
        self.viewport_mediator = self.facade.retrieveMediator(DocViewPortMediator.NAME)
        
    def __len__(self):
        return len(self.__docmap)

    ### UI events handlers ###
    
    def _on_win_close_req(self, evt):
        win = evt.Source
        doc = win.docproxy.document
        if doc.modified and not doc.empty and not win.confirm_close():
            return
            
        self.sendNotification(main.Gribouillis.DOC_DELETE, win.docproxy)

    def _on_win_activated(self, evt):
        self.sendNotification(main.Gribouillis.DOC_ACTIVATE, evt.Source.docproxy)

    ### notification handlers ###

    @mvcHandler(main.Gribouillis.DOC_SAVE_RESULT)
    def _on_save_document_result(self, docproxy, result):
        pass

    @mvcHandler(main.Gribouillis.DOC_ACTIVATED)
    def _on_activate_document(self, docproxy):
        win = self.get_win(docproxy)
        if not win.Activate:
            win.NNSet('Activate', True)
        win.set_doc_name(docproxy.docname)
        win.ToFront()
        win.set_cursor_radius(docproxy.document.brush.radius_max)

    @mvcHandler(main.Gribouillis.BRUSH_PROP_CHANGED)
    def _on_doc_brush_prop_changed(self, brush, name):
        if name == 'color': return
        
        # synchronize storage brushes with drawing brushes.
        v = getattr(brush, name)
        for docproxy in self.__docmap.iterkeys():
            if docproxy.brush is brush:
                setattr(docproxy.document.brush, name, v)

        # For the cursor
        if name == 'radius_max':
            self.get_win(docproxy).set_cursor_radius(v)

    @mvcHandler('pymui-toggle-erase')
    def _toggle_erase(self, docproxy):
        # Don't change the recorded brush setting, but a state of the drawing brush
        docproxy.drawbrush.erase = 1.0 - docproxy.drawbrush.erase

    #### Public API ####
    
    def save_document(self, docproxy=None):
        docproxy = docproxy or model.DocumentProxy.get_active()
        if not docproxy.document.filename:
            self.save_as_document()
        self.sendNotification(main.Gribouillis.DOC_SAVE, (docproxy, docproxy.docname))

    def save_as_document(self, docproxy=None):
        docproxy = docproxy or model.DocumentProxy.get_active()
        
        if docproxy.document.empty:
            self.sendNotification(main.Gribouillis.SHOW_ERROR_DIALOG, _T("Empty document!") % filename)
            return
            
        win = self.get_win(docproxy)
        filename = self.viewComponent.get_document_filename(parent=win, read=False)
        if filename:
            self.sendNotification(main.Gribouillis.DOC_SAVE, (docproxy, filename))
            
    def has_doc(self, docproxy):
        return docproxy in self.__docmap
        
    def get_win(self, docproxy):
        return self.__docmap[docproxy]
    
    def add_doc(self, docproxy, component):
        """add_doc(docproxy, component) -> None
        
        Register a new document view component with its display areas.
        Attach the given document model to the document view.
        """
        
        self.__docmap[docproxy] = component
        map(self.viewport_mediator.add_viewport, component.disp_areas)
        
        component.Notify('CloseRequest', self._on_win_close_req, when=True)
        component.Notify('Activate', self._on_win_activated, when=True)
        
    def del_doc(self, docproxy):
        component = self.__docmap.pop(docproxy)
        map(self.viewport_mediator.remove_viewport, component.disp_areas)
        if len(self.__docmap):
            docproxy = self.__docmap.keys()[-1]
            self.sendNotification(main.Gribouillis.DOC_ACTIVATE, docproxy)
        return component
    
    def load_background(self):
        docproxy = model.DocumentProxy.get_active()
        filename = self.viewComponent.get_image_filename(parent=self.get_win(docproxy), drawer=resolve_path(prefs['backgrounds-path']))
        if filename:
            try:
                docproxy.set_background(filename)
            except:
                self.sendNotification(main.Gribouillis.SHOW_ERROR_DIALOG,
                                      "Failed to load background image %s.\n" % filename +
                                      "(Note: Only PNG files are supported as background).")
                raise

    def set_background_rgb(self, rgb):
        docproxy = model.DocumentProxy.get_active()
        win = self.get_win(docproxy)
        win.set_background_rgb(rgb)

    def clear_active_layer(self, docproxy=None):
        docproxy = docproxy or model.DocumentProxy.get_active()
        docproxy.clear_layer(docproxy.active_layer)
        
    def refresh_all(self):
        for win in self.__docmap.itervalues():
            win.RootObject.contents.Redraw()
            
    def toggle_rulers(self, docproxy=None):
        win = self.get_win(docproxy or model.DocumentProxy.get_active())
        win.toggle_rulers()
        
    @property
    def proxies(self):
        return self.__docmap.iterkeys()

class LayerMgrMediator(Mediator):
    NAME = "LayerMgrMediator"

    app_mediator = None
    doc_mediator = None
    
    def __init__(self, component):
        assert isinstance(component, LayerMgr)
        super(LayerMgrMediator, self).__init__(LayerMgrMediator.NAME, component)

        self.__docproxy = None
        self.doc_mediator = self.facade.retrieveMediator(DocumentMediator.NAME)
        self.app_mediator = self.facade.retrieveMediator(ApplicationMediator.NAME)

        component.btn['add'].Notify('Pressed', self.add_layer, when=False)
        component.btn['del'].Notify('Pressed', lambda *a: self.remove_active_layer(), when=False)
        component.btn['up'].Notify('Pressed', self._on_up_layer, when=False)
        component.btn['down'].Notify('Pressed', self._on_down_layer, when=False)
        component.btn['top'].Notify('Pressed', self._on_top_layer, when=False)
        component.btn['bottom'].Notify('Pressed', self._on_bottom_layer, when=False)
        component.btn['merge'].Notify('Pressed', self._on_merge_layer, when=False)
        component.btn['dup'].Notify('Pressed', self._on_dup_layer, when=False)

    def _on_layer_name_changed(self, layer, name):
        if layer.name != name:
            vo = model.vo.LayerCommandVO(docproxy=self.__docproxy, layer=layer, name=name)
            self.sendNotification(main.Gribouillis.DOC_LAYER_RENAME, vo, type=utils.RECORDABLE_COMMAND)
        
    def _on_dup_layer(self, e):
        layer = self.viewComponent.active
        vo = model.vo.LayerCommandVO(docproxy=self.__docproxy, layer=layer)
        self.sendNotification(main.Gribouillis.DOC_LAYER_DUP, vo, type=utils.RECORDABLE_COMMAND)

    def _on_up_layer(self, e):
        self.sendNotification(main.Gribouillis.DOC_LAYER_STACK_CHANGE,
                              (self.__docproxy, self.viewComponent.active, self.viewComponent.get_active_position()+1),
                              type=utils.RECORDABLE_COMMAND)

    def _on_down_layer(self, e):
        self.sendNotification(main.Gribouillis.DOC_LAYER_STACK_CHANGE,
                              (self.__docproxy, self.viewComponent.active, self.viewComponent.get_active_position()-1),
                              type=utils.RECORDABLE_COMMAND)

    def _on_top_layer(self, e):
        self.sendNotification(main.Gribouillis.DOC_LAYER_STACK_CHANGE,
                              (self.__docproxy, self.viewComponent.active, len(self.viewComponent)-1),
                              type=utils.RECORDABLE_COMMAND)

    def _on_bottom_layer(self, e):
        self.sendNotification(main.Gribouillis.DOC_LAYER_STACK_CHANGE,
                              (self.__docproxy, self.viewComponent.active, 0),
                              type=utils.RECORDABLE_COMMAND)

    def _on_change_name(self, evt, ctrl):
        name = evt.value.contents.strip()
        if not name:
            ctrl.restore_name()
        else:
            self._on_layer_name_changed(ctrl.layer, name)

    def _on_layer_activated(self, evt, win, docproxy, layer):
        win.set_active(layer)
        self.sendNotification(main.Gribouillis.DOC_LAYER_ACTIVATE, (docproxy, layer))

    def _on_layer_ope_changed(self, evt, docproxy, layer):
        layer.operator = model.Layer.OPERATORS_LIST[evt.value.value]
        self.sendNotification(main.Gribouillis.DOC_LAYER_UPDATED, (docproxy, layer))

    def _on_layer_vis_changed(self, evt, docproxy, layer):
        self.__docproxy.set_layer_visibility(layer, evt.value.value)
        
    def _on_layer_opa_changed(self, evt, docproxy, layer):
        self.__docproxy.set_layer_opacity(layer, evt.value.value / 100.)
        
    def _on_merge_layer(self, e):
        self.sendNotification(main.Gribouillis.DOC_LAYER_MERGE_DOWN,
                              (self.__docproxy, self.viewComponent.get_active_position()),
                              type=utils.RECORDABLE_COMMAND)

    def _add_notifications(self, ctrl):
        ctrl.name.Notify('Acknowledge', self._on_change_name, ctrl)
        ctrl.actBt.Notify('Pressed', self._on_layer_activated, when=True,
                          win=self.viewComponent, docproxy=self.__docproxy, layer=ctrl.layer)
        ctrl.opebt.Notify('Active', self._on_layer_ope_changed, docproxy=self.__docproxy, layer=ctrl.layer)
        ctrl.vis.Notify('Selected', self._on_layer_vis_changed, docproxy=self.__docproxy, layer=ctrl.layer)
        ctrl.opaSl.Notify('Value', self._on_layer_opa_changed, docproxy=self.__docproxy, layer=ctrl.layer)

    #### notification handlers ####

    @mvcHandler(main.Gribouillis.DOC_DELETE)
    def _on_doc_delete(self, docproxy):
        if docproxy is self.__docproxy:
            self.viewComponent.clear()
            self.viewComponent.Open = False
            self.__docproxy = None

    @mvcHandler(main.Gribouillis.NEW_DOCUMENT_RESULT)
    @mvcHandler(main.Gribouillis.DOC_UPDATED)
    def _on_new_doc_result(self, docproxy):
        if self.__docproxy is docproxy:
            map(self._add_notifications, self.viewComponent.set_layers(docproxy.document.layers, docproxy.document.active))

    @mvcHandler(main.Gribouillis.DOC_ACTIVATED)
    def _on_doc_activated(self, docproxy):
        if self.__docproxy is not docproxy:
            self.__docproxy = docproxy
            map(self._add_notifications, self.viewComponent.set_layers(docproxy.document.layers, docproxy.active_layer))

    @mvcHandler(main.Gribouillis.DOC_LAYER_ADDED)
    def _on_doc_layer_added(self, docproxy, layer, pos):
        if self.__docproxy is docproxy:
            self._add_notifications(self.viewComponent.add_layer(layer, pos))
            
    @mvcHandler(main.Gribouillis.DOC_LAYER_DELETED)
    def _on_doc_layer_deleted(self, docproxy, layer):
        if self.__docproxy is docproxy:
            self.viewComponent.del_layer(layer)
            
    @mvcHandler(main.Gribouillis.DOC_LAYER_STACK_CHANGED)
    def _on_doc_layer_stack_changed(self, docproxy, layer, pos):
        if self.__docproxy is docproxy:
            self.viewComponent.move_layer(layer, pos)
            
    @mvcHandler(main.Gribouillis.DOC_LAYER_ACTIVATED)
    def _on_doc_layer_activated(self, docproxy, layer):
        if self.__docproxy is docproxy and layer is not self.viewComponent.active:
            self.viewComponent.active = layer
            
    @mvcHandler(main.Gribouillis.DOC_LAYER_UPDATED)
    def _on_doc_layer_updated(self, docproxy, layer):
        if self.__docproxy is docproxy and layer is not self.viewComponent.active:
            self.viewComponent.update_layer(layer)

    #### Public API ####
    
    def add_layer(self, *a):
        vo = model.vo.LayerConfigVO(docproxy=self.__docproxy, pos=self.viewComponent.get_active_position()+1)
        self.sendNotification(main.Gribouillis.DOC_LAYER_ADD, vo, type=utils.RECORDABLE_COMMAND)

    def remove_active_layer(self):
        vo = model.vo.LayerCommandVO(docproxy=self.__docproxy, layer=self.viewComponent.active)
        self.sendNotification(main.Gribouillis.DOC_LAYER_DEL, vo, type=utils.RECORDABLE_COMMAND)
        
    def load_image_as_layer(self):
        docproxy = model.DocumentProxy.get_active()
        win = self.doc_mediator.get_win(docproxy)
        filename = self.app_mediator.viewComponent.get_image_filename(parent=win)
        if filename:
            self.sendNotification(main.Gribouillis.DOC_LOAD_IMAGE_AS_LAYER,
                                  model.vo.LayerConfigVO(docproxy=docproxy, filename=filename, pos=self.viewComponent.get_active_position()+1),
                                  type=RECORDABLE_COMMAND)

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

    @mvcHandler(main.Gribouillis.BRUSH_PROP_CHANGED)
    def _on_doc_brush_prop_changed(self, brush, name):
        if self.viewComponent.brush is not brush: return
        self.viewComponent.brush_changed_prop(name, getattr(brush, name))

class CommandsHistoryListMediator(Mediator):
    NAME = "CommandsHistoryListMediator"

    #### Private API ####

    def __init__(self, component):
        assert isinstance(component, CommandsHistoryList)
        super(CommandsHistoryListMediator, self).__init__(CommandsHistoryListMediator.NAME, component)

        self.__cur_hp = None

        component.btn_undo.Notify('Pressed', self._on_undo, when=False)
        component.btn_redo.Notify('Pressed', self._on_redo, when=False)
        component.btn_flush.Notify('Pressed', self._on_flush, when=False)

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
        hp = utils.CommandsHistoryProxy.get_active()
        if hp != self.__cur_hp:
            self.__cur_hp = hp
            self.viewComponent.update(hp)

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

class ColorHarmoniesWindowMediator(Mediator):
    NAME = "ColorHarmoniesWindowMediator"

    #### Private API ####

    __mode = 'idle'
    __brush = None

    def __init__(self, component):
        assert isinstance(component, ColorHarmoniesWindow)
        super(ColorHarmoniesWindowMediator, self).__init__(ColorHarmoniesWindowMediator.NAME, component)

        self.appmediator = self.facade.retrieveMediator(ApplicationMediator.NAME)
        self.docmediator = self.facade.retrieveMediator(DocumentMediator.NAME)

        component.colorwheel.add_watcher('mouse-button', self._on_mouse_button, component.colorwheel)
        component.colorwheel.add_watcher('mouse-motion', self._on_mouse_motion, component.colorwheel)
        component.widgets['AsBgBt'].Notify('Pressed', self._on_color_as_bg, when=False)
        component.set_hsv_callback(self._set_hsv)
        
    def _set_hsv(self, hsv):
        model.DocumentProxy.get_active().set_brush_color_hsv(*hsv)

    def _on_mouse_button(self, evt, widget):
        rawkey = evt.RawKey
        if rawkey == IECODE_LBUTTON:
            if evt.Up:
                if self.__mode == 'idle': return
                widget.enable_mouse_motion(False)
                self.__mode = 'idle'
                hsv = widget.hsv
            else:
                if not evt.InObject: return
                pos = widget.mouse_to_user(evt.MouseX, evt.MouseY)
                if widget.hit_hue(*pos):
                    hsv = widget.set_hue_pos(*pos)
                    widget.enable_mouse_motion(True)
                    self.__mode = 'hue-move'
                elif widget.hit_square(*pos):
                    hsv = widget.set_square_pos(*pos)
                    widget.enable_mouse_motion(True)
                    self.__mode = 'square-move'
                else:
                    return
                    #hsv = widget.hit_harmony(*pos)
                    #if hsv is None: return

            self.viewComponent.hev = hsv
            model.DocumentProxy.get_active().set_brush_color_hsv(*hsv)
            return pymui.MUI_EventHandlerRC_Eat

    def _on_mouse_motion(self, evt, widget):
        pos = widget.mouse_to_user(evt.MouseX, evt.MouseY)
        if self.__mode == 'hue-move':
            hsv = widget.set_hue_pos(*pos)
        else:
            hsv = widget.set_square_pos(*pos)
        self.viewComponent.hsv = hsv
        model.DocumentProxy.get_active().set_brush_color_hsv(*hsv)
        return pymui.MUI_EventHandlerRC_Eat

    def _on_color_as_bg(self, evt):
        self.docmediator.set_background_rgb(self.viewComponent.rgb)

    ### notification handlers ###

    @mvcHandler(main.Gribouillis.DOC_ACTIVATE)
    def _on_activate_document(self, docproxy):
        self.__brush = docproxy.document.brush
        self.viewComponent.hsv = self.__brush.hsv

    @mvcHandler(main.Gribouillis.BRUSH_PROP_CHANGED)
    def _on_brush_prop_changed(self, brush, name):
        if self.__brush is brush and name == 'color':
            self.viewComponent.hsv = brush.hsv

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

class DocViewPortMediator(Mediator):
    NAME = "DocViewPortMediator"

    active = None # Viewport components set this value to themself at focus
    
    #### Private API ####

    def __init__(self, component):
        assert isinstance(component, Application)
        super(DocViewPortMediator, self).__init__(viewComponent=component)
        self.__vpmap = {}
        
    ### public API ####
    
    def add_viewport(self, viewport):
        dp = viewport.docproxy
        if dp in self.__vpmap:
            self.__vpmap[dp].append(viewport)
        else:
            self.__vpmap[dp] = [viewport]
        viewport.mediator = self
        
    def remove_viewport(self, viewport):
        dp = viewport.docproxy
        self.__vpmap[dp].remove(viewport)
        if not self.__vpmap[dp]:
            del self.__vpmap[dp]
        del viewport.mediator
        #viewport.remove()

    def split(self, viewport, horiz=False):
        da1, da2 = viewport.split(horiz)
        self.add_viewport(da1)
        if da2:
            self.add_viewport(da2)
        
    def toggle_guide(self, viewport, guide):
        if viewport is None:
            return
        viewport.toggle_guide(guide)

    def view_reset(self, viewport):
        if viewport is None:
            return
        viewport.reset_transforms()
        viewport._win.set_scale(viewport.scale)
    
    def view_translate_reset(self, viewport):
        if viewport is None:
            return
        viewport.reset_translation()
    
    def view_scale_reset(self, viewport, center):
        if viewport is None:
            return
        viewport.reset_scaling()
        viewport._win.set_scale(viewport.scale)
    
    def view_rotate_reset(self, viewport, center):
        if viewport is None:
            return
        viewport.reset_rotation()
    
    def view_scale_up(self, viewport, center):
        if viewport is None:
            return
        viewport.scale_up(*center)
        viewport._win.set_scale(viewport.scale)

    def view_scale_down(self, viewport, center):
        if viewport is None:
            return
        viewport.scale_down(*center)
        viewport._win.set_scale(viewport.scale)
    
    def view_swap_x(self, viewport, x=None):
        if viewport is None:
            return
        viewport.swap_x(x if x is not None else viewport.width/2)
    
    def view_swap_y(self, viewport, y=None):
        if viewport is None:
            return
        viewport.swap_y(y if y is not None else viewport.height/2)
        
    def rotate(self, viewport, angle):
        if viewport is None:
            return
        viewport.rotate(angle)

    def enable_passepartout(self, viewport, state):
        if viewport is None:
            return
        viewport.enable_passepartout(state)
        
    ### notification handlers ###
        
    @mvcHandler(main.Gribouillis.DOC_UPDATED)
    @mvcHandler(main.Gribouillis.DOC_DIRTY)
    def _on_doc_dirty(self, docproxy, area=None):
        """Redraw given area (surface coordinates).
        
        If area is None => full redraw.
        """
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

class DocInfoMediator(Mediator):
    NAME = "DocInfoMediator"
    
    def __init__(self, component):
        assert isinstance(component, DocInfoWindow)
        super(DocInfoMediator, self).__init__(DocInfoMediator.NAME, component)

    #### notification handlers ####

    @mvcHandler(main.Gribouillis.DOC_DELETE)
    def _on_doc_delete(self, docproxy):
        if docproxy is self.viewComponent.docproxy:
            del self.viewComponent.docproxy

    @mvcHandler(main.Gribouillis.DOC_ACTIVATED)
    def _on_doc_activated(self, docproxy):
        if docproxy is not self.viewComponent.docproxy:
            self.viewComponent.docproxy = docproxy
            
    @mvcHandler(main.Gribouillis.DOC_UPDATED)
    def _on_doc_updated(self, docproxy):
        if docproxy is self.viewComponent.docproxy:
            self.viewComponent.docproxy = docproxy
