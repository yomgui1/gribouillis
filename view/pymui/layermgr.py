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

__all__ = [ 'LayerMgr', 'LayerCtrl' ]

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
    STATE_COLORS = { False: 0, True: '2:00000000,44444444,99999999' }

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
    def __init__(self, name):
        super(LayerMgr, self).__init__(ID='LayerMgr', Title='Layers', CloseOnReq=True)
        self.name = name

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

                # TODO: check visibility
                
                self.btn['merge'].Disabled = layer is self.__layctrllist[0].layer
                return

    active = property(fget=get_active, fset=set_active)


