from pymui import *
from pymui.mcc import laygroup
from brush import Brush

import brush

class BrushSelect(Window):
    def __init__(self, title):
        super(BrushSelect, self).__init__(title, ID="BSEL",
                                          RightEdge=64, BottomEdge=64,
                                          Width=6*brush.Brush.BRUSH_SCALE, Height=12*brush.Brush.BRUSH_SCALE)

        self.brush = Brush()

        ro = Group.VGroup()
        ro.AddChild(Group.HGroup(Title="Current brush", Child=(self.brush, Rectangle.HSpace(0))))
        ro.AddChild(Rectangle(HBar=True, FixHeight=8))
        self._bgroup = laygroup.LayGroup(SameSize=True, TopOffset=0, Spacing=0)
        ro.AddChild(self._bgroup)

        self.RootObject = ro

    def SetBrushes(self, brushes):
        self._bgroup.DoMethod(MUIM_Group_InitChange)
        self._bgroup.AddChild(lock=True, *brushes)
        self._bgroup.DoMethod(MUIM_Group_ExitChange)
