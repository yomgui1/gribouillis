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
from brush import DrawableBrush

class BrushSelect(Window):
    def __init__(self, title):
        super(BrushSelect, self).__init__(title, ID="BSEL",
                                          RightEdge=64, BottomEdge=64,
                                          Width=6*DrawableBrush.BRUSH_SCALE,
                                          Height=12*DrawableBrush.BRUSH_SCALE)

        self.brush = DrawableBrush()
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
