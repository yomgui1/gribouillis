from pymui import *
from pymui.mcc import laygroup
from brush import Brush

import brush

class BrushSelect(Window):
    def __init__(self, title):
        super(BrushSelect, self).__init__(title, ID="BSEL",
                                          RightEdge=64, BottomEdge=64,
                                          Width=6*brush.Brush.BRUSH_SCALE,
                                          Height=12*brush.Brush.BRUSH_SCALE)

        self.brush = Brush()
        self.brush.Notify('Name', MUIV_EveryTime, self.OnBrushChange)

        self.obj_EditBrush = SimpleButton("Edit")
        brush_group = VGroup(Child=(self.brush, self.obj_EditBrush))

        self.obj_BName = Text(Frame=MUIV_Frame_Text, SetMin=False)
        info_group = VGroup(Child=(self.obj_BName, VSpace(0)))

        ro = VGroup()
        ro.AddChild(HGroup(Title="Current brush", Child=(brush_group, info_group)))
        ro.AddChild(Rectangle(HBar=True, FixHeight=8))
        self._bgroup = laygroup.LayGroup(SameSize=True, TopOffset=0, Spacing=0)
        ro.AddChild(self._bgroup)

        self.RootObject = ro

    def OnBrushChange(self):
        self.obj_BName.Contents = self.brush.shortname

    def SetBrushes(self, brushes):
        self._bgroup.DoMethod(MUIM_Group_InitChange)
        self._bgroup.AddChild(lock=True, *brushes)
        self._bgroup.DoMethod(MUIM_Group_ExitChange)
