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

import pygtk
pygtk.require('2.0')
import gtk

import main, view, utils
from utils import mvcHandler

from layermgr import *
from cmdhistoric import *
from brusheditor import *
from brushhouse import *
from colorwindow import *

__all__ = ['Application', 'ApplicationMediator']


class Application(view.mixin.ApplicationMixin):
    __metaclass__ = utils.MetaSingleton

    _last_filename = None

    def __init__(self):
        self._open_doc = None # last open document filename
        self.create_ui()

    def create_ui(self):
        self.layermgr = LayerManager()
        self.cmdhist = CommandsHistoryList()
        self.brusheditor = BrushEditorWindow()
        self.brushhouse = BrushHouseWindow()
        self.colorwin = ColorWindow()

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


from docviewer import *

class ApplicationMediator(utils.Mediator):
    NAME = "ApplicationMediator"

    document_mediator = None

    #### Private API ####

    def __init__(self, component):
        assert isinstance(component, Application)
        super(ApplicationMediator, self).__init__(ApplicationMediator.NAME, component)

    def onRegister(self):
        self.facade.registerMediator(DialogMediator(self.viewComponent))
        self.facade.registerMediator(LayerManagerMediator(self.viewComponent.layermgr))
        self.facade.registerMediator(CommandsHistoryListMediator(self.viewComponent.cmdhist))
        self.facade.registerMediator(BrushHouseWindowMediator(self.viewComponent.brushhouse))
        self.facade.registerMediator(BrushEditorWindowMediator(self.viewComponent.brusheditor))
        self.facade.registerMediator(ColorWindowMediator(self.viewComponent.colorwin))

        self.document_mediator = DocumentMediator(self.viewComponent)
        self.facade.registerMediator(self.document_mediator)

    def get_document_filename(self, parent=None):
        return self.viewComponent.get_filename(parent)

    ### notification handlers ###

    @mvcHandler(main.Gribouillis.QUIT)
    def _on_quit(self, note):
        # TODO: check for modified documents
        self.viewComponent.quit()

    #### Public API ####

    def delete_docproxy(self, docproxy):
        self.document_mediator.delete_docproxy(docproxy)

        # Close the application on last document close event.
        if len(self.document_mediator) == 0:
            self.viewComponent.quit()


class DialogMediator(utils.Mediator):
    NAME = "DialogMediator"

    def show_dialog(self, type, msg):
        dlg = gtk.MessageDialog(self.viewComponent,
                                type=type,
                                buttons=gtk.BUTTONS_OK,
                                message_format=msg)
        dlg.run()
        dlg.destroy()

    #### notification handlers ####

    @mvcHandler(main.Gribouillis.SHOW_ERROR_DIALOG)
    def on_show_error(self, msg):
        self.show_dialog(gtk.MESSAGE_ERROR, msg)

    @mvcHandler(main.Gribouillis.SHOW_WARNING_DIALOG)
    def on_show_warning(self, msg):
        self.show_dialog(gtk.MESSAGE_WARNING, msg)

    @mvcHandler(main.Gribouillis.SHOW_INFO_DIALOG)
    def on_show_info(self, msg):
        self.show_dialog(gtk.MESSAGE_INFO, msg)

