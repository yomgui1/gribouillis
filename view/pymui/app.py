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

import pymui, os

import main, view, model, utils
from model import vo
from utils import Mediator, mvcHandler

from languages import lang_dict
from layermgr import *
from cmdhistoric import *
from colorharmonies import *
from brushhouse import *

__all__ = [ 'Application', 'ApplicationMediator' ]

class Application(pymui.Application, view.mixin.ApplicationMixin):
    LANG = lang_dict['default']

    _open_doc = None # last open document filename

    def __init__(self):
        menu_def = { self.LANG.MenuApp:     ((self.LANG.MenuAppNewDoc,  'N', 'new-doc'),
                                             (self.LANG.MenuAppLoadDoc, 'O', 'load-doc'),
                                             (self.LANG.MenuAppSaveDoc, 'S', 'save-doc'),
                                             None, # Separator
                                             ('Load image as layer...', None, 'load-layer-image'),
                                             None, # Separator
                                             (self.LANG.MenuAppQuit,    'Q', None),
                                             ),
                     self.LANG.MenuEdit:    (('Undo',   'Z', 'undo'),
                                             ('Redo',   'Y', 'redo'),
                                             ('Flush', None, 'flush'),
                                             ),
                     self.LANG.MenuView:    (('Reset',  '=', 'reset-view'),
                                             ('Load background...', None, 'load-background'),
                                             ),
                     self.LANG.MenuLayers:  (('Clear active', 'K', 'clear_layer'),
                                             ),
                     'Tools':               (('Toggle line guide', '1', 'line-guide'),
                                             ('Toggle ellipse guide', '2', 'ellipse-guide'),
                                             ),
                     self.LANG.MenuWindows: (('Layers', 'L', lambda *a: self.layermgr.OpenWindow()),
                                             ('Color Harmonies', 'C', lambda *a: self.colorhrm.OpenWindow()),
                                             ('Commands historic', 'H', lambda *a: self.cmdhist.OpenWindow()),
                                             ('Brush Editor', 'B', lambda *a: self.brusheditor.OpenWindow()),
                                             ('Brush House', None, lambda *a: self.brushhouse.OpenWindow()),
                                             ),
                     }
                     
        self.menu_items = {}
        menustrip = pymui.Menustrip()
        order = (self.LANG.MenuApp, self.LANG.MenuEdit, self.LANG.MenuLayers,
                 self.LANG.MenuView, 'Tools', self.LANG.MenuWindows)
        for k in order:
            v = menu_def[k]
            menu = pymui.Menu(k)
            menustrip.AddTail(menu)

            for t in v:
                if t is None:
                    menu.AddTail(pymui.Menuitem('-')) # Separator
                    continue
                elif t[0][0] == '#': # toggled item
                    title = t[0][1:]
                    item = pymui.Menuitem(title, t[1], Checkit=True)
                    item.title = title
                else:
                    item = pymui.Menuitem(t[0], t[1])
                if callable(t[2]):
                    item.Bind(*t[2:])
                else:
                    self.menu_items[t[2]] = item
                menu.AddTail(item)

        super(Application, self).__init__(
            Title       = "Gribouillis",
            Version     = "$VER: Gribouillis %s (%s)" % (main.VERSION, main.DATE),
            Copyright   = "\xa92009, Guillaume ROGUEZ",
            Author      = "Guillaume ROGUEZ",
            Description = self.LANG.AppliDescription,
            Base        = "Gribouillis",
            Menustrip   = menustrip)

        self.layermgr = LayerMgr()
        self.cmdhist = CommandsHistoryList()
        self.colorhrm = ColorHarmoniesWindow()
        self.brusheditor = BrushEditorWindow()
        self.brushhouse = BrushHouseWindow()

        self.AddChild(self.layermgr)
        self.AddChild(self.cmdhist)
        self.AddChild(self.colorhrm)
        self.AddChild(self.brusheditor)
        self.AddChild(self.brushhouse)

        self.brushhouse.Open = True

    def run(self):
        self.Run()

    def quit(self):
        self.Quit()

    def get_filename(self, title, parent=None, read=True, pat='#?'):
        filename = pymui.GetFilename(parent,
                                     title,
                                     self._open_doc and os.path.dirname(self._open_doc),
                                     pat,
                                     not read)
        if filename:
            self._open_doc = filename[0]
            return self._open_doc

    def get_image_filename(self, pat="#?.(png|jpeg|jpg|targa|tga|gif|ora)", *a, **k):
        return self.get_filename(self.LANG.LoadImageReqTitle, pat=pat, *a, **k)

    def get_document_filename(self, pat="#?.(png|jpeg|jpg|targa|tga|gif|ora)", *a, **k):
        return self.get_filename("Select document filename", pat=pat, *a, **k)

    def get_new_document_type(self, alltypes, parent=None):
        return 'RGB'

    def open_brush_editor(self):
        self.brusheditor.Open = True


from docviewer import *
from brusheditor import *

class ApplicationMediator(Mediator):
    """Application Mediator class.

    Responsible to receive and handle all notifications at Application level, like:
    - closing the application.
    - create new documents on demand.
    - etc
    """

    NAME = "ApplicationMediator"

    document_mediator = None

    #### Private API ####

    def __init__(self, component):
        assert isinstance(component, Application)
        super(ApplicationMediator, self).__init__(ApplicationMediator.NAME, component)

        component.menu_items['undo'].Bind(self._on_cmd_undo)
        component.menu_items['redo'].Bind(self._on_cmd_redo)
        component.menu_items['flush'].Bind(self._on_cmd_flush)
        component.menu_items['new-doc'].Bind(self._on_new_doc)
        component.menu_items['load-doc'].Bind(self._on_load_doc)
        component.menu_items['save-doc'].Bind(self._on_save_doc)
        component.menu_items['clear_layer'].Bind(self._on_clear_active_layer)
        component.menu_items['load-background'].Bind(self._on_load_background)
        component.menu_items['reset-view'].Bind(self._on_reset_view)
        component.menu_items['load-layer-image'].Bind(self._on_load_image_as_layer)
        component.menu_items['line-guide'].Bind(self._on_line_guide)
        component.menu_items['ellipse-guide'].Bind(self._on_ellipse_guide)

    def onRegister(self):
        self.facade.registerMediator(DialogMediator(self.viewComponent))
        self.facade.registerMediator(LayerMgrMediator(self.viewComponent.layermgr))
        self.facade.registerMediator(CommandsHistoryListMediator(self.viewComponent.cmdhist))
        self.facade.registerMediator(ColorHarmoniesWindowMediator(self.viewComponent.colorhrm))
        self.facade.registerMediator(BrushEditorWindowMediator(self.viewComponent.brusheditor))
        self.facade.registerMediator(BrushHouseWindowMediator(self.viewComponent.brushhouse))

        self.document_mediator = DocumentMediator(self.viewComponent)
        self.facade.registerMediator(self.document_mediator)

    def get_document_filename(self, parent=None):
        return self.viewComponent.get_document_filename(parent)

    def _on_cmd_undo(self, evt):
        self.sendNotification(main.Gribouillis.UNDO)

    def _on_cmd_redo(self, evt):
        self.sendNotification(main.Gribouillis.REDO)

    def _on_cmd_flush(self, evt):
        self.sendNotification(main.Gribouillis.FLUSH)

    def _on_new_doc(self, evt):
        vo = model.vo.EmptyDocumentConfigVO('New document')
        if self.viewComponent.get_new_document_type(vo):
            self.sendNotification(main.Gribouillis.NEW_DOCUMENT, vo)

    def _on_load_doc(self, evt):
        dv = self.document_mediator._get_viewer(model.DocumentProxy.get_active())
        filename = self.viewComponent.get_document_filename(parent=dv, read=False)
        if filename:
            vo = model.vo.FileDocumentConfigVO(filename)
            self.sendNotification(main.Gribouillis.NEW_DOCUMENT, vo)

    def _on_save_doc(self, evt):
        docproxy = model.DocumentProxy.get_active()
        dv = self.document_mediator._get_viewer(docproxy)
        filename = self.viewComponent.get_document_filename(parent=dv, read=False)
        if filename:
            self.sendNotification(main.Gribouillis.DOC_SAVE, (docproxy, filename))

    def _on_clear_active_layer(self, evt):
        docproxy = model.DocumentProxy.get_active()
        self.sendNotification(main.Gribouillis.DOC_LAYER_CLEAR,
                              vo.LayerCommandVO(docproxy, docproxy.active_layer),
                              type=utils.RECORDABLE_COMMAND)

    def _on_load_background(self, evt):
        self.document_mediator.load_background()

    def _on_reset_view(self, evt):
        self.document_mediator.reset_view()

    def _on_load_image_as_layer(self, evt):
        self.document_mediator.load_image_as_layer()
        
    def _on_line_guide(self, evt):
        self.document_mediator.toggle_line_guide()

    def _on_ellipse_guide(self, evt):
        self.document_mediator.toggle_ellipse_guide()
    

    ### notification handlers ###

    @mvcHandler( main.Gribouillis.QUIT)
    def _on_quit(self, note):
        # test here if some documents need to be saved
        if len(self.document_mediator) > 0:
            res = pymui.DoRequest(self,
                                  gadgets= "*_No|_Yes",
                                  title  = "Need confirmation",
                                  format = "Some documents are not saved yet.\nSure to leave Gribouillis?")
            if res == 1: return
        self.viewComponent.quit()

    #### Public API ####

    def delete_docproxy(self, docproxy):
        self.document_mediator.delete_docproxy(docproxy)

        # Close the application on last document close event.
        if len(self.document_mediator) == 0:
            self.viewComponent.quit()

    def set_background_rgb(self, rgb):
        self.document_mediator.set_background_rgb(rgb)


class DialogMediator(Mediator):
    NAME = 'DialogMediator'

    def show_dialog(self, title, msg):
        pymui.DoRequest(app=self.viewComponent, title=title, format=msg, gadgets='*_Ok')

    #### notification handlers ####

    @mvcHandler(main.Gribouillis.SHOW_ERROR_DIALOG)
    def on_show_error(self, msg):
        self.show_dialog('', msg)

    @mvcHandler(main.Gribouillis.SHOW_WARNING_DIALOG)
    def on_show_warning(self, msg):
        self.show_dialog('', msg)

    @mvcHandler(main.Gribouillis.SHOW_INFO_DIALOG)
    def on_show_info(self, msg):
        self.show_dialog('', msg)

