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
import view.context as ctx

from model.devices import *
from view import viewport
from utils import _T

from .widgets import Ruler
from .viewport import DocViewport
from .const import *


class ModifiableContainer:
    def __init__(self, container):
        self.__contents = None
        self.__container = container
    
    def get_contents(self):
        return self.__contents
        
    def set_contents(self, contents=None):
        """use_contents(contents=None) -> BOOPSI object
        
        Change root object contents using the given one.
        Returns the previous contents.
        
        contents : a BOOPSI object or None for empty contents.
        """
        
        if contents is None and self.__contents is None:
            return
            
        root = self.__container
        root.InitChange()
        try:
            old_contents = self.__contents
            if old_contents is not None:
                root.RemChild(old_contents)
            self.__contents = contents
            if contents:
                print "Set %s as contents of %s" % (contents, root)
                root.AddTail(contents)
        finally:
            root.ExitChange()
        return old_contents

    contents = property(fget=get_contents, fset=set_contents, fdel=set_contents)


class RuledViewGroup(pymui.Group):
    """RuledViewGroup() -> PyMUI Group instance

    Container for a single Viewport with one horizontal
    and one vertical rulers.
    """

    viewport = None
    
    def __init__(self, root):
        super(RuledViewGroup, self).__init__(Horiz=False, Columns=2,
                                             InnerSpacing=0, Spacing=0)        
        self._root = root

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
        
        vp = DocViewport(root, rulers=(self.hruler, self.vruler))
        self.viewport = vp
        self.like = vp.like
        self.AddChild(vp)
        root.register_viewport(vp)

    def _on_ruler_metric(self, evt, pop, lst):
        pop.Close(0)
        k = Ruler.METRIC_KEYS[lst.Active.value]
        self.hruler.set_metric(k)
        self.vruler.set_metric(k)

    def delete_contents(self):
        self._root.unregister_viewport(self.viewport)
        self.viewport.Destroy()


class SplitableViewGroup(pymui.Group, ModifiableContainer):
    """SplitableViewGroup() -> PyMUI Group instance

    Container for two Viewport splited horizontaly or verticaly,
    and separated by a balance object.
    Each side can be again splited calling split() method.
    """

    def __init__(self, root, parent=None):
        super(SplitableViewGroup, self).__init__(InnerSpacing=0, Spacing=0)
        ModifiableContainer.__init__(self, self)
        
        self._root = root
        self._parent = parent

    def split(self, horiz=True):
        vp = self.contents
        assert isinstance(vp, DocViewport)
        
        split1 = SplitableViewGroup(self._root, self, vp)
        split2 = SplitableViewGroup(self._root, self, vp.duplicate())
        self._root.register_viewport(split2.contents)

        grp = (pymui.HGroup if horiz else pymui.VGroup)(InnerSpacing=0, Spacing=0)
        grp.split1 = split1
        grp.split2 = split2
        grp.AddChild(split1, BetterBalance(ID=0), split2)
        self.contents = grp

    def unsplit(self):
        vp = self.contents
        assert isinstance(vp, DocViewport)
        if self._parent is not None:
            grp = self._parent.set_contents(vp)
            if vp is grp.split1.contents:
                other = grp.split2.delete_contents()
            else:
                other = grp.split1.delete_contents()
            grp.Destroy()
            
    def delete_contents(self, obj):
        if isinstance(obj, DocViewport):
            self._root.unregister_viewport(obj)
            obj.Destroy()
        else:
            self.delete_contents(obj.set_contents(None))

    @property
    def viewports(self):
        obj = self.contents
        if isinstance(obj, DocViewport):
            return [obj]
        else:
            return obj.split1.viewports + obj.split2.viewport


class DrawingRoot(pymui.Group):
    """DrawingRoot class
    
    Versatile paged group to show one or more document viewport
    in various layout configurations.
    """

    def __init__(self, docproxy, register_viewport_cb, unregister_viewport_cb):
        super(DrawingRoot, self).__init__(Horiz=True, PageMode=True)
        
        self.register_viewport = register_viewport_cb
        self.unregister_viewport = unregister_viewport_cb

        # Page 1
        self._ruled = RuledViewGroup(self)
        
        # Page 2:
        self._splitable = SplitableViewGroup(self)
        
        self.AddChild(self._ruled, self._splitable)

        # Show default viewport
        vp = DocViewport(self, docproxy)
        self._splitable.set_contents(vp)
        self.register_viewport(vp)
        self.show_ruled(vp)

    def show_ruled(self, viewport=None):
        if viewport:
            assert viewport in self.viewports
            self._ruled.like(viewport)
        self.ActivePage = 0

    def show_splited(self):
        self.ActivePage = 1

    @property
    def viewports(self):
        if self._ruled.viewport is not None:
            return self._splitable.viewports + [self._ruled.viewport]
        else:
            return self._splitable.viewports

    @property
    def rulers(self):
        return self.RootObject.object.ActivePage.value == 0


class DocWindowBase(pymui.Window, ModifiableContainer):
    # Pointers type from C header file 'intuition/pointerclass.h'
    POINTERTYPE_NORMAL = 0
    POINTERTYPE_DRAW = 6
    POINTERTYPE_PICK = 5
    
    focus = 0  # used by viewport objects
    
    def __init__(self, **kwds):
        root = pymui.HGroup()
        super(DocWindowBase, self).__init__(None,
                                            ID=0, # Haitian power
                                            CloseOnReq=True,
                                            TabletMessages=True,
                                            RootObject=root,
                                            **kwds)
        ModifiableContainer.__init__(self, root)
        self.Notify('Activate', self._on_activate)

    def _on_activate(self, evt):
        if evt.value:
            self.pointer = self.POINTERTYPE_DRAW
        else:
            self.pointer = self.POINTERTYPE_NORMAL

        ctx.active_docwin = self

    def active_docproxy(self, docproxy):
        pass

    def set_scale(self, scale):
        pass

    def confirm_close(self):
        "Request user confirmation to close the window."
        
        return pymui.DoRequest(pymui.GetApp(),
                               gadgets=_T("_Yes|*_No"),
                               title=_T("Need confirmation"),
                               format=_T("This window contains modified"
                                         "and not yet saved work\n"
                                         "Are you sure to close it?"))


class FramedDocWindow(DocWindowBase):
    _name = None
    _scale = 1.0
    _title_header = _T("Document") + ": %s @ %u%% (%s)"
    __instances = set()

    # private API

    def __init__(self):
        super(FramedDocWindow, self).__init__(Position=('centered', 'centered'),
                                              WidthVisible=50,
                                              HeightVisible=50)
        FramedDocWindow.__instances.add(self)
        
        self.Notify('CloseRequest', lambda *a: FramedDocWindow.__instances.remove(self))

    @staticmethod
    def open_all(state=True):
        for win in FramedDocWindow.__instances:
            # MUI lacks of a way to remember window position during runtime
            # without save it at closing if user has requested it.
            # So I emulate that using a PyMUI function that call
            # the instuition function ChangeWindowBox().
            if win.Open.value and not state:
                win.__box = win.LeftEdge.value, win.TopEdge.value, \
                            win.Width.value, win.Height.value
            
            win.Open = state
            
            if win.Open.value and state:
                win.SetWindowBox(*win.__box)

    def _refresh_title(self):
        self.Title = FramedDocWindow._title_header % (self._dname, self._scale * 100, self._lname)

    # Public API
    
    def active_docproxy(self, docproxy):
        "Modify window properties using the given active docproxy"

        self._dname = docproxy.docname
        self._lname = docproxy.active_layer.name.encode('latin1', 'replace')
        self._refresh_title()

    def set_scale(self, scale):
        self._scale = scale
        self._refresh_title()


class FullscreenDocWindow(DocWindowBase):
    # Private API
    #

    def __init__(self):
        super(FullscreenDocWindow, self).__init__(WidthScreen=100,
                                                  HeightScreen=100,
                                                  Backdrop=True,
                                                  Borderless=True)