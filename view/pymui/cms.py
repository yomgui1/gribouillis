###############################################################################
# Copyright (c) 2009-2013 Guillaume Roguez
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

import pymui, sys

from model import profile
from utils import _T

__all__ = [ 'AssignICCWindow', 'ConvertICCWindow' ]

class AssignICCWindow(pymui.Window):
    _radio = None
    _docproxy = None
    _profile = None
    
    def __init__(self):
        super(AssignICCWindow, self).__init__(_T("Assign Profile"), CloseOnReq=True)

        self._profiles = profile.Profile.get_all()
        
        top = pymui.VGroup()
        self.RootObject = top
        
        self._radio_grp = pymui.VGroup(GroupTitle=_T("Assign Profile")+':')
        self._cb = pymui.Cycle(map(str, self._profiles), CycleChain=True, Disabled=True)
        self._cb.Notify('Active', self._on_profile_active)
        self._radio_grp.AddTail(self._cb)
        
        top.AddChild(self._radio_grp)
        
        top.AddChild(pymui.HBar(0))
        grp = pymui.HGroup()
        top.AddChild(grp)
        
        grp.AddChild(pymui.HSpace(0))
        bt = pymui.SimpleButton(_T("Assign"), CycleChain=True)
        grp.AddChild(bt)
    
    def _setup_radio(self):
        self._radio_grp.InitChange()
        try:
            if self._radio:
                self._radio_grp.Remove(self._radio)
                self._radio.RemoveNotify(self._radio_notify)
                del self._radio
            entries = [_T("No color management on this document"),
                       _T("Profile")+': ']
            if self._profile:
                entries.insert(1, _T("Working")+': %s' % self._profile)
                act = 1
            else:
                act = 0
            self._radio = pymui.Radio(entries,CycleChain=True)
            self._radio.Active = act
            self._radio_notify = self._radio.Notify('Active', self._on_radio_active)
            self._radio_grp.AddHead(self._radio)
        finally:
            self._radio_grp.ExitChange()
            
    def _on_radio_active(self, evt):
        self._cb.Disabled = evt.value.value == 0
        
    def _on_profile_active(self, evt):
        if self._docproxy:
            self._docproxy.profile = self._profiles[evt.value.value]
    
    def _set_docproxy(self, docproxy):
        if docproxy != self._docproxy or self._profile != docproxy.profile:
            self._docproxy = docproxy
            self._profile = docproxy.profile
            #TODO: bugged
            # self._setup_radio()
        
    docproxy = property(fset=_set_docproxy)
    
class ConvertICCWindow(pymui.Window):
    _docproxy = None
    _profile = None
    
    def __init__(self):
        super(ConvertICCWindow, self).__init__(_T("Convert to Profile"), CloseOnReq=True)

        self._profiles = profile.Profile.get_all()
        
        top = pymui.VGroup()
        self.RootObject = top
        
        grp = pymui.VGroup(GroupTitle=_T("Source")+':')
        top.AddChild(grp)

        self._cur_label = pymui.Text()
        grp.AddChild(self._cur_label)
        
        grp = pymui.VGroup(GroupTitle=_T("Destination")+':')
        top.AddChild(grp)

        hgrp = pymui.HGroup()
        grp.AddChild(hgrp)
        
        hgrp.AddChild(pymui.Text(_T("Profile")+': '))
        
        self._pro_cycle = pymui.Cycle(map(str, self._profiles), CycleChain=True)
        hgrp.AddTail(self._pro_cycle)

        grp = pymui.VGroup(GroupTitle=_T("Options")+':')
        top.AddChild(grp)

        self._intents = profile.INTENTS.keys()
        cycle = pymui.Cycle(self._intents)
        cycle.Notify('Active', self._on_intent_active)

        hgrp = pymui.HGroup()
        grp.AddChild(hgrp)

        hgrp.AddChild(pymui.Text(_T("Intent")+': '))
        hgrp.AddChild(cycle)

        """
        bt1 = gtk.CheckButton(_T("Use Black Point Compensation")+': ')
        bt2 = gtk.CheckButton(_T("Use Dither")+': ')
        bt3 = gtk.CheckButton(_T("Flatten Image")+': ')
        if len(docproxy.document.layers) == 1:
            bt3.set_sensitive(False)

        vbox.pack_start(bt1)
        vbox.pack_start(bt2)
        vbox.pack_start(bt3)

        self.show_all()
        """
        
        top.AddChild(pymui.HBar(0))
        grp = pymui.HGroup()
        top.AddChild(grp)
        
        grp.AddChild(pymui.HSpace(0))
        bt = pymui.SimpleButton(_T("Convert"), CycleChain=True)
        grp.AddChild(bt)
        
    def _on_intent_active(self, evt):
        self._intent = profile.INTENTS[self._intents[evt.value.value]]
        
    def _set_docproxy(self, docproxy):
        if docproxy != self._docproxy or self._profile != docproxy.profile:
            self._docproxy = docproxy
            self._profile = docproxy.profile
            self._cur_label.Contents = _T("Profile")+': %s' % self._profile
        
    docproxy = property(fset=_set_docproxy)
