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
import os.path

class CMSPrefsWindow(Window):
    def __init__(self, title):
        super(CMSPrefsWindow, self).__init__(title, ID=0, LeftEdge='centered', TopEdge='centered')

        self._ok_cb = []
        self._rgb_profiles = [["sRGB (built-in)", None],
                              ["From file...", None]]

        self.Notify('CloseRequest', True, self.Close)
        
        top = VGroup()
        self.RootObject = top

        o = CheckMark()
        o.CycleChain = True
        o.Notify('Pressed', False, self.OnEnableCMS, MUIV_TriggerValue)
        g = HGroup(InnerBottom=8)
        g.AddChild(o, LLabel("Activate Color Management"))
        top.AddChild(g)

        g = ColGroup(2, GroupFrameT="Profiles")

        self._rgb_profiles_obj = Cycle([n for n, _ in self._rgb_profiles], CycleChain=True)
        o.Notify('Active', MUIV_EveryTime, self.OnCycleProfile, MUIV_TriggerValue, 'RGB')
        g.AddChild(Label("For RGB surfaces:"), o)
        
        im1 = Image(Spec=MUII_PopFile,
                    Frame=MUIV_Frame_PopUp,
                    InnerSpacing=(0,)*4,
                    InputMode=MUIV_InputMode_RelVerify)
        im1.Notify('Selected', False, self.OnSelectInputFile)
        im2 = Image(Spec=MUII_PopFile,
                    Frame=MUIV_Frame_PopUp,
                    InnerSpacing=(0,)*4, 
                    InputMode=MUIV_InputMode_RelVerify)
        im2.Notify('Selected', False, self.OnSelectOutputFile)

        top.AddChild(HGroup(Child=(Text(MUIX_R+"Input Profile:", Weight=0),
                                         self._str_in, im1)))
        top.AddChild(HGroup(Child=(Text(MUIX_R+"Output Profile:", Weight=0),
                                         self._str_out, im2)))

        top.AddChild(Rectangle(HBar=True, Weight=0, FixHeight=8))
        bt_ok = SimpleButton("Ok")
        bt_cancel = SimpleButton("Cancel")
        top.AddChild(HGroup(Child=(bt_ok, bt_cancel)))

        bt_ok.Notify('Selected', False, self.OnConfirm)
        bt_cancel.Notify('Selected', False, self.Close)

    def AddOkCallback(self, cb, *a):
        self._ok_cb.append((cb, a))

    def Open(self):
        self._str_in.Contents = self._in_profile
        self._str_out.Contents = self._out_profile
        super(CMSPrefsWindow, self).Open()

    def OnEnableCMS(self, status):
        self.ApplicationObject.EnableCMS(status)

    def OnCycleProfile(self, active, name):
        # From file?
        if active == len(self._rgb_profiles)-1:
            getfilename(self, "Choose %s color profile" % name,
                        self.last_load_dir, "#?.icc",
                        False)
        else:
            _, p = self._rgb_profiles[active]

        self.ApplicationObject.SetProfile(name, p)
        
    def OnConfirm(self):
        self.Close()
        if os.path.isfile(self._str_in.Contents):
            self._in_profile = self._str_in.Contents
        if os.path.isfile(self._str_out.Contents):
            self._out_profile = self._str_out.Contents
        for cb, a in self._ok_cb:
            cb(self, *a)

    def OnSelectInputFile(self):
        self._str_in.Contents = getfilename(self, "Select Input Profile", os.path.dirname(self._str_in.Contents))

    def OnSelectOutputFile(self):
        self._str_out.Contents = getfilename(self, "Select Output Profile", os.path.dirname(self._str_out.Contents))

    in_profile = property(fget=lambda self: self._in_profile)
    out_profile = property(fget=lambda self: self._out_profile)
