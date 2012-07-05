# -*- coding: latin-1 -*-
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

import math

import main
from view.contexts import command, new_context
from utils import _T

@command(_T('open color manager window'))
def cmd_open_colorwin(appctx):
    appctx.app.open_color_mgr()

@command(_T('open brush house window'))
def cmd_open_brush_house(appctx):
    appctx.app.open_brush_house()

@command(_T('open brush editor window'))
def cmd_open_brush_editor(appctx):
    appctx.app.open_brush_editor()

@command(_T('open commands historic window'))
def cmd_open_cmdhist(appctx):
    appctx.app.open_cmdhistoric()

@command(_T('open layer manager window'))
def cmd_open_layer_mgr(appctx):
    appctx.app.open_layer_mgr()
    
@command(_T('open preferences window'))
def cmd_open_preferences(appctx):
    appctx.app.open_preferences()
    
@command(_T('open color manager window'))
def cmd_open_colorwin(appctx):
    appctx.app.open_color_mgr()
    
@command(_T('open document information window'))
def cmd_open_docinfo(appctx):
    appctx.app.open_docinfo()
    
@command(_T('toggle color manager window'))
def cmd_toggle_colorwin(appctx):
    appctx.app.toggle_color_mgr()

@command(_T('toggle brush house window'))
def cmd_toggle_brush_house(appctx):
    appctx.app.toggle_brush_house()

@command(_T('toggle brush editor window'))
def cmd_toggle_brush_editor(appctx):
    appctx.app.toggle_brush_editor()

@command(_T('toggle commands historic window'))
def cmd_toggle_cmdhist(appctx):
    appctx.app.toggle_cmdhistoric()

@command(_T('toggle layer manager window'))
def cmd_toggle_layer_mgr(appctx):
    appctx.app.toggle_layer_mgr()

@command(_T('cleanup workspace'))
def cmd_cleanup_workspace(appctx):
    appctx.app.close_all_non_drawing_windows()

@command(_T('undo'))
def cmd_undo(appctx):
    appctx.app.mediator.sendNotification(main.UNDO)
    
@command(_T('redo'))
def cmd_redo(appctx):
    appctx.app.mediator.sendNotification(main.REDO)
    
@command(_T('new document'))
def cmd_new_doc(appctx):
    appctx.app.mediator.new_document()
    
@command(_T('load document'))
def cmd_load_doc(appctx):
    appctx.app.mediator.load_document()
    
@command(_T('save document'))
def cmd_save_doc(appctx):
    appctx.app.mediator.document_mediator.save_document()
    
@command(_T('save document as'))
def cmd_save_as_doc(appctx):
    appctx.app.mediator.document_mediator.save_as_document()
    
@command(_T('new layer'))
def cmd_new_layer(appctx):
    appctx.app.mediator.layermgr_mediator.add_layer()
    
@command(_T('remove active layer'))
def cmd_rem_active_layer(appctx):
    appctx.app.mediator.layermgr_mediator.remove_active_layer()
    
@command(_T('enter in color pick mode'))
def cmd_enter_color_pick_mode(appctx):
    return 'Pick Mode'
