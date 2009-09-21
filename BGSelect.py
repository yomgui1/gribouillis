###############################################################################
# Copyright (c) 2009 Guillaume Roguez
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
from pymui.mcc import laygroup

MUIA_Dtpic_Scale = 0x8042ca4c  # private

class Background(Dtpic):
    def __init__(self, path, size=None):
        super(Background, self).__init__(InputMode=MUIV_InputMode_Toggle,
                                         Frame=MUIV_Frame_None,
                                         Name=path)
        if size:
            self._set(MUIA_Dtpic_Scale, size, 'I')
    
class MiniBackgroundSelect(Window):
    IMAGE_SIZE = 48
    
    def __init__(self):
        ro = laygroup.LayGroup(SameSize=True, Spacing=2)
        super(MiniBackgroundSelect, self).__init__(ID=0, # ID=0 => don't store position/size!
                                                   LeftEdge='moused', TopEdge='moused',
                                                   Width=5*self.IMAGE_SIZE, Height=3*self.IMAGE_SIZE,
                                                   Borderless=True,
                                                   RootObject=ro,
                                                   NeedsMouseObject=True)

        self.selection = None
        self.Notify('MouseObject', MUIV_EveryTime, self.OnMouseObject, MUIV_TriggerValue)
        self.watchers = []

    def add_watcher(self, cb):
        if cb not in self.watchers:
            self.watchers.append(cb)

    def rem_watcher(self, cb):
        self.watchers.remove(cb)

    def AddImage(self, path):
        bg = Background(path, self.IMAGE_SIZE)
        bg.CycleChain = True
        bg.Notify('Selected', True, self.OnSelection, bg)
        ro = self.RootObject
        ro.DoMethod(MUIM_Group_InitChange)
        ro.AddChild(bg)
        ro.DoMethod(MUIM_Group_ExitChange)
        if not self.selection:
            self.selection = bg

    def OnMouseObject(self, obj):
        if isinstance(obj, Background):
            self.selection.Selected = False
            obj.NNSet('Selected', True)
            self.selection = obj

    def OnSelection(self, bg):
        self.Close()
        for cb in self.watchers:
            cb(bg)
