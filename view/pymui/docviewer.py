# -*- coding: latin-1 -*-

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

import pymui, sys
import traceback as tb

from pymui.mcc.betterbalance import BetterBalance
from random import random

import model, view, main, utils

from model.devices import *
from view import viewport

from .app import Application
from .widgets import Ruler
from .viewport import DocViewport
from const import *


__all__ = [ 'DocWindow', 'DocWindowFullscreen' ]

class DocWindow(pymui.Window):

    # Pointers type from C header file 'intuition/pointerclass.h'
    POINTERTYPE_NORMAL = 0
    POINTERTYPE_DRAW   = 6
    POINTERTYPE_PICK   = 5

    focus = 0 # used by viewport objects
    permit_rulers = True
    _name = None
    _scale = 1.0
    
    # Private API
    #

    def __init__(self, docproxy, **kwds):
        self.title_header = 'Document: %s @ %u%% (%s)'
        super(DocWindow, self).__init__('',
                                        ID=0,       # The haitian power
                                        LeftEdge='centered',
                                        TopEdge='centered',
                                        WidthVisible=50,
                                        HeightVisible=50,
                                        TabletMessages=True, # enable tablet events support
                                        **kwds)

        self.disp_areas = []
        self._watchers = {'pick': None}

        self.docproxy = docproxy
        name = docproxy.docname

        root = pymui.ColGroup(2, InnerSpacing=0, Spacing=0)
        self.RootObject = root
        
        # Rulers space
        obj = pymui.List(SourceArray=[ Ruler.METRICS[k][0] for k in Ruler.METRIC_KEYS ],
                         AdjustWidth=True,
                         MultiSelect=pymui.MUIV_List_MultiSelect_None)
        pop = pymui.Popobject(Object=obj,
                              Button=pymui.Image(Frame='ImageButton',
                                                 Spec=pymui.MUII_PopUp,
                                                 InputMode='RelVerify'))
        obj.Notify('DoubleClick', self._on_ruler_metric, pop, obj)
        root.AddChild(pop)
        self._popruler = pop
        
        # Top ruler
        self._hruler = Ruler(Horiz=True)
        root.AddChild(self._hruler)
        
        # Left ruler
        self._vruler = Ruler(Horiz=False)
        root.AddChild(self._vruler)
        
        self._vpgrp = pymui.HGroup(InnerSpacing=0, Spacing=0)
        root.AddChild(self._vpgrp)
        
        # Default editor area
        da, _ = self.add_viewport()
        
        # Status bar - TODO
        #root.AddChild(pymui.HVSpace())
        #self._status = pymui.Text(Frame='Text', Background='Text')
        #root.AddChild(self._status)

        self.Notify('Activate', self._on_activate)
        self.set_doc_name(name)
        
        # defaults
        self._popruler.ShowMe = False
            
    def _on_activate(self, evt):
        if evt.value:
            self.pointer = self.POINTERTYPE_DRAW
        else:
            self.pointer = self.POINTERTYPE_NORMAL
        
    def _on_ruler_metric(self, evt, pop, lister):
        pop.Close(0)
        k = Ruler.METRIC_KEYS[lister.Active.value]
        self._hruler.set_metric(k)
        self._vruler.set_metric(k)
        
    def add_viewport(self, master=None, horiz=False):
        da = DocViewport(self, self.docproxy)
        da._hruler = self._hruler
        da._vruler = self._vruler
        self.disp_areas.append(da)

        if not master:
            if len(self.disp_areas) > 1:
                self._vpgrp.AddChild(BetterBalance())
                da.location = 1
            else:
                da.location = 0
            self._vpgrp.AddChild(da)
            da.group = self._vpgrp
            da.other = da2 = None
            self._vpgrp.da = [da, da2]
        else:
            parent = master.group
            if horiz:
                grp = pymui.VGroup(InnerSpacing=0, Spacing=0)
            else:
                grp = pymui.HGroup(InnerSpacing=0, Spacing=0)
            
            parent.InitChange()
            try:
                grp.location = master.location
                da2 = DocDisplayArea(self, self.docproxy)
                self.disp_areas.append(da2)
                grp.AddChild(da, BetterBalance(), da2)
                da.location = 0
                da.group = grp
                da.other = da2
                da2.location = 1
                da2.group = grp
                da2.other = da
                grp.da = [da, da2]
                if master.location == 0:
                    parent.AddHead(grp)
                else:
                    parent.AddTail(grp)
                parent.RemChild(master)
                self.disp_areas.remove(master)
            finally:
                parent.ExitChange()
                
        return da, da2

    def set_watcher(self, name, cb, *args):
        self._watchers[name] = (cb, args)

    # Public API
    #
    
    def refresh_title(self):
        self.Title = self.title_header % (self._name, self._scale*100, self.docproxy.active_layer.name.encode('latin1', 'replace'))

    def set_doc_name(self, name):
        self._name = name
        self.refresh_title()
        
    def set_scale(self, scale):
        self._scale = scale
        self.refresh_title()

    def confirm_close(self):
        return pymui.DoRequest(pymui.GetApp(),
                               gadgets= "_Yes|*_No",
                               title  = "Need confirmation",
                               format = "This document is modified and not saved yet.\nSure to close it?")

    def set_cursor_radius(self, r):
        for da in self.disp_areas:
            da.set_cursor_radius(r)
            
    def set_background_rgb(self, rgb):
        for da in self.disp_areas:
            da.set_background_rgb(rgb)
            
    def toggle_rulers(self):
        state = self.permit_rulers and not self._popruler.ShowMe.value
        root = self.RootObject.object
        root.InitChange()
        try:
            self._popruler.ShowMe = state
            # I don't know why... but hidding only the pop, hiding all rulers...
        finally:
            root.ExitChange()

    def set_status(self, **kwds):
        pass # TODO

    @property
    def rulers(self):
        return self._popruler.ShowMe.value

class DocWindowFullscreen(DocWindow):
    # Private API
    #

    def __init__(self, ctx, docproxy):
        super(DocWindowFullscreen, self).__init__(ctx, docproxy,
                                                  #WidthScreen=100,
                                                  #HeightScreen=100,
                                                  Backdrop=True,
                                                  Borderless=True)