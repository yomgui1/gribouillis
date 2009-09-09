from pymui import *
from pymui.mcc import laygroup

MUIA_Dtpic_Scale = 0x8042ca4c  # private

class Background(Dtpic):
    def __init__(self, path, size=None):
        super(Background, self).__init__(InputMode=MUIV_InputMode_Toggle,
                                         Frame=MUIV_Frame_None,
                                         Name=path)
        if size:
            self._set(MUIA_Dtpic_Scale, size)
    
class MiniBackgroundSelect(Window):
    IMAGE_SIZE = 48
    
    def __init__(self, title):
        ro = laygroup.LayGroup(SameSize=True, Spacing=2)
        super(BackgroundSelect, self).__init__(ID="BGSE",
                                               TopEdge='moused', BottomEdge='moused',
                                               Width=5*IMAGE_SIZE, Height=3*IMAGE_SIZE,
                                               DragBar=False,
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
        bg = Background(path, IMAGE_SIZE)
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
