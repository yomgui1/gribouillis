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

"""Controller module, implementation of control part.

This module exports all functions called by the hi-level MVC
notification system (obj.sendNotification() method).
This hi-level interface doesn't depend on any platforms implementation,
nor related to Model or View layers.
"""

import os

import utils
import main
import model

from puremvc.patterns.command import SimpleCommand, MacroCommand
from puremvc.interfaces import ICommand

from utils import _T, UndoableCommand
from view.contexts import LastColorModal

class StartupCmd(MacroCommand, ICommand):
    """First command executed when application is created.
    Initialize model and view layers, setup defaults.
    """
    def initializeMacroCommand(self):
        self.addSubCommand(InitModelCmd)
        self.addSubCommand(InitViewCmd)


class InitModelCmd(SimpleCommand, ICommand):
    def execute(self, note):
        pp = model.PrefsProxy()
        self.facade.registerProxy(pp)
        pp.load('config.xml')
        model.prefs = pp
        
        # Load the default document
        docpath = pp.data.get('default-document')
        if docpath is None:
            vo = model.vo.EmptyDocumentConfigVO()
        else:
            vo = model.vo.FileDocumentConfigVO(docpath)
        
        self.sendNotification(main.NEW_DOCUMENT, vo)


class InitViewCmd(SimpleCommand, ICommand):
    def execute(self, note):
        # View knows the list of its Mediators
        #self.facade.registerMediator(view.ApplicationMediator(note.getBody()))
        pass


class UndoCmd(SimpleCommand, ICommand):
    def execute(self, note):
        hp = utils.CommandsHistoryProxy.get_active()
        if hp.canUndo():
            hp.getPrevious().undo()


class RedoCmd(SimpleCommand, ICommand):
    def execute(self, note):
        hp = utils.CommandsHistoryProxy.get_active()
        if hp.canRedo():
            hp.getNext().redo()


class FlushCmd(SimpleCommand, ICommand):
    def execute(self, note):
        hp = utils.CommandsHistoryProxy.get_active()
        hp.flush()


class NewDocumentCmd(SimpleCommand, ICommand):
    """Try to open/create document model as specified by given
    DocumentConfigVO instance.
    Exception raised if document cannot be created/open.
    """
    def execute(self, note):
        vo = note.getBody()  # DocumentConfigVO

        if isinstance(vo, model.vo.EmptyDocumentConfigVO):
            basename = vo.name
            bases = (basename, basename + ' #')
            given = [name for name in model.DocumentProxy.iternames()
                     if name.startswith(bases)]

            name = None
            if bases[0] not in given:
                name = bases[0]
            else:
                x = 1
                fmt = bases[1] + '%u'
                while x < 1000:
                    name = fmt % x
                    if name not in given:
                        break
                    x += 1

            vo.name = name
            docproxy = model.DocumentProxy.new_proxy(vo)
        else:
            # FileDocumentConfigVO
            # Search first if document isn't created yet,
            # if is it, the existing document is just activated.
            # New document are created/loaded then activated.

            docproxy = model.DocumentProxy.from_doc_name(vo.name)
            if not docproxy:
                # If the active docproxy is in 'safe' state (empty or
                # untouched), it's going to be used as container for the
                # wanted document. Otherwise a new docproxy is created.
                docproxy = model.DocumentProxy.get_active()
                if not docproxy or not docproxy.document.close_safe:
                    docproxy = model.DocumentProxy.new_proxy(vo)

                docproxy.load(vo.name)

        self.sendNotification(main.DOC_ACTIVATE, docproxy)


class DeleteDocumentCmd(SimpleCommand, ICommand):
    def execute(self, note):
        docproxy = note.getBody()

        # delete from view
        appmed = self.facade.retrieveMediator(view.ApplicationMediator.NAME)
        appmed.rem_docproxy(docproxy)

        # delete from model
        self.facade.removeProxy('HP_' + docproxy.getProxyName())
        self.facade.removeProxy(docproxy.getProxyName())

        del docproxy


class SaveDocumentCmd(SimpleCommand, ICommand):
    def execute(self, note):
        docproxy, filename = note.getBody()
        if docproxy.document.empty:
            self.sendNotification(main.SHOW_ERROR_DIALOG,
                                  _T("Failed to save document as %s.\nReason: Empty document") % filename)
            return

        try:
            docproxy.document.save_as(filename)
            docproxy.docname = filename

        except Exception, e:
            self.sendNotification(main.SHOW_ERROR_DIALOG,
                                  _T("Failed to save document as %s.\nReason: %s") % (filename, e))

        else:
            self.sendNotification(main.DOC_SAVE_RESULT, (docproxy, True))


class ActivateDocumentCmd(SimpleCommand, ICommand):
    def execute(self, note):
        docproxy = note.getBody()
        docproxy.active = docproxy

        # activate the commands history proxy of the document
        hp = self.facade.retrieveProxy('HP_' + docproxy.getProxyName())
        hp.activate()

        self.sendNotification(main.DOC_ACTIVATED, self)


class RenameLayerCmd(UndoableCommand):
    def execute(self, note):

        self.__name = "Rename layer '%s' to '%s'" % (note.getBody().layer.name, note.getBody().name)
        super(RenameLayerCmd, self).execute(note)
        self.registerUndoCommand(RenameLayerCmd)

    def executeCommand(self):
        note = self.getNote()
        vo = note.getBody()

        # update the name for the next command execution (undo/redo)
        old_name = vo.layer.name
        vo.layer.name = vo.name
        vo.name = old_name
        self.sendNotification(main.DOC_LAYER_RENAMED, (vo.docproxy, vo.layer))

    def getCommandName(self):
        return self.__name


class SetLayerVisibilityCmd(SimpleCommand, ICommand):
    def execute(self, note):
        vo = note.getBody()
        vo.layer.visible = vo.state

        # Using DOC_LAYER_UPDATED than DOC_DIRTY as a layer property is modified
        self.sendNotification(main.DOC_LAYER_UPDATED, (vo.docproxy, vo.layer))


class SetLayerOpacityCmd(SimpleCommand, ICommand):
    def execute(self, note):
        vo = note.getBody()
        vo.layer.opacity = vo.state

        # Using DOC_LAYER_UPDATED than DOC_DIRTY as a layer property is modified, not only the contents
        self.sendNotification(main.DOC_LAYER_UPDATED, (vo.docproxy, vo.layer))


class AddLayerCmd(UndoableCommand):
    def execute(self, note):
        vo = note.getBody()
        if vo.layer:
            name = vo.layer.name
        else:
            name = vo.name
        self.__name = "Add layer %s" % name
        super(AddLayerCmd, self).execute(note)
        self.registerUndoCommand(RemoveLayerCmd)

    def executeCommand(self):
        note = self.getNote()
        vo = note.getBody()  # LayerCommandVO
        docproxy = vo.docproxy

        if vo.layer:
            # layer exist (redo or Remove undo) just insert it
            docproxy.insert_layer(vo.layer, vo.pos, activate=True)
        else:
            # Create layer and save it in the value object for undo/redo
            vo.layer = docproxy.new_layer(vo)

        self.sendNotification(main.DOC_LAYER_ACTIVATED, (docproxy, docproxy.active_layer))

    def getCommandName(self):
        return self.__name


class RemoveLayerCmd(UndoableCommand):
    def execute(self, note):
        vo = note.getBody()
        vo.pos = vo.docproxy.document.get_layer_index(vo.layer)  # keep position for redo

        # Let one layer to the document
        if len(vo.docproxy.document) <= 1:
            return

        self.__name = "Delete layer %s" % vo.layer.name

        super(RemoveLayerCmd, self).execute(note)
        self.registerUndoCommand(AddLayerCmd)

    def executeCommand(self):
        note = self.getNote()
        vo = note.getBody()  # LayerCommandVO
        vo.docproxy.remove_layer(vo.layer)

    def getCommandName(self):
        return self.__name


class DuplicateLayerCmd(UndoableCommand):
    def execute(self, note):
        vo = note.getBody()
        self.__name = "Duplicate layer %s" % vo.layer.name
        vo.from_layer = None
        super(DuplicateLayerCmd, self).execute(note)
        self.registerUndoCommand(RemoveLayerCmd)

    def executeCommand(self):
        vo = self.getNote().getBody()
        if vo.from_layer:
            new_layer = vo.layer
            vo.docproxy.insert_layer(vo.layer, vo.pos, activate=True)
        else:
            vo.from_layer = vo.layer
            new_layer = vo.layer = vo.docproxy.copy_layer(vo.layer)

    def getCommandName(self):
        return self.__name


class ActivateLayerCmd(SimpleCommand, ICommand):
    def execute(self, note):
        docproxy, layer = note.getBody()
        docproxy.document.active = layer
        self.sendNotification(main.DOC_LAYER_ACTIVATED, note.getBody())


class LayerStackChangeCmd(UndoableCommand):
    def execute(self, note):
        docproxy, layer, new_pos = note.getBody()[:3]
        self.__name = "Stack change for layer %s" % layer.name
        new_pos = min(max(0, new_pos), len(docproxy.document) - 1)
        note.setBody((docproxy, layer, new_pos, docproxy.document.get_layer_index(layer)))
        super(LayerStackChangeCmd, self).execute(note)
        self.registerUndoCommand(LayerStackChangeCmd)

    def executeCommand(self):
        note = self.getNote()
        docproxy, layer, new_pos, old_pos = note.getBody()
        docproxy.move_layer(layer, new_pos)
        note.setBody((docproxy, layer, old_pos, new_pos))  # swap pos order for the undo/redo

    def getCommandName(self):
        return self.__name


class MergeDownLayerCmd(UndoableCommand):
    def execute(self, note):
        docproxy, pos = note.getBody()
        if pos == 0:
            return
        ldst, lsrc = docproxy.document.layers[pos - 1:pos + 1]
        self.__name = "Merged layer: %s -> %s" % (lsrc.name, ldst.name)
        note.setBody([docproxy, lsrc, ldst, ldst.opacity, None])
        super(MergeDownLayerCmd, self).execute(note)
        self.registerUndoCommand(_UnMergeLayerCmd)

    def executeCommand(self):
        note = self.getNote()
        docproxy, lsrc, ldst, opa, snapshot = note.getBody()

        if snapshot is None:
            snapshot = ldst.snapshot()      # Save destination layer contents
            lsrc.merge_to(ldst)             # Do the merge
            snapshot.reduce(ldst.surface)   # Keep only modified part in snapshot
            note.getBody()[-1] = snapshot   # Register snapshot for undo operation
        else:
            ldst.unsnapshot(snapshot, redo=True)

        docproxy.remove_layer(lsrc)
        docproxy.set_layer_opacity(ldst, 1.0)

    def getCommandName(self):
        return self.__name


class ClearLayerCmd(UndoableCommand):
    def execute(self, note):
        vo = note.getBody()
        self.__name = "Clear layer %s" % vo.layer.name
        super(ClearLayerCmd, self).execute(note)
        self.registerUndoCommand(_UnsnapshotLayerContentCmd)

    def executeCommand(self):
        vo = self.getNote().getBody()
        vo.snapshot = vo.layer.surface.snapshot()
        vo.dirty_area = vo.layer.area
        vo.layer.clear()
        self.sendNotification(main.DOC_DIRTY, (vo.docproxy, vo.dirty_area))

    def getCommandName(self):
        return self.__name


class RecordStrokeCmd(UndoableCommand):
    """vo parameters:

        docproxy: document proxy
        layer   : layer where stroke is applied
        snapshot: layer snapshot before the stroke
        stroke  : stroke to record
    """

    def execute(self, note):
        vo = note.getBody()
        super(RecordStrokeCmd, self).execute(note)
        vo.dirty_area = vo.layer.document_area(*vo.snapshot.dirty_area)
        self.registerUndoCommand(_UnsnapshotLayerContentCmd)

    def executeCommand(self):
        vo = self.getNote().getBody()
        layer = vo.layer

        if vo.stroke is not None:
            self.__name = 'Stroke (%2.3fMB)' % (vo.snapshot.size / (1024. * 1024))
            vo.stroke = None
        else:
            layer.unsnapshot(vo.snapshot, True)
            self.sendNotification(main.DOC_DIRTY, (vo.docproxy, vo.dirty_area))

        # Update the last color used also
        LastColorModal.push_color(vo.docproxy.get_brush_color_rgb())

    def getCommandName(self):
        return self.__name


class LoadImageAsLayerCmd(UndoableCommand):
    """vo parameters:

        docproxy: document proxy
        filename: stroke to record

       Stored for undo:
        layer: created layer
        pos: layer position in document's layers stack
    """

    def execute(self, note):
        vo = note.getBody()
        vo.name = os.path.basename(vo.filename)
        self.__name = "Add image as layer (%s)" % vo.name
        super(LoadImageAsLayerCmd, self).execute(note)
        self.registerUndoCommand(RemoveLayerCmd)

    def executeCommand(self):
        vo = self.getNote().getBody()

        docproxy = vo.docproxy

        if vo.layer:
            layer = vo.layer
            docproxy.insert_layer(layer, vo.pos, activate=True)
        else:
            # Load the image
            data = model.Document.load_image(vo.filename)
            if data is None:
                self.sendNotification(main.SHOW_ERROR_DIALOG,
                                      "Loading image %s failed" % vo.filename)
                return

            # Create a new layer (on top) and fill it with image data
            vo.layer = layer = docproxy.new_layer(vo)
            data, w, h, stride = data
            layer.surface.from_png_buffer(data, stride, 0, 0, w, h)

            # get the position to be sure
            vo.pos = docproxy.document.get_layer_index(layer)

        self.sendNotification(main.DOC_DIRTY, (docproxy, layer.area))

    def getCommandName(self):
        return self.__name


class SetLayerMatrixCmd(UndoableCommand):
    def execute(self, note):
        self.__name = "Layer transformation"
        super(SetLayerMatrixCmd, self).execute(note)
        self.registerUndoCommand(SetLayerMatrixCmd)

    def executeCommand(self):
        note = self.getNote()
        docproxy, layer, old_mat, new_mat = note.getBody()
        layer.matrix = old_mat
        old_area = layer.area  # area in document space with current matrix
        layer.matrix = new_mat
        new_area = layer.area
        note.setBody((docproxy, layer, new_mat, old_mat))  # inverse matrixes for undo/redo

        area = utils.join_area(old_area, new_area)
        self.sendNotification(main.DOC_DIRTY, (docproxy, area))

    def getCommandName(self):
        return self.__name


### Hidden commands, only used in this module

class _UnMergeLayerCmd(SimpleCommand, ICommand):
    def execute(self, note):
        docproxy, lsrc, ldst, opa, snapshot = note.getBody()
        pos = docproxy.document.get_layer_index(ldst)
        ldst.unsnapshot(snapshot)
        docproxy.set_layer_opacity(ldst, opa)
        docproxy.insert_layer(lsrc, pos + 1, activate=True)


class _UnsnapshotLayerContentCmd(SimpleCommand, ICommand):
    def execute(self, note):
        vo = note.getBody()
        vo.layer.unsnapshot(vo.snapshot)
        self.sendNotification(main.DOC_DIRTY, (vo.docproxy, vo.dirty_area))
