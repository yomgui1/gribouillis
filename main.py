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

import os
import puremvc.patterns.facade

__all__ = ['Gribouillis', 'VERSION', 'DATE']

# Defaults - must be changed by the caller
VERSION = 3.0
BUILD = 0
DATE = 'dd.mm.yyyy'

# Must be commited
STATUS = 'beta'

DOC_ACTIVATE = 'doc-activate'
DOC_ACTIVATED = 'doc-activated'                       # gives the working document
DOC_SAVE = 'doc-save'
DOC_SAVE_RESULT = 'doc-save-result'
DOC_DELETE = 'doc-delete'
DOC_RELEASE = 'doc-release'

# document's layer notifications
DOC_LAYER_ACTIVATE = 'doc-layer-active'
DOC_LAYER_ACTIVATED = 'doc-layer-actived'
DOC_LAYER_UPDATED = 'doc-layer-updated'
DOC_LAYER_RENAME = 'doc-layer-rename'                 # undoable command
DOC_LAYER_RENAMED = 'doc-layer-renamed'
DOC_LAYER_ADD = 'doc-layer-add'                       # undoable command
DOC_LAYER_DEL = 'doc-layer-del'                       # undoable command
DOC_LAYER_DELETED = 'doc-layer-deleted'
DOC_LAYER_DUP = 'doc-layer-dup'                       # undoable command
DOC_LAYER_STACK_CHANGE = 'doc-layer-stack-change'     # undoable command
DOC_LAYER_STACK_CHANGED = 'doc-layer-stack-changed'
DOC_LAYER_SET_VISIBLE = 'doc-layer-visible'
DOC_LAYER_SET_OPACITY = 'doc-layer-opacity'
DOC_LAYER_MERGE_DOWN = 'doc-layer-merge-down'         # undoable command
DOC_RECORD_STROKE = 'doc-record-stroke'               # undoable command
DOC_LOAD_IMAGE_AS_LAYER = 'doc-load-image-as-layer'   # undoable command
DOC_LAYER_MATRIX = 'doc-layer-matrix'                 # undoable command

# refactored ok
STARTUP = 'startup'
QUIT = 'quit'  # user want to quit the application

SHOW_ERROR_DIALOG = 'show-error-dlg'
SHOW_WARNING_DIALOG = 'show-warning-dlg'
SHOW_INFO_DIALOG = 'show-info-dlg'

NEW_DOCUMENT = 'new-doc'  # user want to create a new document
LAYER_CLEAR = 'layer-clear' # clear layer contents (undoable, data: LayerCmdVO)

USE_BRUSH = 'use-brush'


class Gribouillis(puremvc.patterns.facade.Facade):
    __instance = None

    # application constants
    PREVIEW_BACKGROUND = '${backgrounds-path}/checker.png'
    TRANSPARENT_BACKGROUND = '${backgrounds-path}/checker.png'
    DEFAULT_BACKGROUND = (1, 1, 1)

    def __new__(cl, *a, **k):
        if cl.__instance:
            return cl.__instance

        self = super(Gribouillis, cl).__new__(cl, *a, **k)
        cl.__instance = self
        return self

    def __init__(self, datapath, userpath=None):
        if userpath is None:
            userpath = datapath
        self.paths = dict(data=datapath, userpath=userpath)
        self.initializeFacade()

    @classmethod
    def getInstance(cl):
        return cl.__instance

    def initializeFacade(self):
        super(Gribouillis, self).initializeFacade()
        self.initializeController()

    def initializeController(self):
        import controller

        super_ = super(Gribouillis, self)
        super_.initializeController()

        super_.registerCommand(STARTUP, controller.StartupCmd)

        super_.registerCommand(NEW_DOCUMENT, controller.NewDocumentCmd)
        super_.registerCommand(DOC_ACTIVATE, controller.ActivateDocumentCmd)
        super_.registerCommand(DOC_DELETE, controller.DeleteDocumentCmd)
        super_.registerCommand(DOC_SAVE, controller.SaveDocumentCmd)

        super_.registerCommand(LAYER_CLEAR, controller.ClearLayerCmd)

        super_.registerCommand(DOC_LAYER_RENAME, controller.RenameLayerCmd)
        super_.registerCommand(DOC_LAYER_ADD, controller.AddLayerCmd)
        super_.registerCommand(DOC_LAYER_DEL, controller.RemoveLayerCmd)
        super_.registerCommand(DOC_LAYER_DUP, controller.DuplicateLayerCmd)
        super_.registerCommand(DOC_LAYER_STACK_CHANGE, controller.LayerStackChangeCmd)
        super_.registerCommand(DOC_LAYER_MATRIX, controller.SetLayerMatrixCmd)
        super_.registerCommand(DOC_LAYER_ACTIVATE, controller.ActivateLayerCmd)
        super_.registerCommand(DOC_LAYER_SET_VISIBLE, controller.SetLayerVisibilityCmd)
        super_.registerCommand(DOC_RECORD_STROKE, controller.RecordStrokeCmd)
        super_.registerCommand(DOC_LOAD_IMAGE_AS_LAYER, controller.LoadImageAsLayerCmd)
        super_.registerCommand(DOC_LAYER_SET_OPACITY, controller.SetLayerOpacityCmd)
        super_.registerCommand(DOC_LAYER_MERGE_DOWN, controller.MergeDownLayerCmd)
        super_.registerCommand(USE_BRUSH, controller.UseBrushCmd)
