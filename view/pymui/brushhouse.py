
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
from pymui.mcc import laygroup

import main, model, utils, view

from utils import mvcHandler, Mediator
from model.brush import Brush

__all__ = [ 'BrushHouseWindow', 'BrushHouseWindowMediator' ]

MUIA_Group_PageMax = 0x8042d777 # /* V4  i.. BOOL              */ /* private */

class BrushHouseWindow(pymui.Window):
    _current_cb = utils.idle_cb

    def __init__(self):
        super(BrushHouseWindow, self).__init__('Brush House',
                                               ID='BRHO',
                                               Width=300, Height=200,
                                               TopDeltaEdge=0,
                                               RightEdge=0,
                                               CloseOnReq=True)

        self._brushes = set()
        self._all = None
        self._current = None
        self._pages = []

        # UI
        self._top = topbox = self.RootObject = pymui.VGroup()

        # Brush context menu
        self._brushmenustrip = pymui.Menustrip()
        menu = pymui.Menu('Brush actions')
        self._brushmenustrip.AddTail(menu)

        self._menuitems = {}
        for k, text in [('change-icon', 'Change icon...'),
                        ('delete', 'Delete')]:
            o = self._menuitems[k] = pymui.Menuitem(text)
            menu.AddChild(o)

        # Pages controls
        box = pymui.HGroup()
        topbox.AddChild(box)

        bt = pymui.SimpleButton('New page', Weight=0)
        box.AddChild(bt)
        bt.Notify('Pressed', self._on_add_page, when=False)

        bt = self._del_page_bt = pymui.SimpleButton('Delete page', Weight=0, Disabled=True)
        box.AddChild(bt)
        bt.Notify('Pressed', self._on_del_page, when=False)

        bt = pymui.SimpleButton('New brush', Weight=0)
        box.AddChild(bt)
        bt.Notify('Pressed', self._on_new_brush, when=False)

        bt = pymui.SimpleButton('Save all', Weight=0)
        box.AddChild(bt)
        bt.Notify('Pressed', self._on_save_all, when=False)

        box.AddChild(pymui.HSpace(0))

        # Notebook
        nb = self._nb = pymui.VGroup(Frame='Register',
                                     PageMode=True,
                                     Background='RegisterBack',
                                     muiargs=[(MUIA_Group_PageMax, False)])
        self._titles = pymui.Title(Closable=False, Newable=False)
        nb.AddChild(self._titles)
        nb.Notify('ActivePage', self._on_active_page)
        topbox.AddChild(nb)

        # Add the 'All brushes' page
        self._all = self.add_page('All brushes', close=False)

        # Add brushes
        l =  Brush.load_brushes()
        for brush in l:
            self.add_brush(brush, brush.page)
        self.active_brush = l[0]

        self._del_page_bt.Disable = True
        if len(self._brushes) == 1:
            self._menuitems['delete'].Enabled = False

    def set_current_cb(self, cb):
        self._current_cb = cb

    def add_page(self, name, close=True):
        title = pymui.Text(name, Dropable=True)
        page = laygroup.LayGroup(SameSize=False, Spacing=1)
        page.name = name

        self._top.InitChange()
        self._titles.AddChild(title, lock=True)
        self._nb.AddChild(page, lock=True)
        self._top.ExitChange()

        self._pages.append((page, title))
        self._nb.ActivePage = pymui.MUIV_Group_ActivePage_Last

        return page

    def add_brush(self, brush, pagename=None):
        # Make 2 buttons: one for the "All brushes" page, and another for the current page
        # If current page is the All, only one button is created.
        bt = self._mkbrushbt(self._all, brush)
        bt.allbt = bt
        brush.bt = bt
        self._brushes.add(brush)

        if len(self._brushes) == 2:
            self._menuitems['delete'].Enabled = True

        page = None
        if pagename:
            for o,_ in self._pages:
                if o.name == pagename:
                    page = o
            del o
            if page is None:
                page = self.add_page(pagename)

        page = page or self._pages[self._nb.ActivePage.value][0]
        if page != self._all:
            bt.bt2 = self._mkbrushbt(page, brush)
            bt.bt2.allbt = bt
            brush.page = page.name
        else:
            brush.page = None

        self.ActiveObject = bt
        bt.Selected = True

    def _mkbrushbt(self, page, brush):
        bt = pymui.Dtpic(Frame='ImageButton',
                         Name=brush.icon,
                         ShortHelp=brush.name,
                         #FixWidth=48, FixHeight=48,
                         InputMode='Toggle',
                         CycleChain=True,
                         Draggable=True,
                         ContextMenu=self._brushmenustrip)
        bt.Notify('Selected', self._on_brush_bt_clicked)
        bt.Notify('ContextMenuTrigger', self._on_change_icon, when=self._menuitems['change-icon']._object)
        bt.Notify('ContextMenuTrigger', self._on_delete_brush, when=self._menuitems['delete']._object)
        bt.page = page
        bt.brush = brush
        bt.bt2 = None # button in another page if it has been added

        page.AddChild(bt, lock=True)

        return bt

    def _on_add_page(self, evt):
        self.add_page('New page')

    def _on_del_page(self, evt):
        n = self._nb.ActivePage.value
        page, title = self._pages.pop(n)

        self._top.InitChange()
        self._nb.InitChange()
        self._nb.RemChild(page)
        self._titles.InitChange()
        self._titles.RemChild(title)
        self._titles.ExitChange()
        self._nb.ExitChange()
        self._top.ExitChange()

        self._nb.ActivePage = max(0, n-1)

        if page is not self._all:
            for brush in self._brushes:
                brush.page = None
                brush.bt.bt2 = None

    def _on_active_page(self, evt):
        page = self._pages[self._nb.ActivePage.value][0]
        if self._all:
            if self._all is page:
                self._del_page_bt.Disabled = True
            else:
                self._del_page_bt.Disabled = False

    def _on_new_brush(self, evt):
        self.add_brush(Brush())

    def _on_save_all(self, evt):
        Brush.save_brushes(self._brushes)

    def _on_brush_bt_clicked(self, evt):
        bt = evt.Source
        if bt.Selected.value:
            if bt is bt.allbt:
                if bt.bt2 and not bt.bt2.Selected.value:
                    bt.bt2.Selected = True
            elif not bt.allbt.Selected.value:
                bt.allbt.Selected = True

            old = self._current
            self._current = bt.allbt

            if old and old is not bt.allbt:
                old.Selected = False
                if old.bt2:
                    old.bt2.Selected = False

            self._current_cb(self._current.brush)
        elif self._current is bt.allbt:
            bt.NNSet('Selected', True)
            pymui.GetApp().open_brush_editor()

    def _on_change_icon(self, evt):
        bt = evt.Source.allbt
        filename = pymui.GetApp().get_image_filename(parent=self)
        if filename:
            self._top.InitChange()
            bt.Name = filename
            bt.brush.icon = filename
            if bt.bt2:
                bt.bt2.Name = filename
            self._top.ExitChange()

    def _on_delete_brush(self, evt):
        bt = evt.Source.allbt
        self._top.InitChange()
        bt.page.RemChild(bt, lock=True)
        if bt.bt2:
            bt.bt2.page.RemChild(bt.bt2, lock=True)
        self._top.ExitChange()
        self._brushes.remove(bt.brush)
        if len(self._brushes) == 1:
            self._menuitems['delete'].Enabled = False

    def _set_active_brush(self, brush):
        brush.bt.Selected =True

    active_brush = property(fget=lambda self: self._current.brush, fset=_set_active_brush)


class BrushHouseWindowMediator(Mediator):
    NAME = "BrushHouseWindowMediator"

    #### Private API ####

    def __init__(self, component):
        assert isinstance(component, BrushHouseWindow)
        super(BrushHouseWindowMediator, self).__init__(viewComponent=component)

        self._docproxy = None # active document
        component.set_current_cb(self._on_brush_selected)

    def _on_brush_selected(self, brush):
        #print "[BH] active brush:", brush
        self._docproxy.brush = brush # this cause docproxy to copy brush data to the document drawable brush

    ### notification handlers ###

    @mvcHandler(main.Gribouillis.DOC_ACTIVATED)
    def _on_activate_document(self, docproxy):
        # keep silent if no change
        if docproxy is self._docproxy: return
        self._docproxy = docproxy

        # Check if the document has a default brush, assign current default one if not
        if not docproxy.brush:
            #print "[BH] new doc, default brush is %s" % self.viewComponent.active_brush
            docproxy.brush = self.viewComponent.active_brush
        else:
            # change current active brush by the docproxy one
            self.viewComponent.active_brush = docproxy.brush

    @mvcHandler(main.Gribouillis.DOC_DELETE)
    def _on_delete_document(self, docproxy):
        if docproxy is self._docproxy:
            self._docproxy = None

    @mvcHandler(main.Gribouillis.BRUSH_PROP_CHANGED)
    def _on_brush_prop_changed(self, brush, name):
        if name is 'color': return
        setattr(self._docproxy.brush, name, getattr(brush, name))


