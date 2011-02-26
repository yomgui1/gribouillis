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

import sys

if __name__ == '__main__':
    sys.setrecursionlimit(100)
    sys.path.insert(0, 'libs/python25.zip')

import os
import puremvc.patterns.facade
import controller

__all__ = ['Gribouillis', 'VERSION', 'DATE' ]

VERSION = 2.7
DATE = 23/02/2011

class Gribouillis(puremvc.patterns.facade.Facade):
    # application constants
    BACKGROUND_PATH = os.path.join('images', 'backgrounds')
    DEFAULT_BRUSHPREVIEW_BACKGROUND = os.path.join(BACKGROUND_PATH, 'checker.png')
    DEFAULT_BACKGROUND = (1,1,1)

    # application notifications
    STARTUP             = 'startup'
    QUIT                = 'quit'          # user want to quit the application
    UNDO                = 'undo'
    REDO                = 'redo'
    FLUSH               = 'flush'

    SHOW_ERROR_DIALOG   = 'show_error_dlg'
    SHOW_WARNING_DIALOG = 'show_warning_dlg'
    SHOW_INFO_DIALOG    = 'show_info_dlg'

    NEW_DOCUMENT         = 'new-doc'      # user want to create a new document
    NEW_DOCUMENT_RESULT  = 'new-doc-res'
    
    DOC_UPDATED          = 'doc-updated'
    DOC_ACTIVATE         = 'doc-activate'
    DOC_ACTIVATED        = 'doc-activated' # When the document is ready to accept user inputs

    DOC_SAVE             = 'doc-save'
    DOC_SAVE_RESULT      = 'doc-save-res'
    DOC_DELETE           = 'doc-del'

    LAYER_CREATED        = 'layer-created'

    # document's layer notifications
    DOC_LAYER_ACTIVATE      = 'doc-layer-active'
    DOC_LAYER_ACTIVATED     = 'doc-layer-actived'
    DOC_LAYER_UPDATED       = 'doc-layer-updated'
    DOC_LAYER_RENAME        = 'doc-layer-rename' # undoable command
    DOC_LAYER_ADD           = 'doc-layer-add'    # undoable command
    DOC_LAYER_ADDED         = 'doc-layer-added'
    DOC_LAYER_DEL           = 'doc-layer-del'    # undoable command
    DOC_LAYER_DELETED       = 'doc-layer-deleted'
    DOC_LAYER_DUP           = 'doc-layer-dup'    # undoable command
    DOC_LAYER_MOVE          = 'doc-layer-move'   # undoable command
    DOC_LAYER_MOVED         = 'doc-layer-moved'
    DOC_LAYER_CLEAR         = 'doc-layer-clear'   # undoable command
    DOC_LAYER_SET_VISIBLE   = 'doc-layer-visible' # undoable command
    DOC_LAYER_SET_OPACITY   = 'doc-layer-opacity'
    DOC_LAYER_MERGE_DOWN    = 'doc-layer-merge-down' # undoable command
    DOC_RECORD_STROKE       = 'doc-record-stroke' # undoable command
    DOC_LOAD_IMAGE_AS_LAYER = 'doc-load-image-as-layer' # undoable command
    DOC_BRUSH_UPDATED       = 'doc-brush-updated'

    # Brush notifications
    BRUSH_PROP_CHANGED = 'brush-prop-changed'

    def __init__(self, datapath, userpath=None):
        if userpath is None:
            userpath = datapath
        self.paths = dict(data=datapath, userpath=userpath)
        self.initializeFacade()

    @staticmethod
    def getInstance():
        return Gribouillis()

    def initializeFacade(self):
        super(Gribouillis, self).initializeFacade()
        self.initializeController()

    def initializeController(self):
        super_ = super(Gribouillis, self)
        super_.initializeController()

        super_.registerCommand(Gribouillis.STARTUP, controller.StartupCmd)
        super_.registerCommand(Gribouillis.UNDO, controller.UndoCmd)
        super_.registerCommand(Gribouillis.REDO, controller.RedoCmd)
        super_.registerCommand(Gribouillis.FLUSH, controller.FlushCmd)

        super_.registerCommand(Gribouillis.NEW_DOCUMENT, controller.NewDocumentCmd)
        super_.registerCommand(Gribouillis.DOC_ACTIVATE, controller.ActivateDocumentCmd)
        super_.registerCommand(Gribouillis.DOC_DELETE, controller.DeleteDocumentCmd)
        super_.registerCommand(Gribouillis.DOC_SAVE, controller.SaveDocumentCmd)

        super_.registerCommand(Gribouillis.DOC_LAYER_RENAME, controller.RenameLayerCmd)
        super_.registerCommand(Gribouillis.DOC_LAYER_ADD, controller.AddLayerCmd)
        super_.registerCommand(Gribouillis.DOC_LAYER_DEL, controller.RemoveLayerCmd)
        super_.registerCommand(Gribouillis.DOC_LAYER_DUP, controller.DuplicateLayerCmd)
        super_.registerCommand(Gribouillis.DOC_LAYER_MOVE, controller.MoveLayerCmd)
        super_.registerCommand(Gribouillis.DOC_LAYER_ACTIVATE, controller.ActivateLayerCmd)
        super_.registerCommand(Gribouillis.DOC_LAYER_CLEAR, controller.ClearLayerCmd)
        super_.registerCommand(Gribouillis.DOC_LAYER_SET_VISIBLE, controller.SetLayerVisibilityCmd)
        super_.registerCommand(Gribouillis.DOC_RECORD_STROKE, controller.RecordStrokeCmd)
        super_.registerCommand(Gribouillis.DOC_LOAD_IMAGE_AS_LAYER, controller.LoadImageAsLayerCmd)
        super_.registerCommand(Gribouillis.DOC_LAYER_SET_OPACITY, controller.SetLayerOpacityCmd)
        super_.registerCommand(Gribouillis.DOC_LAYER_MERGE_DOWN, controller.MergeDownLayerCmd)
        

if __name__ == '__main__':
    import os
    import view

    gribouillis = Gribouillis(os.getcwd())
    be_app = view.Application()
    gribouillis.sendNotification(Gribouillis.STARTUP, be_app)
    be_app.run()
