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

import os

import puremvc.patterns.command
import puremvc.interfaces
import model, view, main, utils

from view.contexts import LastColorModal
from utils import _T

class InitModelCmd(puremvc.patterns.command.SimpleCommand, puremvc.interfaces.ICommand):
    def execute(self, note):
        model.prefs.load_preferences('config.xml')
            
        # Open a default empty document
        vo = model.vo.EmptyDocumentConfigVO()
        self.sendNotification(main.Gribouillis.NEW_DOCUMENT, vo)

class InitViewCmd(puremvc.patterns.command.SimpleCommand, puremvc.interfaces.ICommand):
    def execute(self, note):
        # ask the view application to create all its mediators
        self.facade.registerMediator(view.ApplicationMediator(note.getBody()))

        # open the default document now
        self.sendNotification(main.Gribouillis.DOC_ACTIVATE, model.DocumentProxy.get_active())

class StartupCmd(puremvc.patterns.command.MacroCommand, puremvc.interfaces.ICommand):
    def initializeMacroCommand(self):
        self.addSubCommand(InitModelCmd)
        self.addSubCommand(InitViewCmd)

class UndoCmd(puremvc.patterns.command.SimpleCommand, puremvc.interfaces.ICommand):
    def execute(self, note):
        hp = utils.CommandsHistoryProxy.get_active()
        if hp.canUndo():
            hp.getPrevious().undo()

class RedoCmd(puremvc.patterns.command.SimpleCommand, puremvc.interfaces.ICommand):
    def execute(self, note):
        hp = utils.CommandsHistoryProxy.get_active()
        if hp.canRedo():
            hp.getNext().redo()

class FlushCmd(puremvc.patterns.command.SimpleCommand, puremvc.interfaces.ICommand):
    def execute(self, note):
        hp = utils.CommandsHistoryProxy.get_active()
        hp.flush()

class NewDocumentCmd(puremvc.patterns.command.SimpleCommand, puremvc.interfaces.ICommand):
    def execute(self, note):
        vo = note.getBody() # DocumentConfigVO

        if isinstance(vo, model.vo.EmptyDocumentConfigVO):
            # check for unique doc name
            basename = vo.name
            bases = (basename, basename+' #')
            given = [ name for name in model.DocumentProxy.iternames() if name.startswith(bases) ]

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

            if not name:
                self.sendNotification(main.Gribouillis.SHOW_ERROR_DIALOG,
                                      "Document name already exist!")
                return

            vo.name = name
            docproxy = model.DocumentProxy.new_proxy(vo)

        else: # FileDocumentConfigVO
            # search if it wasn't open or active doc is empty, if yes just send a document_ready notification
            docproxy = model.DocumentProxy.from_doc_name(vo.name)
            if not docproxy:
                docproxy = model.DocumentProxy.get_active()
                try:
                    if not docproxy.document.empty:
                        docproxy = model.DocumentProxy.new_proxy(vo)
                    else:
                        docproxy.load(vo.name)
                        self.sendNotification(main.Gribouillis.DOC_UPDATED, docproxy)
                except Exception, e:
                    self.sendNotification(main.Gribouillis.SHOW_ERROR_DIALOG,
                                          "Failed to load document %s.\nReason: %s" % (vo.name, e))
                    docproxy = model.DocumentProxy.get_active()

        if docproxy:
            self.sendNotification(main.Gribouillis.DOC_ACTIVATE, docproxy)

class ActivateDocumentCmd(puremvc.patterns.command.SimpleCommand, puremvc.interfaces.ICommand):
    def execute(self, note):
        docproxy = note.getBody()
        docproxy.activate()

        # activate the commands history proxy of the document
        hp = self.facade.retrieveProxy('HP_' + docproxy.getProxyName())
        hp.activate()

        self.sendNotification(main.Gribouillis.DOC_ACTIVATED, docproxy)

class DeleteDocumentCmd(puremvc.patterns.command.SimpleCommand, puremvc.interfaces.ICommand):
    def execute(self, note):
        docproxy = note.getBody()

        # delete from view
        appmed = self.facade.retrieveMediator(view.ApplicationMediator.NAME)
        appmed.rem_docproxy(docproxy)

        # delete from model
        self.facade.removeProxy('HP_' + docproxy.getProxyName())
        self.facade.removeProxy(docproxy.getProxyName())
        
        del docproxy

class SaveDocumentCmd(puremvc.patterns.command.SimpleCommand, puremvc.interfaces.ICommand):
    def execute(self, note):
        docproxy, filename = note.getBody()
        if docproxy.document.empty:
            self.sendNotification(main.Gribouillis.SHOW_ERROR_DIALOG,
                                  _T("Failed to save document as %s.\nReason: Empty document") % filename)
            return
            
        try:
            docproxy.document.save_as(filename)
            docproxy.docname = filename
            
        except Exception, e:
            self.sendNotification(main.Gribouillis.SHOW_ERROR_DIALOG,
                                  _T("Failed to save document as %s.\nReason: %s") % (filename, e))
                                  
        else:
            self.sendNotification(main.Gribouillis.DOC_SAVE_RESULT, (docproxy, True))

class RenameLayerCmd(utils.UndoableCommand):
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

    def getCommandName(self):
        return self.__name

class SetLayerVisibilityCmd(utils.UndoableCommand):
    def execute(self, note):
        self.__name = "Set layer %svisible" % ('' if note.getBody().state else 'in')
        super(SetLayerVisibilityCmd, self).execute(note)
        self.registerUndoCommand(SetLayerVisibilityCmd)

    def executeCommand(self):
        note = self.getNote()
        vo = note.getBody()

        vo.layer.visible = vo.state

        # update the state for the next command execution (undo/redo)
        vo.state = not vo.state

        # Using DOC_LAYER_UPDATED than DOC_DIRTY as a layer property is modified
        self.sendNotification(main.Gribouillis.DOC_LAYER_UPDATED, (vo.docproxy, vo.layer))

    def getCommandName(self):
        return self.__name

class SetLayerOpacityCmd(puremvc.patterns.command.SimpleCommand, puremvc.interfaces.ICommand):
    def execute(self, note):
        vo = note.getBody()
        vo.layer.opacity = vo.state

        # Using DOC_LAYER_UPDATED than DOC_DIRTY as a layer property is modified, not only the contents
        self.sendNotification(main.Gribouillis.DOC_LAYER_UPDATED, (vo.docproxy, vo.layer))

class AddLayerCmd(utils.UndoableCommand):
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
        vo = note.getBody() # LayerCommandVO

        if vo.layer:
            # layer exist (redo or Remove undo) just insert it
            vo.docproxy.insert_layer(vo.layer, vo.pos, activate=True)
        else:
            # Create layer and save it in the value object for undo/redo
            vo.layer = vo.docproxy.new_layer(vo)

    def getCommandName(self):
        return self.__name

class RemoveLayerCmd(utils.UndoableCommand):
    def execute(self, note):
        vo = note.getBody()
        vo.pos = vo.docproxy.document.get_layer_index(vo.layer) # keep position for redo

        # Let one layer to the document
        if len(vo.docproxy.document) <= 1:
            return

        self.__name = "Delete layer %s" % vo.layer.name

        super(RemoveLayerCmd, self).execute(note)
        self.registerUndoCommand(AddLayerCmd)

    def executeCommand(self):
        note = self.getNote()
        vo = note.getBody() # LayerCommandVO
        vo.docproxy.remove_layer(vo.layer)

    def getCommandName(self):
        return self.__name

class DuplicateLayerCmd(utils.UndoableCommand):
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

class ActivateLayerCmd(puremvc.patterns.command.SimpleCommand, puremvc.interfaces.ICommand):
    def execute(self, note):
        docproxy, layer = note.getBody()
        docproxy.document.active = layer
        self.sendNotification(main.Gribouillis.DOC_LAYER_ACTIVATED, note.getBody())

class LayerStackChangeCmd(utils.UndoableCommand):
    def execute(self, note):
        docproxy, layer, new_pos = note.getBody()[:3]
        self.__name = "Stack change for layer %s" % layer.name
        new_pos = min(max(0, new_pos), len(docproxy.document)-1)
        note.setBody((docproxy, layer, new_pos, docproxy.document.get_layer_index(layer)))
        super(LayerStackChangeCmd, self).execute(note)
        self.registerUndoCommand(LayerStackChangeCmd)

    def executeCommand(self):
        note = self.getNote()
        docproxy, layer, new_pos, old_pos = note.getBody()
        docproxy.move_layer(layer, new_pos)
        note.setBody((docproxy, layer, old_pos, new_pos)) # swap pos order for the undo/redo

    def getCommandName(self):
        return self.__name

# Hidden command, only used in this module
class _UnMergeLayerCmd(puremvc.patterns.command.SimpleCommand, puremvc.interfaces.ICommand):
   def execute(self, note):
        docproxy, lsrc, ldst, opa, snapshot = note.getBody()
        pos = docproxy.document.get_layer_index(ldst)
        ldst.unsnapshot(snapshot)
        docproxy.set_layer_opacity(ldst, opa)
        docproxy.insert_layer(lsrc, pos+1, activate=True)

class MergeDownLayerCmd(utils.UndoableCommand):
    def execute(self, note):
        docproxy, pos = note.getBody()
        if pos == 0: return
        ldst, lsrc = docproxy.document.layers[pos-1:pos+1]
        self.__name = "Merged layer: %s -> %s" % (lsrc.name, ldst.name)
        note.setBody([ docproxy, lsrc, ldst, ldst.opacity, None])
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

# Hidden command, only used in this module
class _UnsnapshotLayerContentCmd(puremvc.patterns.command.SimpleCommand, puremvc.interfaces.ICommand):
    def execute(self, note):
        vo = note.getBody()
        vo.layer.unsnapshot(vo.snapshot)
        self.sendNotification(main.Gribouillis.DOC_DIRTY, (vo.docproxy, vo.dirty_area))

class ClearLayerCmd(utils.UndoableCommand):
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
        self.sendNotification(main.Gribouillis.DOC_DIRTY, (vo.docproxy, vo.dirty_area))

    def getCommandName(self):
        return self.__name

class RecordStrokeCmd(utils.UndoableCommand):
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
            self.__name = 'Stroke (%2.3fMB)' % (vo.snapshot.size/(1024.*1024))
            vo.stroke = None
        else:
            layer.unsnapshot(vo.snapshot, True)
            self.sendNotification(main.Gribouillis.DOC_DIRTY, (vo.docproxy, vo.dirty_area))

        # Update the last color used also
        LastColorModal.push_color(vo.docproxy.get_brush_color_rgb())

    def getCommandName(self):
        return self.__name

class LoadImageAsLayerCmd(utils.UndoableCommand):
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
                self.sendNotification(main.Gribouillis.SHOW_ERROR_DIALOG,
                                      "Loading image %s failed" % vo.filename)
                return

            # Create a new layer (on top) and fill it with image data
            vo.layer = layer = docproxy.new_layer(vo)
            data,w,h,stride = data
            layer.surface.from_png_buffer(data,stride,0,0,w,h)

            # get the position to be sure
            vo.pos = docproxy.document.get_layer_index(layer)
            
        self.sendNotification(main.Gribouillis.DOC_DIRTY, (docproxy, layer.area))

    def getCommandName(self):
        return self.__name

class SetLayerMatrixCmd(utils.UndoableCommand):
    def execute(self, note):
        self.__name = "Layer transformation"
        super(SetLayerMatrixCmd, self).execute(note)
        self.registerUndoCommand(SetLayerMatrixCmd)

    def executeCommand(self):
        note = self.getNote()
        docproxy, layer, old_mat, new_mat = note.getBody()
        layer.matrix = old_mat
        old_area = layer.area # area in document space with current matrix
        layer.matrix = new_mat
        new_area = layer.area
        note.setBody((docproxy, layer, new_mat, old_mat)) # inverse matrixes for undo/redo
        
        area = utils.join_area(old_area, new_area)
        self.sendNotification(main.Gribouillis.DOC_DIRTY, (docproxy, area))

    def getCommandName(self):
        return self.__name

