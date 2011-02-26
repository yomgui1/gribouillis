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

from pymui import *

import model, view, main, utils

from utils import mvcHandler

__all__ = [ 'LayerMgr', 'LayerCtrl', 'LayerMgrMediator' ]

VIRT_GROUP_SPACING = 2
IECODE_LBUTTON   = 0x68

class DropHBar(Rectangle):
    _MCC_ = True

    def __init__(self, space=1):
        Rectangle.__init__(self, HBar=True,
                           InnerLeft=6, InnerRight=6,
                           InnerTop=space + VIRT_GROUP_SPACING, InnerBottom=space,
                           VertWeight=0)

    @muimethod(MUIM_DragQuery)
    def _mcc_DragQuery(self, msg):
        return (MUIV_DragQuery_Accept if isinstance(msg.obj.value, LayerCtrl) else MUIV_DragQuery_Refuse)


class LayerCtrl(Group):
    _MCC_ = True
    STATE_COLORS = { False: '0', True: '2:00000000,44444444,99999999' }

    def __init__(self, layer):
        super(LayerCtrl, self).__init__(Horiz=True, Frame='Group', InnerSpacing=0, Draggable=False,
                                        Background=LayerCtrl.STATE_COLORS[False],
                                        SameHeight=True)

        self.layer = layer

        self.actBt = VSpace(0, Frame='Group', InputMode='RelVerify', ShowSelState=False, CycleChain=True)
        self.vis = CheckMark(layer.visible)
        self.vis.CycleChain = True
        self.ShortHelp = "Click here to activate"
        self.opaSl = Numericbutton(Value=int(layer.opacity*100), Format='%u%%', CycleChain=True, ShortHelp="Opacity")
        self.opebt = Cycle(model.Layer.OPERATORS_LIST, CycleChain=True, Weight=0)
        self.opebt.Active = list(model.Layer.OPERATORS_LIST).index(layer.operator)

        self.name = String(Contents=layer.name, Frame='String', Background=0, CycleChain=True)

        self.AddChild(self.actBt)
        self.AddChild(self.opaSl)
        self.AddChild(self.opebt)
        self.AddChild(self.vis)
        self.AddChild(self.name)

    @muimethod(MUIM_DragQuery)
    def _mcc_DragQuery(self, msg):
        return (MUIV_DragQuery_Accept if msg.obj.value is not self else MUIV_DragQuery_Refuse)

    def set_active(self, v):
        self.Background = LayerCtrl.STATE_COLORS[v]

    def update(self):
        self.vis.Selected = self.layer.visible
        self.name.NNSet('Contents', self.layer.name)
        self.opaSl.NNSet('Value', int(self.layer.opacity*100))

    def restore_name(self):
        self.name.Contents = self.layer.name


class LayerMgr(Window):
    def __init__(self):
        super(LayerMgr, self).__init__(ID='LayerMgr', Title='Layers', CloseOnReq=True)

        self.__layctrllist = []
        self._active = None

        top = VGroup()
        self.RootObject = top

        self.layctrl_grp = VGroupV(InnerSpacing=0, Frame='Virtual', Spacing=VIRT_GROUP_SPACING)
        self.__space = VSpace(0)
        #bar = DropHBar(2)
        #self.layctrl_grp.AddHead(bar)
        self.layctrl_grp.AddTail(self.__space)

        # Layer management buttons
        btn_grp = HGroup()
        self.btn = {}
        for name, label in [('add',  'Add'),
                            ('del',  'Del'),
                            ('up',   'Up'),
                            ('down', 'Down'),
                            ('top',   'Top'),
                            ('bottom', 'Bottom'),
                            ('dup',  'Copy'),
                            ('merge', 'Merge'),
                            ]:
            o = self.btn[name] = SimpleButton(label)
            btn_grp.AddChild(o)

        sc_gp = Scrollgroup(Contents=self.layctrl_grp, FreeHoriz=False)
        self.__vertbar = sc_gp.VertBar.contents
        top.AddChild(sc_gp)
        top.AddChild(HBar(0))
        top.AddChild(HCenter(btn_grp))

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
        ctrl = LayerCtrl(layer)
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
                self.active = layer
                return

    def update_layer(self, layer):
        for ctrl in self.__layctrllist:
            if ctrl.layer is layer:
                ctrl.update()
                return

    def move_layer(self, layer, pos):
        for ctrl in self.__layctrllist:
            if ctrl.layer is layer:
                self.__layctrllist.remove(ctrl)
                self.__layctrllist.insert(pos, ctrl)
                self.layctrl_grp.InitChange()
                self.layctrl_grp.MoveMember(ctrl, len(self.__layctrllist)-pos-1)
                self.layctrl_grp.ExitChange()
                return

    def get_active_position(self):
        return self.__layctrllist.index(self._active)

    def get_active(self):
        return self._active.layer

    def set_active(self, layer):
        for ctrl in self.__layctrllist:
            if (not layer) or ctrl.layer is layer:
                self._set_active_ctrl(ctrl)

                # set the first seen ctrl in the list on this active
                n = self.__vertbar._get(MUIA_Prop_Entries)
                self.__vertbar._set(MUIA_Prop_First, int(n*self.__layctrllist.index(ctrl)/len(self.__layctrllist)))

                return

    active = property(fget=get_active, fset=set_active)


class LayerMgrMediator(utils.Mediator):
    NAME = "LayerMgrMediator"

    def __init__(self, component):
        assert isinstance(component, LayerMgr)
        super(LayerMgrMediator, self).__init__(LayerMgrMediator.NAME, component)

        self.__docproxy = None

        component.btn['add'].Notify('Pressed', self._on_add_layer, when=False)
        component.btn['del'].Notify('Pressed', self._on_delete_layer, when=False)
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

    def _on_add_layer(self, e):
        vo = model.vo.LayerConfigVO(docproxy=self.__docproxy, pos=self.viewComponent.get_active_position()+1)
        self.sendNotification(main.Gribouillis.DOC_LAYER_ADD, vo, type=utils.RECORDABLE_COMMAND)

    def _on_delete_layer(self, e):
        layer = self.viewComponent.active
        vo = model.vo.LayerCommandVO(docproxy=self.__docproxy, layer=layer)
        self.sendNotification(main.Gribouillis.DOC_LAYER_DEL, vo, type=utils.RECORDABLE_COMMAND)

    def _on_dup_layer(self, e):
        layer = self.viewComponent.active
        vo = model.vo.LayerCommandVO(docproxy=self.__docproxy, layer=layer)
        self.sendNotification(main.Gribouillis.DOC_LAYER_DUP, vo, type=utils.RECORDABLE_COMMAND)

    def _on_up_layer(self, e):
        self.sendNotification(main.Gribouillis.DOC_LAYER_MOVE,
                              (self.__docproxy, self.viewComponent.active, self.viewComponent.get_active_position()+1),
                              type=utils.RECORDABLE_COMMAND)

    def _on_down_layer(self, e):
        self.sendNotification(main.Gribouillis.DOC_LAYER_MOVE,
                              (self.__docproxy, self.viewComponent.active, self.viewComponent.get_active_position()-1),
                              type=utils.RECORDABLE_COMMAND)

    def _on_top_layer(self, e):
        self.sendNotification(main.Gribouillis.DOC_LAYER_MOVE,
                              (self.__docproxy, self.viewComponent.active, len(self.viewComponent)-1),
                              type=utils.RECORDABLE_COMMAND)

    def _on_bottom_layer(self, e):
        self.sendNotification(main.Gribouillis.DOC_LAYER_MOVE,
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
            map(self._add_notifications, self.viewComponent.set_layers(docproxy.layers, docproxy.document.active))

    @mvcHandler(main.Gribouillis.DOC_ACTIVATED)
    def _on_doc_activated(self, docproxy):
        if self.__docproxy is not docproxy:
            self.__docproxy = docproxy
            map(self._add_notifications, self.viewComponent.set_layers(docproxy.layers, docproxy.document.active))

    @mvcHandler(main.Gribouillis.DOC_LAYER_ADDED)
    def _on_doc_layer_added(self, docproxy, layer, pos):
        if self.__docproxy is docproxy:
            self._add_notifications(self.viewComponent.add_layer(layer, pos))
            
    @mvcHandler(main.Gribouillis.DOC_LAYER_DELETED)
    def _on_doc_layer_deleted(self, docproxy, layer):
        if self.__docproxy is docproxy:
            self.viewComponent.del_layer(layer)
            
    @mvcHandler(main.Gribouillis.DOC_LAYER_MOVED)
    def _on_doc_layer_moved(self, docproxy, layer, pos):
        if self.__docproxy is docproxy:
            self.viewComponent.move_layer(layer, pos)
            
    @mvcHandler(main.Gribouillis.DOC_LAYER_ACTIVATED)
    def _on_doc_layer_activated(self, docproxy, layer):
        if self.__docproxy is docproxy and layer is not self.viewComponent.active:
            self.viewComponent.active = layer

