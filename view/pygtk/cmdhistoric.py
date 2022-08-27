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

from gi.repository import Gtk as gtk

from utils import _T
from .common import SubWindow


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

        self.btn_undo = gtk.Button(_T('Undo'))
        self.btn_redo = gtk.Button(_T('Redo'))
        self.btn_flush = gtk.Button(_T('Flush'))

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
        self.tvcolumn.set_title(_T('Document: %s') % name)

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
