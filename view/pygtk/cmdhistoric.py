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

import main, utils

from utils import mvcHandler
from .common import SubWindow

__all__ = [ 'CommandsHistoryList', 'CommandsHistoryListMediator' ]

class CommandsHistoryList(SubWindow):
    def __init__(self):
        super(CommandsHistoryList, self).__init__()
        self.set_title('Command Historic')

        topbox = gtk.VBox()

        # The command display list
        self.liststore = gtk.ListStore(str)
        self.treeview = gtk.TreeView(self.liststore)
        self.cell = gtk.CellRendererText()
        self.tvcolumn = gtk.TreeViewColumn('', self.cell, markup=0)
        self.treeview.append_column(self.tvcolumn)

        self.scrolledwin = gtk.ScrolledWindow()
        self.scrolledwin.add(self.treeview)

        # Undo/Redo buttons
        btnbox = gtk.HButtonBox()

        self.btn_undo = gtk.Button('Undo')
        self.btn_redo = gtk.Button('Redo')
        self.btn_flush = gtk.Button('Flush')

        # Packing
        topbox.pack_start(self.scrolledwin, True)
        topbox.pack_start(btnbox, False)

        btnbox.pack_start(self.btn_undo)
        btnbox.pack_start(self.btn_redo)
        btnbox.pack_start(self.btn_flush)

        self.add(topbox)
        topbox.show_all()

        self.enable_undo(False)
        self.enable_redo(False)
        self.enable_flush(False)

        self.__last_added = None

    def set_doc_name(self, name):
        self.tvcolumn.set_title('Document: '+name)

    def enable_undo(self, v=True):
        self.btn_undo.set_sensitive(v)

    def enable_redo(self, v=True):
        self.btn_redo.set_sensitive(v)

    def enable_flush(self, v=True):
        self.btn_flush.set_sensitive(v)

    def add_cmd(self, cmd):
        if self.__last_added:
            n = self.liststore.get_path(self.__last_added)[0]
            if n > 0:
                iter = self.liststore.get_iter_first()
                while n and self.liststore.remove(iter):
                    n -= 1

        self.__last_added = self.liststore.prepend([ cmd.getCommandName() ])
        self.enable_undo()
        self.enable_redo(False)
        self.enable_flush()

    def flush(self):
        self.liststore.clear()
        self.__last_added = None
        self.enable_undo(False)
        self.enable_redo(False)
        self.enable_flush(False)

    def undo(self, cmd):
        self.liststore.set_value(self.__last_added, 0, '<s>%s</s>' % cmd.getCommandName())
        self.__last_added = self.liststore.iter_next(self.__last_added)
        self.enable_undo(self.__last_added is not None)
        self.enable_redo(True)

    def redo(self, cmd):
        if self.__last_added:
            path = (self.liststore.get_path(self.__last_added)[0]-1,)
            if path[0] == 0:
                self.enable_redo(False)
        else:
            path = (len(self.liststore)-1,)
        self.__last_added = self.liststore.get_iter(path)
        self.liststore.set_value(self.__last_added, 0, cmd.getCommandName())
        self.enable_undo(True)

    def from_stacks(self, undo_stack, redo_stack):
        self.liststore.clear()
        self.__last_added = None

        if not undo_stack and not redo_stack:
            self.enable_flush(False)
            return

        self.enable_flush(True)

        if undo_stack:
            for cmd in undo_stack:
                self.__last_added = self.liststore.prepend([ cmd.getCommandName() ])
            self.enable_undo(True)
        else:
            self.enable_undo(False)

        if redo_stack:
            for cmd in redo_stack:
                self.liststore.prepend([ '<s>%s</s>' % cmd.getCommandName() ])
            self.enable_redo(True)
        else:
            self.enable_redo(False)


class CommandsHistoryListMediator(utils.Mediator):
    NAME = "CommandsHistoryListMediator"

    cmdhistproxy = None

    #### Private API ####

    def __init__(self, component):
        assert isinstance(component, CommandsHistoryList)
        super(CommandsHistoryListMediator, self).__init__(CommandsHistoryListMediator.NAME, component)

        self.__cur_hp = None

        component.btn_undo.connect('clicked', self._on_undo)
        component.btn_redo.connect('clicked', self._on_redo)
        component.btn_flush.connect('clicked', self._on_flush)

    #### Protected API ####

    def _on_undo(self, *a):
        self.sendNotification(main.Gribouillis.UNDO)

    def _on_redo(self, *a):
        self.sendNotification(main.Gribouillis.REDO)

    def _on_flush(self, *a):
        self.sendNotification(main.Gribouillis.FLUSH)

    ### notification handlers ###

    @mvcHandler(main.Gribouillis.DOC_ACTIVATED)
    def _on_doc_activated(self, docproxy):
        self.viewComponent.set_doc_name(docproxy.docname)
        self.__cur_hp = utils.CommandsHistoryProxy.get_active()
        self.viewComponent.from_stacks(self.__cur_hp.undo_stack, self.__cur_hp.redo_stack)

    @mvcHandler(utils.CommandsHistoryProxy.CMD_HIST_ADD)
    def _on_cmd_add(self, hp, cmd):
        if hp is self.__cur_hp:
            self.viewComponent.add_cmd(cmd)

    @mvcHandler(utils.CommandsHistoryProxy.CMD_HIST_FLUSHED)
    def _on_cmd_flush(self, hp):
        if hp is self.__cur_hp:
            self.viewComponent.flush()

    @mvcHandler(utils.CommandsHistoryProxy.CMD_HIST_UNDO)
    def _on_cmd_undo(self, hp, cmd):
        if hp is self.__cur_hp:
            self.viewComponent.undo(cmd)

    @mvcHandler(utils.CommandsHistoryProxy.CMD_HIST_REDO)
    def _on_cmd_redo(self, hp, cmd):
        if hp is self.__cur_hp:
            self.viewComponent.redo(cmd)

