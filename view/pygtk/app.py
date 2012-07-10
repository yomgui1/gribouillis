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

import gtk

import view
import utils
import main

from utils import _T
from view.contexts import action

#from layermgr import *
#from cmdhistoric import *
#from brusheditor import *
#from brushhouse import *
#from colorwindow import *

__all__ = ['Application']


class Application(view.mixin.ApplicationMixin):
    __metaclass__ = utils.MetaSingleton

    _last_filename = None

    def __init__(self):
        self._open_doc = None # last open document filename
        self.create_ui()

    def create_ui(self):
        self.windows = {}

    def run(self):
        gtk.main()

    def quit(self):
        gtk.main_quit()

    def open_brush_editor(self):
        self.brusheditor.present()

    def open_brush_house(self):
        self.brushhouse.present()

    def open_layer_mgr(self):
        self.layermgr.present()

    def open_cmdhistoric(self):
        self.cmdhist.present()

    def open_colorwin(self):
        self.colorwin.present()

    def toggle_cmdhistoric(self):
        if self.cmdhist.get_visible():
            self.cmdhist.hide()
        else:
            self.cmdhist.present()

    def toggle_brush_editor(self):
        if self.brusheditor.get_visible():
            self.brusheditor.hide()
        else:
            self.brusheditor.present()

    def toggle_brush_house(self):
        if self.brushhouse.get_visible():
            self.brushhouse.hide()
        else:
            self.brushhouse.present()

    def toggle_color_mgr(self):
        if self.colorwin.get_visible():
            self.colorwin.hide()
        else:
            self.colorwin.present()

    def toggle_layer_mgr(self):
        if self.layermgr.get_visible():
            self.layermgr.hide()
        else:
            self.layermgr.present()

    def select_filename(self, title, parent=None, read=True):
        if read:
            action = gtk.FILE_CHOOSER_ACTION_OPEN
        else:
            action = gtk.FILE_CHOOSER_ACTION_SAVE

        dlg = gtk.FileChooserDialog(title, parent, action,
                                    (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                     (gtk.STOCK_OPEN if read else gtk.STOCK_SAVE), gtk.RESPONSE_OK))
        if self._last_filename:
            dlg.set_filename(self._last_filename)

        try:
            if dlg.run() == gtk.RESPONSE_OK:
                self._last_filename = dlg.get_filename()
                return self._last_filename
        finally:
            dlg.destroy()

    def get_document_filename(self, *a, **k):
        return self.select_filename('Open Document', *a, **k)

    def get_image_filename(self, *a, **k):
        return self.select_filename('Select Image', *a, **k)

    def get_new_document_type(self, vo, parent=None):
        dlg = gtk.Dialog("New Document", parent,
                         buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                  gtk.STOCK_NEW, gtk.RESPONSE_OK))

        # Doc name
        hbox = gtk.HBox()
        dlg.vbox.pack_start(hbox)
        hbox.pack_start(gtk.Label("Document name:"))

        name = gtk.Entry()
        hbox.pack_start(name)
        name.set_text(vo.name)

        hbox.show_all()

        # ComboBox
        combo = gtk.combo_box_new_text()
        dlg.vbox.pack_start(combo)

        # Add entries
        combo.append_text("Select document type:")
        for text in ['RGB']:
            combo.append_text(text)
        combo.set_active(0)
        combo.show()

        # run and check response
        response = dlg.run()
        if (response == gtk.RESPONSE_OK) and (combo.get_active() > 0):
            vo.name = name.get_text()
            vo.colorspace = combo.get_active_text()
        else:
            vo = None

        dlg.destroy()
        return vo

    def close_all_non_drawing_windows(self):
        self.layermgr.hide()
        self.cmdhist.hide()
        self.brusheditor.hide()
        self.brushhouse.hide()
        self.colorwin.hide()

# Actions
#

@action(_T('open color manager window'))
def action_open_colorwin(context, evt):
    context.app.open_colorwin()

@action(_T('open brush house window'))
def action_open_brush_house(context, evt):
    context.app.open_brush_house()

@action(_T('open brush editor window'))
def action_open_brush_editor(context, evt):
    context.app.open_brush_editor()

@action(_T('open commands historic window'))
def action_open_cmdhist(context, evt):
    context.app.open_cmdhistoric()

@action(_T('open layer manager window'))
def action_open_layer_mgr(context, evt):
    context.app.open_layer_mgr()

@action(_T('open preferences window'))
def action_open_preferences(context, evt):
    context.app.open_preferences()

@action(_T('toggle color manager window'))
def action_toggle_colorwin(context, evt):
    context.app.toggle_color_mgr()

@action(_T('toggle brush house window'))
def action_toggle_brush_house(context, evt):
    context.app.toggle_brush_house()

@action(_T('toggle brush editor window'))
def action_toggle_brush_editor(context, evt):
    context.app.toggle_brush_editor()

@action(_T('toggle commands historic window'))
def action_toggle_cmdhist(context, evt):
    context.app.toggle_cmdhistoric()

@action(_T('toggle layer manager window'))
def action_toggle_layer_mgr(context, evt):
    context.app.toggle_layer_mgr()

@action(_T('cleanup workspace'))
def cleanup_workspace(context, evt):
    context.app.close_all_non_drawing_windows()
