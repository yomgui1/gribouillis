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

import pymui
import math
import os

import main
import model
import model.brush
import utils
import view.context as ctx
import view.operator as operator

from utils import _T, mvcHandler

from .app import Application
from .viewport import DocViewport
from .docviewer import DrawingRoot

import operators
import keymaps

del keymaps, operators

ctx.app = None # ApplicationMediator
ctx.tool = None # operators
ctx.eraser = None # BrushHouseWindowMediator
ctx.brush = None # BrushHouseWindowMediator
ctx.active_docproxy = None # ApplicationMediator
ctx.active_docwin = None # DocWindowBase


class GenericMediator(utils.Mediator):
    def show_dialog(self, title, msg):
        pymui.DoRequest(app=self.viewComponent, title=title, format=msg, gadgets='*_Ok')

    def show_error_dialog(self, msg):
        self.show_dialog(_T('Error'), msg)

    def show_warning_dialog(self, msg):
        self.show_dialog(_T('Warning'), msg)

    def show_info_dialog(self, msg):
        self.show_dialog(_T('Info'), msg)

    def evt2op(self, evt, name, *args):
        operator.execute(name, *args)


class ApplicationMediator(GenericMediator):
    """Application Mediator class.

    Responsible to receive and handle all notifications at Application level, like:
    - closing the application.
    - create new documents on demand.
    - etc
    """

    NAME = "ApplicationMediator"

    drawingroot_mediator = None
    layermgr_mediator = None

    # Private API

    def __init__(self, component):
        assert isinstance(component, app.Application)
        super(ApplicationMediator, self).__init__(viewComponent=component)

        ctx.app = component

        component.mediator = self

        component.menu_items['undo'].Bind(self.evt2op, "hist_undo")
        component.menu_items['redo'].Bind(self.evt2op, "hist_redo")
        component.menu_items['flush'].Bind(self.evt2op, "hist_flush")
        component.menu_items['new-doc'].Bind(self.new_document)
        component.menu_items['load-doc'].Bind(self.request_document)
        component.menu_items['save-doc'].Bind(self._menu_save_document)
        component.menu_items['save-as-doc'].Bind(self._menu_save_as_document)
        component.menu_items['clear_layer'].Bind(self.evt2op, "clear_active_layer")
        component.menu_items['load-background'].Bind(self._menu_load_background)
        component.menu_items['reset-view'].Bind(self.evt2op, "reset_active_viewport")
        component.menu_items['load-layer-image'].Bind(self._menu_load_image_as_layer)
        #component.menu_items['toggle-line-guide'].Bind(self._menu_line_guide)
        #component.menu_items['toggle-ellipse-guide'].Bind(self._menu_ellipse_guide)
        #component.menu_items['split-viewport-horiz'].Bind(self._menu_split_viewport_horiz)
        #component.menu_items['split-viewport-vert'].Bind(self._menu_split_viewport_vert)
        component.menu_items['color-lighten'].Bind(self._menu_color_lighten)
        component.menu_items['color-darken'].Bind(self._menu_color_darken)
        component.menu_items['color-saturate'].Bind(self._menu_color_saturate)
        component.menu_items['color-desaturate'].Bind(self._menu_color_desaturate)
        component.menu_items['toggle-rulers'].Bind(self.evt2op, "actdoc_toggle_rulers")
        component.menu_items['rotate-clockwise'].Bind(self.evt2op, "actvp_rotate", math.radians(20))
        component.menu_items['rotate-anticlockwise'].Bind(self.evt2op, "actvp_rotate", -math.radians(20))
        component.menu_items['mirror-x'].Bind(self.evt2op, "actvp_swap_x")
        component.menu_items['mirror-y'].Bind(self.evt2op, "actvp_swap_y")

        component.menu_items['quit'].Bind(self.quit)

        for item in component.windows['Splash'].lasts_bt:
            item.Notify('Pressed', self._on_last_sel, when=False, filename=item.path)

    def onRegister(self):
        self.drawingroot_mediator = DrawRootMediator(self.viewComponent)
        self.facade.registerMediator(self.drawingroot_mediator)

        self.layermgr_mediator = LayerMgrMediator(self.viewComponent.windows['LayerMgr'])
        self.facade.registerMediator(self.layermgr_mediator)

        self.facade.registerMediator(CommandsHistoryListMediator(self.viewComponent.windows['CmdHist']))
        #self.facade.registerMediator(ColorHarmoniesWindowMediator(self.viewComponent.windows['ColorMgr']))
        self.facade.registerMediator(BrushEditorWindowMediator(self.viewComponent.windows['BrushEditor']))
        self.facade.registerMediator(BrushHouseWindowMediator(self.viewComponent.windows['BrushHouse']))
        #self.facade.registerMediator(DocInfoMediator(self.viewComponent.docinfo))

        # Open a new empty document
        self.new_document()

    def get_document_filename(self, parent=None):
        return self.viewComponent.get_document_filename(parent)

    def _on_last_sel(self, evt, filename):
        evt.Source.WindowObject.object.Open = False
        self.open_document(filename)

    # menu items binding

    def _menu_save_document(self, evt):
        pass

    def _menu_save_as_document(self, evt):
        pass

    def _menu_clear_active_layer(self, evt):
        pass

    def _menu_load_background(self, evt):
        pass

    def _menu_load_image_as_layer(self, evt):
        self.layermgr_mediator.load_image_as_layer()

    def _menu_color_lighten(self, evt):
        model.DocumentProxy.get_active().multiply_color(1.0, 1.0, 1.1)

    def _menu_color_darken(self, evt):
        model.DocumentProxy.get_active().multiply_color(1.0, 1.0, 0.9)

    def _menu_color_saturate(self, evt):
        model.DocumentProxy.get_active().multiply_color(1.0, 1.1, 1.0)

    def _menu_color_desaturate(self, evt):
        model.DocumentProxy.get_active().multiply_color(1.0, 0.9, 1.0)

    # notification handlers

    @mvcHandler(main.QUIT)
    def _on_quit(self, note):
        # test here if some documents need to be saved
        if model.DocumentProxy.has_modified():
            res = pymui.DoRequest(self.viewComponent,
                                  gadgets="_Yes|*_No",
                                  title="Need confirmation",
                                  format="Some documents are not saved yet.\nSure to leave the application?")
            if not res:
                return
        self.viewComponent.Quit()

    @mvcHandler(main.DOC_ACTIVATED)
    def _on_doc_activated(self, docproxy):
        ctx.active_docproxy = docproxy

    # public API
    
    def quit(self):
        self.sendNotification(main.QUIT)

    def request_document(self, *a):
        filename = self.viewComponent.get_document_filename(parent=ctx.active_docwin, read=False)
        if filename:
            self.open_document(filename)

    def new_document(self, *a):
        vo = model.vo.EmptyDocumentConfigVO()
        if self.viewComponent.get_new_document_type(vo):
            try:
                docproxy = model.DocumentProxy.new_doc(vo)
            except:
                self.show_error_dialog(_T("Failed to create document"))

        self.drawingroot_mediator.add_docproxy(docproxy)

    def open_document(self, filename):
        vo = model.vo.FileDocumentConfigVO(filename)
        try:
            docproxy = model.DocumentProxy.new_doc(vo)
        except IOError:
            self.show_error_dialog(_T("Can't open file:\n%s" % filename))
            
        self.drawingroot_mediator.add_docproxy(docproxy)


class DrawRootMediator(GenericMediator):
    NAME = "DrawRootMediator"
    
    # private API

    def __init__(self, component):
        assert isinstance(component, Application)
        super(DrawRootMediator, self).__init__(viewComponent=component)

    # public API

    def register_viewport(self, viewport):
        self.facade.registerMediator(DocViewportMediator(viewport))

    def unregister_viewport(self, viewport):
        mediator = self.facade.retrieveMediator(hex(id(viewport)))
        self.facade.removeMediator(mediator)

    def add_docproxy(self, docproxy):
        root = DrawingRoot(docproxy, self.register_viewport, self.unregister_viewport)
        ctx.app.show_drawroot(root)


class DocViewportMediator(GenericMediator):
    NAME = "DocViewportMediator"

    # private API

    def __init__(self, component):
        assert isinstance(component, DocViewport)
        self.NAME = "%s_%x" % (DocViewportMediator.NAME, id(component))
        super(DocViewportMediator, self).__init__(viewComponent=component)

    def onRegister(self):
        self.viewComponent.mediator = self # FixMe: bad design

    def onRemove(self):
        self.viewComponent.mediator = None

    # notification handlers

    @mvcHandler(model.DocumentProxy.DOC_UPDATED)
    def _on_doc_updated(self, docproxy, area=None):
        vp = self.viewComponent
        if vp.docproxy is not docproxy: return
        if area:
            area = vp.get_view_area(*area)
        vp.repaint(area)

    @mvcHandler(model.LayerProxy.LAYER_DIRTY)
    def _on_layer_dirty(self, docproxy, layer, area=None):
        "Redraw given area. If area is None => full redraw."
        
        vp = self.viewComponent
        if vp.docproxy is not docproxy: return
        if area:
            area = vp.get_view_area(*area)
        vp.repaint(area)

    @mvcHandler(model.DocumentProxy.DOC_LAYER_ADDED)
    @mvcHandler(main.DOC_LAYER_STACK_CHANGED)
    @mvcHandler(main.DOC_LAYER_UPDATED)
    @mvcHandler(main.DOC_LAYER_DELETED)
    def _on_layer_repaint(self, docproxy, layer, *args):
        "Specific layer repaint, limited to its area."

        vp = self.viewComponent
        if vp.docproxy is not docproxy: return
        if not layer.empty:
            area = layer.area
            vp.repaint(vp.get_view_area(*area))

    @mvcHandler(model.BrushProxy.BRUSH_PROP_CHANGED)
    def _on_brush_prop_changed(self, brush, name):
        "Update viewport brush rendering"

        if name is 'radius_max':
            self.viewComponent.set_cursor_radius(getattr(brush, name))


class LayerMgrMediator(GenericMediator):
    NAME = "LayerMgrMediator"

    app_mediator = None

    def __init__(self, component):
        assert isinstance(component, layermgr.LayerMgr)
        super(LayerMgrMediator, self).__init__(LayerMgrMediator.NAME, component)

        self.__docproxy = None
        self.app_mediator = self.facade.retrieveMediator(ApplicationMediator.NAME)

        component.mediator = self
        component.btn['add'].Notify('Pressed', self.add_layer, when=False)
        component.btn['del'].Notify('Pressed', lambda *a: self.remove_active_layer(), when=False)
        component.btn['up'].Notify('Pressed', self._on_up_layer, when=False)
        component.btn['down'].Notify('Pressed', self._on_down_layer, when=False)
        component.btn['top'].Notify('Pressed', self._on_top_layer, when=False)
        component.btn['bottom'].Notify('Pressed', self._on_bottom_layer, when=False)
        component.btn['merge'].Notify('Pressed', self._on_merge_layer, when=False)
        component.btn['dup'].Notify('Pressed', self._on_dup_layer, when=False)

        component.opacity.Notify('Value', self._on_layer_opa_changed)
        component.blending.Notify('Active', self._on_layer_ope_changed)

        self._last_active = None
        component.Notify('ActiveObject', self._on_active_object)

    def _on_active_object(self, evt):
        # Permit to comfirm a in-modification layer name String object
        obj = evt.value.object
        if hasattr(obj, 'ctrl'):
            if self._last_active:
                ctrl = self._last_active.ctrl
                self._change_ctrl_name(ctrl, ctrl.name.Contents.contents)
            self._last_active = obj

    def _change_ctrl_name(self, ctrl, name):
        name = name.strip()
        if not name:
            ctrl.restore_name()
        else:
            self._on_layer_name_changed(ctrl.layer, name)

    def _on_layer_name_changed(self, layer, name):
        if layer.name != name:
            vo = model.vo.LayerCommandVO(docproxy=self.__docproxy, layer=layer, name=name)
            self.sendNotification(main.DOC_LAYER_RENAME, vo)

    def _on_dup_layer(self, e):
        layer = self.viewComponent.active
        vo = model.vo.LayerCommandVO(docproxy=self.__docproxy, layer=layer)
        self.sendNotification(main.DOC_LAYER_DUP, vo)

    def _on_up_layer(self, e):
        self.sendNotification(main.DOC_LAYER_STACK_CHANGE,
                              (self.__docproxy, self.viewComponent.active, self.viewComponent.get_active_position() + 1))

    def _on_down_layer(self, e):
        self.sendNotification(main.DOC_LAYER_STACK_CHANGE,
                              (self.__docproxy, self.viewComponent.active, self.viewComponent.get_active_position() - 1))

    def _on_top_layer(self, e):
        self.sendNotification(main.DOC_LAYER_STACK_CHANGE,
                              (self.__docproxy, self.viewComponent.active, len(self.viewComponent) - 1))

    def _on_bottom_layer(self, e):
        self.sendNotification(main.DOC_LAYER_STACK_CHANGE,
                              (self.__docproxy, self.viewComponent.active, 0))

    def _on_change_name(self, evt, ctrl):
        self._change_ctrl_name(ctrl, evt.value.contents)

    def _on_layer_activated(self, evt, ctrl):
        if evt.value.value:
            self.sendNotification(main.DOC_LAYER_ACTIVATE, (self.__docproxy, ctrl.layer))
        elif ctrl.layer == self.__docproxy.active_layer:
            ctrl.activeBt.Selected = True  # re-active the gadget

    def _on_layer_ope_changed(self, evt):
        dp = self.__docproxy
        layer = dp.active_layer
        layer.operator = model.Layer.OPERATORS_LIST[evt.value.value]
        self.sendNotification(main.DOC_LAYER_UPDATED, (dp, layer))

    def _on_layer_vis_changed(self, evt, ctrl):
        visible = evt.value.value
        self.__docproxy.set_layer_visibility(ctrl.layer, visible)

    def _on_layer_opa_changed(self, evt):
        dp = self.__docproxy
        dp.set_layer_opacity(dp.active_layer, evt.value.value / 100.)

    def _on_merge_layer(self, e):
        self.sendNotification(main.DOC_LAYER_MERGE_DOWN,
                              (self.__docproxy, self.viewComponent.get_active_position()))

    def _add_notifications(self, ctrl):
        #ctrl.preview.Notify('Pressed', self._on_layer_activated, when=True,
        #                    win=self.viewComponent, docproxy=self.__docproxy, layer=ctrl.layer)

        ctrl.name.Notify('Acknowledge', self._on_change_name, ctrl)
        ctrl.activeBt.Notify('Selected', self._on_layer_activated, ctrl=ctrl)
        ctrl.visBt.Notify('Selected', self._on_layer_vis_changed, ctrl=ctrl)

    #### notification handlers ####

    @mvcHandler(main.DOC_DELETE)
    def _on_doc_delete(self, docproxy):
        if docproxy is self.__docproxy:
            self.viewComponent.clear()
            self.viewComponent.Open = False
            self.__docproxy = None

    @mvcHandler(model.DocumentProxy.DOC_ADDED)
    @mvcHandler(model.DocumentProxy.DOC_UPDATED)
    def _on_new_doc_result(self, docproxy):
        if self.__docproxy is docproxy:
            map(self._add_notifications, self.viewComponent.set_layers(docproxy.document.layers, docproxy.document.active))

    @mvcHandler(main.DOC_ACTIVATED)
    def _on_doc_activated(self, docproxy):
        if self.__docproxy is not docproxy:
            self.__docproxy = docproxy
            map(self._add_notifications, self.viewComponent.set_layers(docproxy.document.layers, docproxy.active_layer))

    @mvcHandler(model.DocumentProxy.DOC_LAYER_ADDED)
    def _on_doc_layer_added(self, docproxy, layer, pos):
        if self.__docproxy is docproxy:
            self._add_notifications(self.viewComponent.add_layer(layer, pos))

    @mvcHandler(main.DOC_LAYER_DELETED)
    def _on_doc_layer_deleted(self, docproxy, layer):
        if self.__docproxy is docproxy:
            self.viewComponent.del_layer(layer)

    @mvcHandler(main.DOC_LAYER_STACK_CHANGED)
    def _on_doc_layer_stack_changed(self, docproxy, layer, pos):
        if self.__docproxy is docproxy:
            self.viewComponent.move_layer(layer, pos)

    @mvcHandler(main.DOC_LAYER_ACTIVATED)
    def _on_doc_layer_activated(self, docproxy, layer):
        if self.__docproxy is docproxy and layer is not self.viewComponent.active:
            self.viewComponent.active = layer

    @mvcHandler(main.DOC_LAYER_UPDATED)
    def _on_doc_layer_updated(self, docproxy, layer):
        if self.__docproxy is docproxy:
            self.viewComponent.update_layer(layer)

    #### Public API ####

    def add_layer(self, *a):
        vo = model.vo.LayerConfigVO(docproxy=self.__docproxy, pos=self.viewComponent.get_active_position() + 1)
        self.sendNotification(main.DOC_LAYER_ADD, vo)

    def remove_active_layer(self):
        vo = model.vo.LayerCommandVO(docproxy=self.__docproxy, layer=self.viewComponent.active)
        self.sendNotification(main.DOC_LAYER_DEL, vo)

    def load_image_as_layer(self):
        docproxy = model.DocumentProxy.get_active()
        filename = self.app_mediator.viewComponent.get_image_filename(parent=ctx.active_docwin)
        if filename:
            self.sendNotification(main.DOC_LOAD_IMAGE_AS_LAYER,
                                  model.vo.LayerConfigVO(docproxy=docproxy,
                                                         filename=filename,
                                                         pos=self.viewComponent.get_active_position() + 1))

    def exchange_layers(self, one, two):
        self.sendNotification(main.DOC_LAYER_STACK_CHANGE,
                              (self.__docproxy, two, self.__docproxy.document.get_layer_index(one)))

    def show_layers(self, *layers):
        dp = self.__docproxy
        for layer in dp.document.layers:
            dp.set_layer_visibility(layer, layer in layers)

    def hide_layers(self, *layers):
        dp = self.__docproxy
        for layer in dp.document.layers:
            dp.set_layer_visibility(layer, layer not in layers)

    def lock_layers(self, *layers):
        dp = self.__docproxy
        for layer in dp.document.layers:
            layer.locked = layer in layers
            self.viewComponent.update_layer(layer)

    def unlock_layers(self, *layers):
        dp = self.__docproxy
        for layer in dp.document.layers:
            layer.locked = layer not in layers
            self.viewComponent.update_layer(layer)


class BrushEditorWindowMediator(GenericMediator):
    NAME = "BrushEditorWindowMediator"

    brushproxy = None

    #### Private API ####

    def __init__(self, component):
        assert isinstance(component, brusheditor.BrushEditorWindow)
        super(BrushEditorWindowMediator, self).__init__(viewComponent=component)

        self.brushproxy = self.facade.retrieveProxy(model.BrushProxy.NAME)

        component.namebt.Notify('Contents', self._on_brush_name_changed)
        component.on_value_changed_cb = self.brushproxy.set_attr

    def _on_brush_name_changed(self, evt):
        self.brushproxy.set_attr(ctx.brush, 'name', evt.value.contents)

    ### notification handlers ###

    @mvcHandler(main.USE_BRUSH)
    def _on_activate_document(self, brush):
        self.viewComponent.brush = brush

    @mvcHandler(model.BrushProxy.BRUSH_PROP_CHANGED)
    def _on_doc_brush_prop_changed(self, brush, name):
        if self.viewComponent.brush is brush:
            self.viewComponent.brush_changed_prop(name, getattr(brush, name))


class CommandsHistoryListMediator(GenericMediator):
    NAME = "CommandsHistoryListMediator"

    #### Private API ####

    def __init__(self, component):
        assert isinstance(component, cmdhistoric.CommandsHistoryList)
        super(CommandsHistoryListMediator, self).__init__(CommandsHistoryListMediator.NAME, component)

        self.__cur_hp = None

        component.btn_undo.Notify('Pressed', self.evt2op, "hist_undo", when=False)
        component.btn_redo.Notify('Pressed', self.evt2op, "hist_redo", when=False)
        component.btn_flush.Notify('Pressed', self.evt2op, "hist_flush", when=False)

    ### notification handlers ###

    @mvcHandler(main.DOC_ACTIVATED)
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


class ColorHarmoniesWindowMediator(GenericMediator):
    NAME = "ColorHarmoniesWindowMediator"

    #### Private API ####

    __mode = 'idle'
    __brush = None

    def __init__(self, component):
        assert isinstance(component, colorharmonies.ColorHarmoniesWindow)
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
                if self.__mode == 'idle':
                    return
                widget.enable_mouse_motion(False)
                self.__mode = 'idle'
                hsv = widget.hsv
            else:
                if not evt.InObject:
                    return
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

            self.viewComponent.hsv = hsv
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

    @mvcHandler(main.DOC_ACTIVATED)
    def _on_activate_document(self, docproxy):
        self.__brush = docproxy.document.brush
        self.viewComponent.hsv = self.__brush.hsv

    @mvcHandler(model.BrushProxy.BRUSH_PROP_CHANGED)
    def _on_brush_prop_changed(self, brush, name):
        if self.__brush is brush and name == 'color':
            self.viewComponent.hsv = brush.hsv


class BrushHouseWindowMediator(GenericMediator):
    NAME = "BrushHouseWindowMediator"

    #### Private API ####

    def __init__(self, component):
        assert isinstance(component, brushhouse.BrushHouseWindow)
        super(BrushHouseWindowMediator, self).__init__(viewComponent=component)

        eraser = None
        self.brush_proxy = self.facade.retrieveProxy(model.BrushProxy.NAME)

        component.set_current_cb(self._on_brush_selected)
        component.set_eraser_set_cb(self._on_eraser_set)

        # Load saved brushes
        l =  model.brush.Brush.load_brushes()
        assert l, RuntimeError("no brushes!")
        for brush in l:
            component.add_brush(brush, name=brush.group)
            if brush.eraser:
                eraser = brush
            if not eraser:
                if brush.erase == 0:
                    eraser = brush
        component.active_brush = l[0]

        # No eraser brush set?
        # use last brush found with erase = 0
        # else use last brush
        if eraser is None:
            eraser = l[-1]
        self._on_eraser_set(eraser)

    def _on_brush_selected(self, brush):
        ctx.brush = brush
        self.sendNotification(main.USE_BRUSH, brush)

    def _on_eraser_set(self, brush):
        if ctx.eraser:
            self.brush_proxy.set_attr(ctx.eraser, 'eraser', False)
        self.brush_proxy.set_attr(brush, 'eraser', True)

    ### notification handlers ###

    @mvcHandler(main.USE_BRUSH)
    def _on_use_brush(self, brush):
        if ctx.brush is not brush:
            self.viewComponent.active_brush = brush

    @mvcHandler(model.BrushProxy.BRUSH_PROP_CHANGED)
    def _on_brush_prop_changed(self, brush, name):
        if name == 'name':
            if brush is self.viewComponent.active_brush:
                self.viewComponent.refresh_active()
        elif name == 'eraser' and brush.eraser:
            ctx.eraser = brush


class DocInfoMediator(GenericMediator):
    NAME = "DocInfoMediator"

    def __init__(self, component):
        assert isinstance(component, docinfo.DocInfoWindow)
        super(DocInfoMediator, self).__init__(DocInfoMediator.NAME, component)

    #### notification handlers ####

    @mvcHandler(main.DOC_DELETE)
    def _on_doc_delete(self, docproxy):
        if docproxy is self.viewComponent.docproxy:
            del self.viewComponent.docproxy

    @mvcHandler(main.DOC_ACTIVATED)
    def _on_doc_activated(self, docproxy):
        if docproxy is not self.viewComponent.docproxy:
            self.viewComponent.docproxy = docproxy

    @mvcHandler(model.DocumentProxy.DOC_UPDATED)
    def _on_doc_updated(self, docproxy):
        if docproxy is self.viewComponent.docproxy:
            self.viewComponent.docproxy = docproxy
