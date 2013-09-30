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

import gtk

import view
import utils
import main
import view.context as ctx

from utils import _T

from .layermgr import LayerManager
from .colorwindow import ColorWindow
from .brusheditor import BrushEditorWindow
from .cmdhistoric import CommandsHistoryList
from .brushhouse import BrushHouseWindow

__all__ = ['Application']


class Application(view.mixin.ApplicationMixin):
    __metaclass__ = utils.MetaSingleton

    _last_filename = None

    def __init__(self):
        self._open_doc = None # last open document filename
        self.create_ui()

    def create_ui(self):
        d = ctx.windows = {}
        d['ColorManager'] = ColorWindow()
        d['BrushEditor'] = BrushEditorWindow()
        d['LayerManager'] = LayerManager()
        d['CmdHist'] = CommandsHistoryList()
        d['BrushHouse'] = BrushHouseWindow()

    def run(self):
        gtk.main()

    def quit(self):
        gtk.main_quit()

    def open_window(self, name):
        ctx.windows[name].present()

    def toggle_window(self, name):
        win = ctx.windows[name]
        if win.get_visible():
            win.hide()
        else:
            win.present()

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
        """Open a dialog window to ask document type to user.
        The given DocumentVO is modified accordingly.
        """

        dlg = gtk.Dialog(_T("New Document"), parent,
                         buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                  gtk.STOCK_NEW, gtk.RESPONSE_OK))

        # Document name
        hbox = gtk.HBox()
        dlg.vbox.pack_start(hbox)
        hbox.pack_start(gtk.Label(_T("Document name:")))

        name = gtk.Entry()
        hbox.pack_start(name)
        name.set_text(vo.name)

        hbox.show_all()

        # ComboBox
        combo = gtk.combo_box_new_text()
        dlg.vbox.pack_start(combo)

        # Add entries
        combo.append_text(_T("Select document type:"))
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
        for win in ctx.windows.itervalues:
            win.hide()

