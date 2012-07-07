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
import cairo
import os
import traceback as tb

import model, view, main, utils
import const

from utils import _T, resolve_path
from model import devices
from model import prefs

import eventparser

__all__ = [ 'LayerMgr', 'LayerCtrl' ]

VIRT_GROUP_SPACING = 2
PREVIEW_HEIGHT = 48

ALT_QUALIFIERS = const.IEQUALIFIER_LALT | const.IEQUALIFIER_RALT

class LayerPreview(pymui.Area):
    _MCC_ = True
    
    width = height = None
    _active = False
    _clip = None
    _draw = False
    
    def __init__(self):
        super(LayerPreview, self).__init__(FillArea=False, InputMode='Toggle', Draggable=True)
        self._brush = model.brush.DrawableBrush()
        self._brush.rgb = 0, 0, 0
        self._brush.radius_min = .9
        self._brush.radius_max = 1.2
        self._brush.opacity_min = .8
        self._brush.opacity_max = 1
        self._brush.opa_comp = 1.2
        self._brush.hardness = .2
        self._brush.motion_track = 0.5
        self._brush.spacing = .25
        
        self._ev = pymui.EventHandler()
        self._device = devices.InputDevice()
        
    @pymui.muimethod(pymui.MUIM_AskMinMax)
    def _mcc_AskMinMax(self, msg):
        msg.DoSuper()
        mmi = msg.MinMaxInfo.contents
        
        mmi.MaxWidth = mmi.MinWidth = 160
        mmi.MaxHeight = mmi.MinHeight = PREVIEW_HEIGHT
        
    @pymui.muimethod(pymui.MUIM_Draw)
    def _mcc_Draw(self, msg):
        msg.DoSuper()
        if not (msg.flags.value & pymui.MADF_DRAWOBJECT): return
        
        w = self.MWidth
        h = self.MHeight
        
        if self.width != w or self.height != h:
            self.width = w
            self.height = h
            self._surface = model.surface.BoundedPlainSurface(model._pixbuf.FORMAT_ARGB15X, w, h)
            self._drawbuf = self._surface.get_rawbuf()
            self._drawbuf.clear_white()
            self._shadow = model._pixbuf.Pixbuf(model._pixbuf.FORMAT_ARGB8, w, h)
            self._repaint_shadow()
            self._renderbuf = model._pixbuf.Pixbuf(model._pixbuf.FORMAT_ARGB8_NOA, w, h)
            self._renderbuf.clear()
        
        self.AddClipping()
        try:
            if self._clip is None:
                x = y = 0
            else:
                x, y, w, h = self._clip
            self._clip = None
            
            self._drawbuf.blit(self._renderbuf, x, y, x, y, w, h)
            if not self._active:
                self._shadow.compose(self._renderbuf, x, y, x, y, w, h)
            self._rp.Blit8(self._renderbuf, self._renderbuf.stride, self.MLeft + x, self.MTop + y, w, h, x, y)
        finally:
            self.RemoveClipping()

    @pymui.muimethod(pymui.MUIM_Setup)
    def MCC_Setup(self, msg):
        self._ev.install(self, pymui.IDCMP_RAWKEY | pymui.IDCMP_MOUSEBUTTONS)
        return msg.DoSuper()

    @pymui.muimethod(pymui.MUIM_Cleanup)
    def MCC_Cleanup(self, msg):
        self._ev.uninstall()
        return msg.DoSuper()

    @pymui.muimethod(pymui.MUIM_HandleEvent)
    def MCC_HandleEvent(self, msg):
        try:
            ev = self._ev
            ev.readmsg(msg)
            cl = ev.Class
            if cl == pymui.IDCMP_MOUSEBUTTONS or cl == pymui.IDCMP_RAWKEY:
                if ev.Up:
                    event = eventparser.KeyReleasedEvent(ev, self)
                else:
                    event = eventparser.KeyPressedEvent(ev, self)
                
                if event.get_key() == 'mouse_leftpress':
                    if not ev.Up and ev.InObject:
                        if self.active:
                            self.start_draw(event)
                            return pymui.MUI_EventHandlerRC_Eat
                    elif self._draw:
                        self.stop_draw(event)
                        return pymui.MUI_EventHandlerRC_Eat
                        
                elif ev.InObject:
                    if event.get_key() == 'delete':
                        self.erase()
                        return pymui.MUI_EventHandlerRC_Eat
                
            elif cl == pymui.IDCMP_MOUSEMOVE:
                event = eventparser.CursorMoveEvent(ev, self)
                self.draw(event)
                return pymui.MUI_EventHandlerRC_Eat
                
        except:
            tb.print_exc(limit=20)

    def get_device_state(self, event):
        state = devices.DeviceState()
        
        state.time = event.get_time()

        # Get raw device position
        state.cpos = event.get_cursor_position()
        state.vpos = state.cpos
        state.spos = state.cpos
        
        # Tablet stuffs
        state.pressure = event.get_pressure()
        state.xtilt = event.get_cursor_xtilt()
        state.ytilt = event.get_cursor_ytilt()
        
        self._device.add_state(state)
        return state

    def enable_motion_events(self, state=True):
        self._ev.uninstall()
        if state:
            idcmp = self._ev.idcmp | pymui.IDCMP_MOUSEMOVE
        else:
            idcmp = self._ev.idcmp & ~pymui.IDCMP_MOUSEMOVE
        self._ev.install(self, idcmp)
        
    def start_draw(self, event):
        self._draw = True
        self.enable_motion_events(True)
        self._brush.start(self._surface, self.get_device_state(event))
        
    def stop_draw(self, event):
        self._draw = False
        self.enable_motion_events(False)
        self._brush.stop()
        self.Redraw()
        
    def draw(self, event):
        self._clip = self._brush.draw_stroke(self.get_device_state(event))
        self.Redraw()

    def erase(self):
        self._drawbuf.clear_white()
        self.Redraw()

    def _repaint_shadow(self):
        self._shadow.clear()
        cr = cairo.Context(cairo.ImageSurface.create_for_data(self._shadow, cairo.FORMAT_ARGB32, self.width, self.height))
        gradient = cairo.LinearGradient(0, 0, 0, self.height-1)
        gradient.add_color_stop_rgba(0.0, 0, 0, 0, 1)
        gradient.add_color_stop_rgba(0.5, 0, 0, 0, 0)
        gradient.add_color_stop_rgba(1.0, 0, 0, 0, 1)
        cr.set_source(gradient)
        cr.paint()

    def set_active(self, state):
        state = bool(state)
        if self._active != state:
            self._active = state
            self.Redraw()
            
    active = property(fget=lambda self: self._active, fset=set_active)

class LayerCtrl(pymui.Group):
    _MCC_ = True

    _alt = False
    
    def __init__(self, layer, mediator):
        super(LayerCtrl, self).__init__(Horiz=True, Draggable=False, SameHeight=True)
        
        self._ev = pymui.EventHandler()

        self.mediator = mediator
        self.layer = layer
        #self.preview = LayerPreview()
        self.name = pymui.String(layer.name.encode('latin1', 'replace'),
                                 Frame='Button', Background='StringBack',
                                 CycleChain=True, FrameDynamic=True)
        self.name.ctrl = self
        
        image_path = os.path.join(resolve_path(prefs['view-icons-path']), "updown.png")
        handler = pymui.Dtpic(image_path, Frame='None', InputMode='RelVerify',
                              ShowSelState=False, LightenOnMouse=True,
                              ShortHelp=_T("Click and drag this icon to re-order the layer in stack"))
        self.activeBt = pymui.Dtpic(self._get_active_image(0), Frame='None', InputMode='Toggle',
                                    Selected=False,
                                    ShowSelState=False, LightenOnMouse=True,
                                    ShortHelp=_T("Active layer has this checkmark selected."))
        self.visBt = pymui.Dtpic(self._get_visible_image(layer.visible), Frame='None', InputMode='Toggle',
                                 Selected=layer.visible,
                                 ShowSelState=False, LightenOnMouse=True,
                                 ShortHelp=_T("Layer visibility status.\nPress ALT key to toggle also all others layers"))
        self.lockBt = pymui.Dtpic(self._get_lock_image(layer.locked), Frame='None', InputMode='Toggle',
                                  Selected=layer.locked,
                                  ShowSelState=False, LightenOnMouse=True,
                                  ShortHelp=_T("Layer locked status (write protection).\nPress ALT key to toggle also all others layers"))
        grp = pymui.HGroup(Child=(handler, self.activeBt, self.name, self.visBt, self.lockBt))
        self.AddChild(pymui.HGroup(Child=[pymui.HSpace(6), grp, pymui.HSpace(6)]))
        
        handler.Notify('Pressed', lambda *a: self.DoDrag(0x80000000, 0x80000000, 0), when=True)
        
        self.activeBt.Notify('Selected', self._on_active_sel)
        self.visBt.Notify('Selected', self._on_visible_sel)
        self.lockBt.Notify('Selected', self._on_lock_sel)

    @pymui.muimethod(pymui.MUIM_DragQuery)
    def _mcc_DragQuery(self, msg):
        return (pymui.MUIV_DragQuery_Accept if msg.obj.object is not self else pymui.MUIV_DragQuery_Refuse)

    @pymui.muimethod(pymui.MUIM_DragDrop)
    def _mcc_DragDrop(self, msg):
        other = msg.obj.object
        self.mediator.exchange_layers(self.layer, other.layer)

    @pymui.muimethod(pymui.MUIM_Setup)
    def _mcc_Setup(self, msg):
        self._ev.install(self, pymui.IDCMP_RAWKEY)
        return msg.DoSuper()

    @pymui.muimethod(pymui.MUIM_Cleanup)
    def _mcc_Cleanup(self, msg):
        self._ev.uninstall()
        return msg.DoSuper()
        
    @pymui.muimethod(pymui.MUIM_HandleEvent)
    def _mcc_HandleEvent(self, msg):
        try:
            self._ev.readmsg(msg)
            self._alt = self._ev.Qualifier & ALT_QUALIFIERS != 0
        except:
            tb.print_exc(limit=20)
    
    def _get_act_object(self):
        return self.WindowObject.object.MouseObject.object
        
    def _get_lock_image(self, sel):
        return os.path.join(resolve_path(prefs['view-icons-path']), ("lock.png" if sel else "unlock.png"))
        
    def _get_visible_image(self, sel):
        return os.path.join(resolve_path(prefs['view-icons-path']), ("power_on.png" if sel else "power_off.png"))

    def _get_active_image(self, sel):
        return os.path.join(resolve_path(prefs['view-icons-path']), ("edit.png" if sel else "blue.png"))

    def _on_lock_sel(self, evt):
        sel = evt.value.value
        self.lockBt.Name = self._get_lock_image(sel)
        
        if self._alt and self._get_act_object() is self.lockBt:
            if sel:
                self.mediator.lock_layers(self.layer)
            else:
                self.mediator.unlock_layers(self.layer)
        else:
            self.layer.locked = sel
        
    def _on_visible_sel(self, evt):
        sel = evt.value.value
        self.visBt.Name = self._get_visible_image(sel)
        
        if self._alt and self._get_act_object() is self.visBt:
            if sel:
                self.mediator.show_layers(self.layer)
            else:
                self.mediator.hide_layers(self.layer)
        
    def _on_active_sel(self, evt):
        sel = evt.value.value
        self.activeBt.Name = self._get_active_image(sel)

    def set_active(self, v):
        self.activeBt.Selected = v
        
    def update(self):
        self.name.NNSet('Contents', self.layer.name.encode('latin1', 'replace'))
        self.visBt.Selected = self.layer.visible
        self.lockBt.Selected = self.layer.locked

    def restore_name(self):
        pass

class LayerMgr(pymui.Window):
    def __init__(self, name):
        super(LayerMgr, self).__init__(ID='LayerMgr', Title=name, CloseOnReq=True)
        self.name = name
        
        self.__layctrllist = []
        self._active = None

        top = pymui.VGroup()
        self.RootObject = top

        self.layctrl_grp = pymui.VGroupV(Frame='Virtual', Spacing=VIRT_GROUP_SPACING)
        self.__space = pymui.VSpace(0)
        self.layctrl_grp.AddTail(self.__space)

        # Layer info group
        layerinfo = pymui.ColGroup(2)
        layerinfo.AddChild(pymui.Label(_T("Blending")+':'))
        self.blending = pymui.Cycle(model.Layer.OPERATORS_LIST, CycleChain=True, ShortHelp=_T("Set layer's blending mode"))
        layerinfo.AddChild(self.blending)
        layerinfo.AddChild(pymui.Label(_T("Opacity")+':'))
        self.opacity = pymui.Slider(Value=100, Format='%u%%', CycleChain=True, ShortHelp=_T("Set layer's opacity value"))
        layerinfo.AddChild(self.opacity)

        # Layer management buttons
        btn_grp = pymui.ColGroup(4)
        self.btn = {}
        for name, label in [('add',  'Add'),
                            ('del',  'Del'),
                            ('dup',  'Copy'),
                            ('merge', 'Merge'),
                            ('up',   'Up'),
                            ('down', 'Down'),
                            ('top',   'Top'),
                            ('bottom', 'Bottom'),
                            ]:
            o = self.btn[name] = pymui.SimpleButton(label)
            btn_grp.AddChild(o)

        sc_gp = pymui.Scrollgroup(Contents=self.layctrl_grp, FreeHoriz=False)
        self.__vertbar = sc_gp.VertBar.object
        top.AddChild(sc_gp)
        top.AddChild(pymui.HBar(0))
        top.AddChild(layerinfo)
        top.AddChild(pymui.HBar(0))
        top.AddChild(pymui.HCenter(btn_grp))

    def __len__(self):
        return len(self.__layctrllist)

    def _set_active_ctrl(self, ctrl):
        if ctrl is self._active: return
        ctrl.set_active(True)
        if self._active:
            self._active.set_active(False)
        self._active = ctrl

    def clear(self):
        self.layctrl_grp.InitChange()
        for ctrl in self.__layctrllist:
            self.layctrl_grp.Remove(ctrl)
        self.layctrl_grp.ExitChange()
        self.__layctrllist = []

    def add_layer_ctrl(self, layer, pos=0):
        ctrl = LayerCtrl(layer, self.mediator)
        self.layctrl_grp.AddHead(ctrl)
        self.layctrl_grp.MoveMember(ctrl, len(self.__layctrllist)-pos)
        self.__layctrllist.insert(pos, ctrl)
        return ctrl

    def set_layers(self, layers, active=None):
        self.layctrl_grp.InitChange()
        self.clear()
        ctrls = []
        for i, layer in enumerate(layers):
            ctrls.append(self.add_layer_ctrl(layer, i))
        self.layctrl_grp.MoveMember(self.__space, -1)
        self.layctrl_grp.ExitChange()

        self.active = active
        return ctrls
        
    def add_layer(self, layer, pos):
        self.layctrl_grp.InitChange()
        ctrl = self.add_layer_ctrl(layer, pos)
        self.layctrl_grp.ExitChange()
        self.active = layer
        return ctrl
        
    def del_layer(self, layer):
        for ctrl in self.__layctrllist:
            if ctrl.layer is layer:
                self.layctrl_grp.InitChange()
                self.layctrl_grp.Remove(ctrl)
                self.layctrl_grp.ExitChange()
                self.__layctrllist.remove(ctrl)
                return

    def update_layer(self, layer):
        for ctrl in self.__layctrllist:
            if ctrl.layer is layer:
                ctrl.update()
                if ctrl == self._active:
                    self.opacity.NNSet('Value', int(layer.opacity * 100))
                    self.blending.NNSet('Active', model.Layer.OPERATORS_LIST.index(layer.operator))
                return

    def move_layer(self, layer, pos):
        for ctrl in self.__layctrllist:
            if ctrl.layer is layer:
                self.__layctrllist.remove(ctrl)
                self.__layctrllist.insert(pos, ctrl)
                self.layctrl_grp.InitChange()
                self.layctrl_grp.MoveMember(ctrl, len(self.__layctrllist)-pos-1)
                self.layctrl_grp.ExitChange()
                self.btn['merge'].Disabled = layer is self.__layctrllist[0].layer
                return

    def get_active_position(self):
        return self.__layctrllist.index(self._active)

    def get_active(self):
        return self._active.layer

    def set_active(self, layer):
        for ctrl in self.__layctrllist:
            if (not layer) or ctrl.layer is layer:
                self._set_active_ctrl(ctrl)

                self.opacity.NNSet('Value', int(layer.opacity * 100))
                self.blending.NNSet('Active', model.Layer.OPERATORS_LIST.index(layer.operator))
                
                self.btn['merge'].Disabled = layer is self.__layctrllist[0].layer
                return

    active = property(fget=get_active, fset=set_active)
