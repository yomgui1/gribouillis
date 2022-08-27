
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

import cairo
import pymui
from pymui.mcc import laygroup
from pymui.mcc import rawimage

import main
import model
import utils
import view
import view.context as ctx

from utils import _T, resolve_path
from model.brush import Brush, DrawableBrush
from model.document import Document
from model import _pixbuf, prefs

__all__ = [ 'BrushHouseWindow' ]

MUIA_Group_PageMax = 0x8042d777 # /* V4  i.. BOOL              */ /* private */

_BRUSH_PREVIEW_BACK = "5:" + resolve_path(main.Gribouillis.TRANSPARENT_BACKGROUND)

surf = cairo.ImageSurface.create_from_png(resolve_path(main.Gribouillis.TRANSPARENT_BACKGROUND))
_PREVIEW_BACK_PAT = cairo.SurfacePattern(surf)
_PREVIEW_BACK_PAT.set_extend(cairo.EXTEND_REPEAT)
_PREVIEW_BACK_PAT.set_filter(cairo.FILTER_NEAREST)
del surf

class BrushHouseWindow(pymui.Window):
    _current_cb = utils.idle_cb
    _eraser_set_cb = utils.idle_cb

    def __init__(self, name):
        super(BrushHouseWindow, self).__init__(name,
                                               ID='BRHO',
                                               LeftEdge=0,
                                               TopDeltaEdge=0,
                                               CloseOnReq=True)
        self.name = name

        self._brushes = set()
        self._all = None
        self._current = None
        self._pages = []
        self._drawbrush = DrawableBrush() # used for preview

        # UI
        self._top = topbox = self.RootObject = pymui.VGroup()

        # Brush context menu
        self._brushmenustrip = pymui.Menustrip()
        menu = pymui.Menu(_T('Brush actions'))
        self._brushmenustrip.AddTail(menu)

        self._menuitems = {}
        for k, text in [('use-preview-icon', _T('Use preview icon')),
                        ('use-image-icon', _T('Use image icon')),
                        ('change-icon', _T('Change image icon...')),
                        ('as-eraser', _T('As eraser brush...')),
                        ('dup', _T('Duplicate')),
                        ('delete', _T('Delete'))]:
            o = self._menuitems[k] = pymui.Menuitem(text)
            menu.AddChild(o)

        # Pages controls
        box = pymui.HGroup()
        topbox.AddChild(box)

        bt = pymui.SimpleButton(_T('New page'), Weight=0)
        box.AddChild(bt)
        bt.Notify('Pressed', self._on_add_page, when=False)

        bt = self._del_page_bt = pymui.SimpleButton(_T('Delete page'), Weight=0, Disabled=True)
        box.AddChild(bt)
        bt.Notify('Pressed', self._on_del_page, when=False)

        bt = pymui.SimpleButton(_T('New brush'), Weight=0)
        box.AddChild(bt)
        bt.Notify('Pressed', self._on_new_brush, when=False)

        bt = pymui.SimpleButton(_T('Save all'), Weight=0)
        box.AddChild(bt)
        bt.Notify('Pressed', self._on_save_all, when=False)

        box.AddChild(pymui.HSpace(0))

        # Notebook
        nb = self._nb = pymui.VGroup(Frame='Register',
                                     PageMode=True,
                                     Background='RegisterBack',
                                     CycleChain=True,
                                     muiargs=[(MUIA_Group_PageMax, False)])
        self._titles = pymui.Title(Closable=False, Newable=False)
        nb.AddChild(self._titles)
        nb.Notify('ActivePage', self._on_active_page)
        topbox.AddChild(nb)
        
        self._pagenamebt = pymui.String(Frame='String', Background='StringBack', Disabled=True, CycleChain=True)
        self._pagenamebt.Notify('Acknowledge', lambda ev, v: self._change_page_name(v), pymui.MUIV_TriggerValue)
        
        self._brushnamebt = pymui.Text(Frame='String', PreParse=pymui.MUIX_C)
        
        grp = pymui.HGroup(Child=[ pymui.Label(_T('Page name')+':'), self._pagenamebt, pymui.Label(_T('Active brush')+':'), self._brushnamebt ])
        topbox.AddChild(grp)

        # Add the 'All brushes' page
        self._all = self.add_page(_T('All brushes'), close=False)

        self._del_page_bt.Disable = True
        if len(self._brushes) == 1:
            self._menuitems['delete'].Enabled = False

    def set_current_cb(self, cb):
        self._current_cb = cb
        
    def set_eraser_set_cb(self, cb):
        self._eraser_set_cb = cb

    def add_page(self, name, close=True):
        # page name is unique...
        for page, title in self._pages:
            if page.name == name:
                return page
                
        title = pymui.Text(name, Dropable=True)
        page = laygroup.LayGroup(SameSize=False, Spacing=1, InnerSpacing=0)
        page.name = name

        self._top.InitChange()
        self._titles.AddChild(title, lock=True)
        self._nb.AddChild(pymui.Scrollgroup(Contents=page, NoHorizBar=True), lock=True)
        self._top.ExitChange()

        self._pages.append((page, title))
        self._nb.ActivePage = pymui.MUIV_Group_ActivePage_Last

        return page

    def add_brush(self, brush, page=None, name=None):
        # Make 2 buttons: one for the "All brushes" page, and another for the current page
        # If current page is the All, only one button is created.
        bt = self._mkbrushbt(self._all, brush)
        bt.allbt = bt
        brush.bt = bt
        self._brushes.add(bt)
        
        # Obtain a valid page object
        if page is None:
            if name:
                page = self.add_page(name)
            else:
                page = self._all
                
        if page != self._all:
            bt.bt2 = self._mkbrushbt(page, brush)
            bt.bt2.allbt = bt
            brush.group = page.name
        else:
            brush.group = None
            
        if len(self._brushes) == 2:
            self._menuitems['delete'].Enabled = True

        #self.ActiveObject = bt
        bt.Selected = True

    def _preview_icon_buffer(self, brush):
        self._drawbrush.set_from_brush(brush)
        self._drawbrush.smudge = 0.
        width = 128
        height = 60
        buf = self._drawbrush.paint_rgb_preview(width, height, fmt=_pixbuf.FORMAT_ARGB8)
        
        # Compose with a checker background
        cr = cairo.Context(cairo.ImageSurface.create_for_data(buf, cairo.FORMAT_ARGB32, width, height))
        cr.set_operator(cairo.OPERATOR_DEST_OVER)
        cr.set_source(_PREVIEW_BACK_PAT)
        cr.paint()
        
        return buf
    
    def _load_brush_icon_for_rawimage(self, brush):
        buf, w, h, stride = Document.load_image(brush.icon, 'RGB')
        brush.icon_preview = buf
        data = rawimage.mkRawimageData(w, h, buf, rawimage.RAWIMAGE_FORMAT_RAW_RGB_ID)
        return data
        
    def _mkbrushbt(self, page, brush):
        if brush.icon:
            data = self._load_brush_icon_for_rawimage(brush)
            bt = rawimage.Rawimage(int(data),
                                   Frame='None',
                                   InputMode='Toggle',
                                   InnerSpacing=2)
            bt.ri_data = data
        else:
            if not brush.icon_preview:
                brush.icon_preview = self._preview_icon_buffer(brush)
            buf = brush.icon_preview
            data = rawimage.mkRawimageData(buf.width, buf.height, str(buffer(buf)))
            bt = rawimage.Rawimage(int(data),
                                   Frame='None',
                                   InputMode='Toggle',
                                   InnerSpacing=2)
            bt.ri_data = data

        bt.Background = 'ImageButtonBack'
        bt.ShortHelp = brush.name
        bt.CycleChain = True
        bt.Draggable = True
        bt.ContextMenu = self._brushmenustrip
        
        bt.Notify('Selected', self._on_brush_bt_clicked)
        bt.Notify('ContextMenuTrigger', self._on_preview_icon, when=self._menuitems['use-preview-icon']._object)
        bt.Notify('ContextMenuTrigger', self._on_image_icon, when=self._menuitems['use-image-icon']._object)
        bt.Notify('ContextMenuTrigger', self._on_change_icon, when=self._menuitems['change-icon']._object)
        bt.Notify('ContextMenuTrigger', self._on_dup_brush, when=self._menuitems['dup']._object)
        bt.Notify('ContextMenuTrigger', self._on_delete_brush, when=self._menuitems['delete']._object)
        bt.Notify('ContextMenuTrigger', self._on_as_eraser, when=self._menuitems['as-eraser']._object)
        
        bt.page = page
        bt.brush = brush
        bt.bt2 = None # button in another page if it has been added

        page.AddChild(bt, lock=True)

        return bt

    def _on_add_page(self, evt):
        self.add_page(name='New page')

    def _on_del_page(self, evt):
        n = self._nb.ActivePage.value
        page, title = self._pages.pop(n)

        self._top.InitChange()
        self._nb.RemChild(page.Parent.object)
        self._titles.RemChild(title)
        self._top.ExitChange()

        self._nb.ActivePage = max(0, n-1)

        if page is not self._all:
            for bt in list(self._brushes):
                if bt.page is page.name:
                    self._brushes.remove(bt)
        
    def _on_active_page(self, evt):
        page = self._pages[self._nb.ActivePage.value][0]
        self._pagenamebt.NNSet('Contents', page.name)
        if self._all:
            if self._all is page:
                self._pagenamebt.Disabled = True
                self._del_page_bt.Disabled = True
            else:
                self._pagenamebt.Disabled = False
                self._del_page_bt.Disabled = False

    def _on_new_brush(self, evt):
        i = self._nb.ActivePage.value
        self.add_brush(Brush(), page=self._pages[i][0])

    def _on_save_all(self, evt):
        Brush.save_brushes(bt.brush for bt in self._brushes)

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
            ctx.app.open_window('BrushEditor')
            
        self._brushnamebt.Contents = bt.brush.name

    def _on_change_icon(self, evt):
        bt = evt.Source.allbt
        filename = pymui.GetApp().get_image_filename(parent=self)
        if filename:
            self._top.InitChange()
            bt.brush.icon = filename.replace('PROGDIR:', '')
            data = self._load_brush_icon_for_rawimage(bt.brush)
            bt.ri_data = data
            bt.Picture = int(data)
            if bt.bt2:
                bt = bt.bt2
                data = self._load_brush_icon_for_rawimage(bt.brush)
                bt.ri_data = data
                bt.Picture = int(data)
            self._top.ExitChange()

    def _on_delete_brush(self, evt):
        bt = evt.Source.allbt
        self._top.InitChange()
        bt.page.RemChild(bt, lock=True)
        if bt.bt2:
            bt.bt2.page.RemChild(bt.bt2, lock=True)
        self._top.ExitChange()
        self._brushes.remove(bt)
        if len(self._brushes) == 1:
            self._menuitems['delete'].Enabled = False

    def _on_dup_brush(self, evt):
        bt = evt.Source
        brush = Brush()
        brush.set_from_brush(bt.brush)
        self.add_brush(brush, page=bt.page)

    def _on_preview_icon(self, evt):
        bt = evt.Source.allbt
        buf = bt.brush.icon_preview = self._preview_icon_buffer(bt.brush)
        bt.ri_data = rawimage.mkRawimageData(buf.width, buf.height, str(buffer((buf))))
        bt.Picture = int(bt.ri_data)
        if bt.bt2:
            bt.bt2.Picture = int(bt.ri_data)

    def _on_image_icon(self, evt):
        bt = evt.Source.allbt
        if bt.brush.icon:
            data = self._load_brush_icon_for_rawimage(bt.brush)
            bt.ri_data = data
            bt.Picture = int(data)
            if bt.bt2:
                bt.bt2.Picture = int(bt.ri_data)
        else:
            self._on_change_icon(evt)

    def _on_as_eraser(self, evt):
        self._eraser_set_cb(evt.Source.allbt.brush)

    def _set_active_brush(self, brush):
        brush.bt.Selected =True

    def _change_page_name(self, value):
        page, title = self._pages[self._nb.ActivePage.value]
        page.name = title.Contents = value.contents

    def refresh_active(self):
        self._brushnamebt.Contents = self.active_brush.name

    active_brush = property(fget=lambda self: self._current.brush, fset=_set_active_brush)

