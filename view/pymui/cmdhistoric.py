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

from pymui import *

import model, view, main, utils

__all__ = [ 'CommandsHistoryList' ]

class MyList(List):
    MCC = True

    def __init__(self, *a, **k):
        self.__entries = {}
        List.__init__(self, *a, **k)

    @muimethod(MUIM_List_Construct)
    def _construct(self, msg):
        # string is not copied by the list,
        # so record a str object here
        s = c_STRPTR(msg.entry.value).value
        v = c_STRPTR(s)
        self.__entries[long(v)] = s
        return v

    @muimethod(MUIM_List_Destruct)
    def _destructor(self, msg):
        del self.__entries[msg.entry.value]


class CommandsHistoryList(Window):
    def __init__(self, name):
        super(CommandsHistoryList, self).__init__(ID='CMDH', Title='Commands Historic', CloseOnReq=True)
        self.name = name

        ro = VGroup()
        self.RootObject = ro

        # The command display list
        self._cmdlist = MyList(Background='ListBack', Input=True, AutoVisible=True)

        self.title = Text(Frame='Group')
        ro.AddChild(self.title)

        lv = Listview(List=self._cmdlist)
        ro.AddChild(lv)

        # List/Buttons separator
        ro.AddChild(HBar(0))

        # Undo/Redo buttons
        btn_grp = HGroup()
        ro.AddChild(btn_grp)

        self.btn_undo = btn = SimpleButton('Undo', CycleChain=True, Disabled=True)
        btn_grp.AddChild(btn)

        self.btn_redo = btn = SimpleButton('Redo', CycleChain=True, Disabled=True)
        btn_grp.AddChild(btn)

        self.btn_flush = btn = SimpleButton('Flush', CycleChain=True, Disabled=True)
        btn_grp.AddChild(btn)

        self.__last_added = -1

    def set_doc_name(self, name):
        self.title.Contents = name

    def enable_undo(self, v=True):
        self.btn_undo.Disabled = not v

    def enable_redo(self, v=True):
        self.btn_redo.Disabled = not v

    def enable_flush(self, v=True):
        self.btn_flush.Disabled = not v

    def add_cmd(self, cmd):
        if self.__last_added > 0:
            for i in xrange(self.__last_added):
                self._cmdlist.Remove(MUIV_List_Remove_First)

        self._cmdlist.InsertSingleString(cmd.getCommandName(), MUIV_List_Insert_Top)
        self._cmdlist.Active = MUIV_List_Active_Top
        self.__last_added = 0
        self.enable_undo()
        self.enable_redo(False)
        self.enable_flush()

    def flush(self):
        self._cmdlist.Clear()
        self._cmdlist.InsertSingleString(MUIX_B + '<start>')
        self._cmdlist.Active = MUIV_List_Active_Top
        self.__last_added = -1
        self.enable_undo(False)
        self.enable_redo(False)
        self.enable_flush(False)

    def undo(self, cmd):
        self._cmdlist.Remove(self.__last_added)
        self._cmdlist.InsertSingleString('\0334' + MUIX_I + cmd.getCommandName(), self.__last_added)
        self.__last_added += 1
        self.enable_undo(self.__last_added < self._cmdlist.Entries.value-1)
        self.enable_redo(True)

    def redo(self, cmd):
        self.__last_added -= 1
        self._cmdlist.Remove(self.__last_added)
        self._cmdlist.InsertSingleString(cmd.getCommandName(), self.__last_added)
        self.enable_undo(True)
        self.enable_redo(self.__last_added > 0)

    def update(self, hp):
        undo = hp.undo_stack
        redo = hp.redo_stack
        self._cmdlist.Quiet = True
        self._cmdlist.Clear()

        self.__last_added = -1
        self._cmdlist.InsertSingleString(MUIX_B + '<start>')

        if not (undo or redo):
            self.enable_flush(False)

            self._cmdlist.Quiet = False
            self._cmdlist.Active = 0
            return

        if undo:
            for cmd in undo:
                self._cmdlist.InsertSingleString(cmd.getCommandName(), MUIV_List_Insert_Top)
            self.enable_redo(True)
        else:
            self.enable_redo(False)

        if redo:
            for cmd in redo:
                self._cmdlist.InsertSingleString('\0334' + MUIX_I + cmd.getCommandName(), MUIV_List_Insert_Top)
            if undo:
                self.__last_added = len(redo)
            self.enable_redo(True)
        else:
            self.enable_redo(False)

        self._cmdlist.Active = MUIV_List_Active_Top
        self._cmdlist.Quiet = False

        if self.__last_added >= 0:
            self._cmdlist.Active = self.__last_added
