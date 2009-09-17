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

import pymui

class CMSPrefsWindow(pymui.Window):    
    def __init__(self, title):
        super(CMSWindow, self).__init__(title, ID=0, LeftEdge='centered', TopEdge='centered')

        self._in_profile = ""
        self._out_profile = ""
        self._ok_cb = []

        top = pymui.VGroup()
        self.RootObject = top

        self._str_in = pymui.String(MaxLen=1024, Frame=pymui.MUIV_Frame_String)
        self._str_out = pymui.String(MaxLen=1024, Frame=pymui.MUIV_Frame_String)

        top.AddChild(pymui.HGroup(Child=(pymui.Text("Input Profile:"), self._str_in)))
        top.AddChild(pymui.HGroup(Child=(pymui.Text("Output Profile:"), self._str_out)))

        top.AddChild(pymui.Rectangle(HBar=True, Weight=0, FixHeight=8))
        bt_ok = pymui.SimpleButton("Ok")
        bt_cancel = pymui.SimpleButton("Cancel")
        top.AddChild(HGroup(Child=(bt_ok, bt_cancel)))

        bt_ok.Notify('Acknowledge', MUIV_EveryTime, self.OnConfirm)
        bt_cancel.Notify('Acknowledge', MUIV_EveryTime, self.Close)

    def AddOkCallback(self, cb, *a):
        self._ok_cb.append((cb, a))

    def Open(self):
        self._str_in.Contents = self._in_profile
        self._str_out.Contents = self._out_profile
        super(CMSWindow, self).Open()

    def OnConfirm(self):
        self.Close()
        self._in_profile = self._str_in.Contents
        self._out_profile = self._str_out.Contents
        for cb, a in self._ok_cb:
            cb(self, *a)

    in_profile = property(fget=lambda self: self._in_profile)
    out_profile = property(fget=lambda self: self._out_profile)
