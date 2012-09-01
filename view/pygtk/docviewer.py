###############################################################################
# Copyright (c) 2009-2012 Guillaume Roguez
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
import gobject

from view.context2 import Context
from .viewport import DocViewport
from .contexts import DocWindowCtx
from .app import Application

from utils import _T

gdk = gtk.gdk


def _menu_signal(name):
    return gobject.signal_new(name, gtk.Window,
                              gobject.SIGNAL_ACTION,
                              gobject.TYPE_BOOLEAN, ())

# signal used to communicate between viewer's menu and document mediator
sig_menu_quit                = _menu_signal('menu_quit')
sig_menu_new_doc             = _menu_signal('menu_new_doc')
sig_menu_load_doc            = _menu_signal('menu_load_doc')
sig_menu_save_doc            = _menu_signal('menu_save_doc')
sig_menu_close_doc           = _menu_signal('menu_close_doc')
sig_menu_clear_layer         = _menu_signal('menu_clear_layer')
sig_menu_load_background     = _menu_signal('menu_load_background')
sig_menu_load_image_as_layer = _menu_signal('menu_load_image_as_layer')


class DocWindow(gtk.Window):
    #### Private API ####

    __title_fmt = _T("Document: %s")
    ui = """<ui>
        <menubar name="MenuBar">
            <menu action='File'>
                <menuitem action="new-doc"/>
                <menuitem action="open-doc"/>
                <menuitem action="save-doc"/>
                <menuitem action="close-doc"/>
                <separator/>
                <menuitem action="quit"/>
            </menu>
            <menu action='Edit'>
                <menuitem action="cmd-undo"/>
                <menuitem action="cmd-redo"/>
                <menuitem action="cmd-flush"/>
                <menuitem action="cmd-win"/>
            </menu>
            <menu action='View'>
                <menuitem action="view-load-background"/>
            </menu>
            <menu action='Layers'>
                <menuitem action="layers-win"/>
                <menuitem action="layers-load-image"/>
                <menuitem action="layers-clear-active"/>
            </menu>
            <menu action='Color'>
                <menuitem action="color-win"/>
                <menuitem action="assign-profile"/>
                <menuitem action="convert-profile"/>
            </menu>
            <menu action='Tools'>
                <menuitem action="brush-house-win"/>
                <menuitem action="brush-win"/>
                <menuitem action="brush-radius-inc"/>
                <menuitem action="brush-radius-dec"/>
                <separator/>
                <menuitem action="line-ruler-toggle"/>
                <menuitem action="ellipse-ruler-toggle"/>
                <menuitem action="navigator-toggle"/>
            </menu>
        </menubar>
        </ui>
        """
    
    def __init__(self, docproxy):
        super(DocWindow, self).__init__()

        self.viewports = []
        self.docproxy = docproxy
        self._ctx = Context(DocWindowCtx,
                            app=Application(),
                            window=self,
                            docproxy=docproxy)

        # UI
        uimanager = gtk.UIManager()
        accelgroup = uimanager.get_accel_group()
        self.add_accel_group(accelgroup)

        uimanager.add_ui_from_string(DocWindow.ui) ## UI description

        self._topbox = topbox = gtk.VBox(False, 1)
        topbox.set_border_width(1)
        self.add(topbox)

        # Actions
        actiongroup = gtk.ActionGroup('GribouillisActionGroup')
        self.actiongroup = actiongroup

        actiongroup.add_actions([
                # Menu Titles
                ('File', None, _T('Gribouillis')),
                ('Edit', None, _T('Edit')),
                ('Layers', None, _T('Layers')),
                ('Brush', None, _T('Brush')),
                ('Color', None, _T('Color')),
                ('View', None, _T('View')),
                ('Tools', None, _T('Tools')),

                # Sub-menu items
                ('new-doc', gtk.STOCK_NEW, _T('New Document...'),
                 None, None,
                 lambda *a: self.emit('menu_new_doc')),

                ('open-doc', gtk.STOCK_OPEN, _T('Open Document...'),
                 None, None,
                 lambda *a: self.emit('menu_load_doc')),

                ('save-doc', gtk.STOCK_SAVE, _T('Save Document...'),
                 None, None,
                 lambda *a: self.emit('menu_save_doc')),

                ('close-doc', gtk.STOCK_CLOSE, _T('Close Document'),
                 None, None,
                 lambda *a: self.emit('menu_close_doc')),

                ('quit', gtk.STOCK_QUIT, _T('Quit!'),
                 None, None,
                 lambda *a: self.emit('menu_quit')),

                ('cmd-undo', gtk.STOCK_UNDO, _T('Undo last command'),
                 '<Control>z', None,
                 lambda *a: self._ctx.execute("doc-hist-undo")),

                ('cmd-redo', gtk.STOCK_REDO, _T('Redo last command'),
                 '<Control><Shift>z', None,
                 lambda *a: self._ctx.execute("doc-hist-redo")),

                ('cmd-flush', gtk.STOCK_APPLY, _T('Flush commands historic'),
                 '<Control><Alt>z', None,
                 lambda *a: self._ctx.execute("doc-hist-flush")),

                ('cmd-win', gtk.STOCK_PROPERTIES, _T('Open commands historic'),
                 '<Alt>h', None,
                 None),

                ('layers-load-image', gtk.STOCK_ADD, _T('Load image as new layer...'),
                 '<Control><Alt>z', None,
                 lambda *a: self.emit('menu_load_image_as_layer')),

                ('layers-win', gtk.STOCK_PROPERTIES, _T('Open layers list window'),
                 '<Control>l', None,
                 None),

                ('layers-clear-active', gtk.STOCK_CLEAR, _T('Clear active layer'),
                 '<Control>k', None,
                 lambda *a: self.emit('menu_clear_layer')),

                ('view-load-background', None, _T('Load background image'),
                 '<Control><Alt>b', None,
                 lambda *a: self.emit('menu_load_background')),

                ('color-win', gtk.STOCK_PROPERTIES, _T('Open color editor'),
                 '<Control>c', None,
                 None),

                ('brush-house-win', None, _T('Open brush house window'),
                 None, None,
                 None),

                ('brush-win', gtk.STOCK_PROPERTIES, _T('Edit brush properties'),
                 '<Control>b', None,
                 None),
                
                ('brush-radius-inc', gtk.STOCK_ADD, _T('Increase brush size'),
                 'plus', None,
                 lambda *a: self._ctx.execute("increase-brush-radius")),

                ('brush-radius-dec', gtk.STOCK_REMOVE, _T('Decrease brush size'),
                 'minus', None,
                 lambda *a: self._ctx.execute("decrease-brush-radius")),

                ('line-ruler-toggle', None, _T('Toggle line ruler'),
                 None, None,
                 None),

                ('ellipse-ruler-toggle', None, _T('Toggle ellipse ruler'),
                 None, None,
                 None),

                ('navigator-toggle', None, _T('Toggle Navigator'),
                 None, None,
                 None),

                ('assign-profile', None, _T('Assign Color Profile'),
                 None, None,
                 None),

                ('convert-profile', None, _T('Convert to Color Profile'),
                 None, None,
                 None),

            #('', None, '', None, None, callable),
            ])

        #actiongroup.add_toggle_actions([
        #    ])

        uimanager.insert_action_group(actiongroup, 0)

        # MenuBar
        menubar = uimanager.get_widget('/MenuBar')
        topbox.pack_start(menubar, False)

        # Default viewport
        vp = DocViewport(self, docproxy, self._ctx)
        self._add_vp(vp)

        vp = DocViewport(self, docproxy, self._ctx)
        self._add_vp(vp)

        #self.set_can_focus(True)
        self.move(0, 0)
        self.set_default_size(600, 400)
        self.show_all()

        # UI is ready to show doc properties
        self.proxy_updated()

    def _add_vp(self, vp):
        self.viewports.append(vp)
        self._topbox.pack_start(vp, True, True, 0)
        self.vp = vp

    #### Public API ####

    def proxy_updated(self):
        "Update window properties build on doc proxy ones"
        self.set_doc_name(self.docproxy.docname)

    def set_doc_name(self, name):
        self.set_title(self.__title_fmt % name)

    def confirm_close(self):
        dlg = gtk.Dialog(_T("Sure?"), self,
                         gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                         (gtk.STOCK_YES, gtk.RESPONSE_OK,
                          gtk.STOCK_NO, gtk.RESPONSE_CANCEL))
        dlg.set_default_response(gtk.RESPONSE_CANCEL)
        response = dlg.run()
        dlg.destroy()
        return response == gtk.RESPONSE_OK

    def load_background(self, evt=None):
        filename = Application().get_image_filename(parent=self)
        if filename:
            self.vp.set_background(filename)

    def assign_icc(self):
        dlg = AssignCMSDialog(self.docproxy, self)
        result = dlg.run()
        if result == gtk.RESPONSE_OK:
            self.docproxy.profile = dlg.get_profile()
        dlg.destroy()

    def convert_icc(self):
        dlg = ConvertDialog(self.docproxy, self)
        result = dlg.run()
        if result == gtk.RESPONSE_OK:
            dst_profile = dlg.get_destination()
            src_profile = self.docproxy.profile
            ope = Transform(src_profile, dst_profile)
            self.vp.apply_ope(ope)
            self.vp.redraw()
        dlg.destroy()
