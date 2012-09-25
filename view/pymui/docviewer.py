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

import pymui
import sys
import traceback as tb

from pymui.mcc.betterbalance import BetterBalance
from random import random

import model
import view
import main
import utils

from model.devices import *
from view import viewport

from .app import Application
from .widgets import Ruler
from .viewport import DocViewport
from const import *


class RuledViewGroup(pymui.Group):
    """RuledViewGroup() -> PyMUI Group instance

    Container for a single Viewport with one horizontal
    and one vertical rulers.
    """

    def __init__(self, docproxy):
        super(RuledViewGroup, self).__init__(Horiz=False, Columns=2,
                                             InnerSpacing=0, Spacing=0)

        # Rulers pop button
        names = [Ruler.METRICS[k][0] for k in Ruler.METRIC_KEYS]
        lst = pymui.List(SourceArray=names,
                         AdjustWidth=True,
                         MultiSelect=pymui.MUIV_List_MultiSelect_None)
        self._popruler = pymui.Popobject(
            Object=lst,
            Button=pymui.Image(Frame='ImageButton',
            Spec=pymui.MUII_PopUp,
            InputMode='RelVerify'))
        lst.Notify('DoubleClick', self._on_ruler_metric, self._popruler, lst)
        self.AddChild(self._popruler)

        # Top ruler
        self.hruler = Ruler(Horiz=True)
        self.AddChild(self.hruler)

        # Left ruler
        self.vruler = Ruler(Horiz=False)
        self.AddChild(self.vruler)

        # Viewport
        self.viewport = DocViewport(docproxy, rulers=(self.hruler,
                                                      self.vruler))
        self.AddChild(self.viewport)

    def _on_ruler_metric(self, evt, pop, lst):
        pop.Close(0)
        k = Ruler.METRIC_KEYS[lst.Active.value]
        self.hruler.set_metric(k)
        self.vruler.set_metric(k)


class SplitableViewGroup(pymui.Group):
    """SplitableViewGroup() -> PyMUI Group instance

    Container for two Viewport splited horizontaly or verticaly,
    and separated by a balance object.
    Each side can be again splited calling split() method.
    if args is empty, the group starts with a single (non splited) viewport.
    """

    def __init__(self, horiz=True, *args, **kwds):
        super(SplitableViewGroup, self).__init__(InnerSpacing=0, Spacing=0,
                                                 Horiz=horiz)
        if args:
            self.contents = args
            v1, v2 = args
            self.AddChild(v1)
            self.AddChild(BetterBalance(ID=0))
            self.AddChild(v2)
        else:
            self.contents = DocViewport()
            self.AddChild(self.contents)
            if 'docproxy' in kwds:
                self.contents.set_docproxy(kwds['docproxy'])

    def split(self, horiz=True):
        self.InitChange()
        try:
            self.RemChild(self.contents)
            self.contents = SplitableViewGroup(horiz, self.contents,
                                               DocViewport())
            self.AddChild(self.contents)
        finally:
            self.ExitChange()

    @property
    def viewports(self):
        if isinstance(self.contents, DocViewport):
            return [self.contents]
        else:
            return self.contents[0].viewports + self.contents[1].viewports


class DocWindow(pymui.Window):
    # Pointers type from C header file 'intuition/pointerclass.h'
    POINTERTYPE_NORMAL = 0
    POINTERTYPE_DRAW = 6
    POINTERTYPE_PICK = 5

    focus = 0  # used by viewport objects
    _name = None
    _scale = 1.0

    # Private API
    #

    def __init__(self, docproxy, **kwds):
        self.title_header = _T("Document") + ": %s @ %u%% (%s)"
        super(DocWindow, self).__init__(None,
                                        ID=0,  # The haitian power
                                        LeftEdge='centered',
                                        TopEdge='centered',
                                        WidthVisible=50,
                                        HeightVisible=50,
                                        TabletMessages=True,
                                        **kwds)

        self._watchers = {'pick': None}
        self.set_docproxy(docproxy)

        # Root = paged group, with 2 pages:
        # 1 : ruled viewport group
        # 2 : tiled viewport group

        self.RootObject = root = pymui.VGroup(PageMode=True)

        self._ruled = RuledViewGroup(docproxy)
        self._splitable = SplitableViewGroup(docproxy=docproxy)

        root.AddChild(self._ruled, self._splitable)

        self.Notify('Activate', self._on_activate)
        self.show_ruled()

    def _on_activate(self, evt):
        if evt.value:
            self.pointer = self.POINTERTYPE_DRAW
        else:
            self.pointer = self.POINTERTYPE_NORMAL

    def _refresh_title(self):
        self.Title = self.title_header % (docproxy.docname, self._scale * 100,
                                          name)

    # Public API

    def set_watcher(self, name, cb, *args):
        self._watchers[name] = (cb, args)

    def show_ruled(self):
        self.RootObject.ActivePage = 0

    def show_splited(self):
        self.RootObject.ActivePage = 1

    def set_docproxy(self, docproxy):
        self.docproxy = docproxy
        self._name = docproxy.active_layer.name.encode('latin1', 'replace')
        self._refresh_title()

    def set_scale(self, scale):
        self._scale = scale
        self._refresh_title()

    def confirm_close(self):
        return pymui.DoRequest(pymui.GetApp(),
                               gadgets="_Yes|*_No",
                               title="Need confirmation",
                               format="This document is modified and not " \
                                   "saved yet.\nSure to close it?")

    def set_cursor_radius(self, r):
        for da in self.viewports:
            da.set_cursor_radius(r)

    def set_background_rgb(self, rgb):
        for da in self.disp_areas:
            da.set_background_rgb(rgb)

    @property
    def viewports(self):
        if self.RootObject.object.ActivePage.value == 0:
            return [self._ruled.viewport]
        else:
            return self._splitable.viewports

    @property
    def rulers(self):
        return self.RootObject.object.ActivePage.value == 0


class DocWindowFullscreen(DocWindow):
    # Private API
    #

    def __init__(self):
        super(DocWindowFullscreen, self).__init__(WidthScreen=100,
                                                  HeightScreen=100,
                                                  Backdrop=True,
                                                  Borderless=True)
