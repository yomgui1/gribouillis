
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

import gtk, gobject
import gtk.gdk as gdk

import main, model, utils, view

from utils import mvcHandler, Mediator
from model.brush import Brush
from .common import SubWindow

__all__ = [ 'BrushHouseWindow', 'BrushHouseWindowMediator' ]

TABLE_WIDTH = 5

class BrushHouseWindow(SubWindow):
    _current_cb = utils.idle_cb

    def __init__(self):
        super(BrushHouseWindow, self).__init__()

        self.set_title('Brushes House')

        self._brushes = set()
        self._all = None
        self._current = None

        # UI
        topbox = gtk.VBox()
        self.add(topbox)

        uimanager = gtk.UIManager()
        accelgroup = uimanager.get_accel_group()
        self.add_accel_group(accelgroup)

        ui = '''<ui>
        <popup name="IconMenu">
            <menuitem action='delete'/>
        </popup>
        </ui>
        '''
        uimanager.add_ui_from_string(ui)

        # Actions
        actiongroup = gtk.ActionGroup('BrushHouseAG')
        self.actiongroup = actiongroup

        actiongroup.add_actions([
            ('delete', gtk.STOCK_DELETE, 'Delete', None, None, lambda *a: self.del_brush(self._popup_bt)),
            ])

        uimanager.insert_action_group(actiongroup, 0)

        self._bt_menu_popup = uimanager.get_widget('/IconMenu')

        # Pages controls
        box = gtk.HButtonBox()
        box.set_layout(gtk.BUTTONBOX_START)
        topbox.pack_start(box, False)

        bt = gtk.Button('New page')
        box.add(bt)
        bt.connect('clicked', self._on_add_page)

        bt = self._del_page_bt = gtk.Button('Delete page')
        box.add(bt)
        bt.connect('clicked', self._on_del_page)

        bt = gtk.Button('New brush')
        box.add(bt)
        bt.connect('clicked', self._on_new_brush)

        bt = gtk.Button('Save all')
        box.add(bt)
        bt.connect('clicked', self._on_save_all)

        # Notebook
        nb = self._nb = gtk.Notebook()
        nb.set_tab_pos(gtk.POS_TOP)
        nb.set_scrollable(True)
        nb.connect('switch-page', self._on_switch_page)

        topbox.add(nb)

        topbox.show_all()

        # Add the 'All brushes' page
        self._all = self.add_page('All brushes')

        # Add brushes
        l = Brush.load_brushes()
        for brush in l:
            self.add_brush(brush, brush.page)
        self.active_brush = l[0]

        self._del_page_bt.set_sensitive(False)
        self.set_default_size(300, 200)

    def set_current_cb(self, cb):
        self._current_cb = cb

    def add_page(self, name):
        frame = gtk.Frame()
        frame._name = name

        t = frame.table = gtk.Table(TABLE_WIDTH, homogeneous=True)
        frame.add(frame.table)
        frame.show_all()

        t.count = 0

        label = gtk.Label(name)
        label.show()

        n = self._nb.append_page(frame, label)
        self._nb.set_tab_reorderable(frame, True)
        self._nb.set_current_page(n)

        return frame

    def add_brush(self, brush, pagename=None):
        # Make 2 buttons: one for the "All brushes" page, and another for the current page
        # If current page is the All, only one button is created.
        bt = self._mkbrushbt(self._all, brush)
        bt.allbt = bt
        brush.bt = bt
        self._brushes.add(brush)

        page = None
        if pagename:
            for o in self._pages:
                if o._name == pagename:
                    page = o
            del o
            if page is None:
                page = self.add_page(pagename)

        page = page or self._nb.get_nth_page(self._nb.get_current_page())
        if page != self._all:
            bt.bt2 = self._mkbrushbt(page, brush)
            bt.bt2.allbt = bt
            brush.page = page._name
        else:
            brush.page = None

        bt.clicked()

    def del_brush(self, bt):
        pass # TODO

    def _on_add_page(self, evt):
        self.add_page('New page')

    def _on_del_page(self, evt):
        self._nb.remove_page(self._nb.get_current_page())

    def _on_switch_page(self, evt, page, n):
        if self._all == self._nb.get_nth_page(n):
            self._del_page_bt.set_sensitive(False)
        else:
            self._del_page_bt.set_sensitive(True)

    def _mkbrushbt(self, frame, brush):
        bt = gtk.ToggleButton()
        bt.set_image(gtk.image_new_from_file(brush.icon))
        bt.set_size_request(60, 60)
        bt.show_all()
        bt.connect('clicked', self._on_brush_bt_clicked)
        bt.connect('button-release-event', self._on_brush_bt_released)
        bt.brush = brush
        bt.bt2 = None # button in another page if it has been added

        t = frame.table
        x = t.count % TABLE_WIDTH
        y = t.count / TABLE_WIDTH
        frame.table.attach(bt, x, x+1, y, y+1, gtk.FILL, gtk.FILL, 1, 1)
        t.count += 1

        return bt

    def _on_new_brush(self, evt):
        self.add_brush(Brush())

    def _on_save_all(self, evt):
        Brush.save_brushes(self._brushes)

    def _on_brush_bt_released(self, bt, evt):
        if evt.button == 3:
            self._popup_bt = bt
            self._bt_menu_popup.popup(None, None, None, 3, evt.time)
            return True

    def _on_brush_bt_clicked(self, bt):
        if bt.get_active():
            if bt is bt.allbt:
                if bt.bt2 and not bt.bt2.get_active():
                    bt.bt2.set_active(True)
            elif not bt.allbt.get_active():
                bt.allbt.set_active(True)

            old = self._current
            self._current = bt.allbt

            if old and old is not bt.allbt:
                old.set_active(False)
                if old.bt2:
                    old.bt2.set_active(False)

            self._current_cb(self._current.brush)
        elif self._current is bt.allbt:
            bt.set_active(True)
            #pymui.GetApp().open_brush_editor()

    active_brush = property(fget=lambda self: self._current.brush,
                            fset=lambda self, brush: brush.bt.set_active(True))


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
