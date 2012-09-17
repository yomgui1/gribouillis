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

import string

from math import radians

import main
import model

from view.operator import eventoperator, execoperator
from view.keymap import KeymapManager
from utils import _T

from .eventparser import GdkEventParser


NORMAL_DIST = 16
DEFAULT_ROT_ANGLE = radians(22.5)
del radians


##
## Exec operators
##

_default_ope_for_win_tmpl = string.Template("""
@execoperator(_T('open $description'))
def open_$name(ctx):
   ctx.application.open_window("$name")

@execoperator(_T('toggle $description'))
def toggle_$name(ctx):
   ctx.application.toggle_window("$name")
""")

for description, name in [('color manager window', 'ColorManager'),
                          ('brush editor window', 'BrushEditor'),
                          ('brush house window', 'BrushHouse'),
                          ('commands historic window', 'CmdHist'),
                          ('layer manager window', 'LayerManager'),
                          ('preferences window', 'GlobalPrefs')]:
    eval(compile(_default_ope_for_win_tmpl.substitute(description=description,
                                                      name=name),
                 "operators", "exec"))

@execoperator(_T('cleanup workspace'))
def cleanup_workspace(ctx):
    ctx.application.close_all_non_drawing_windows()

@execoperator(_T('undo'))
def hist_undo(ctx):
    ctx.active_docproxy.undo()

@execoperator(_T('redo'))
def hist_redo(ctx):
    ctx.active_docproxy.redo()

@execoperator(_T('flush'))
def hist_flush(ctx):
    ctx.active_docproxy.flush()

@execoperator(_T('clear active layer'))
def clear_active_layer(ctx):
    ctx.active_docproxy.clear_layer()


##
## Event operators
##

@eventoperator(_T("vp-enter"))
def vp_enter(ctx, event, viewport):
    KeymapManager.use_map("Viewport")
    viewport.show_brush_cursor(True)

@eventoperator(_T("vp-leave"))
def vp_leave(ctx, event, viewport):
    viewport.show_brush_cursor(False)

@eventoperator(_T("vp-move-cursor"))
def vp_move_cursor(ctx, event, viewport):
    viewport.repaint_cursor(*GdkEventParser.get_cursor_position(event))

@eventoperator(_T("vp-stroke-start"))
def vp_stroke_start(ctx, event, viewport):
    viewport.update_dev_state(event)
    viewport.show_brush_cursor(False)
    viewport.docproxy.draw_start(viewport.device)
    KeymapManager.save_map()
    KeymapManager.use_map("Stroke")

@eventoperator(_T("vp-stroke-confirm"))
def vp_stroke_confirm(ctx, event, viewport):
    state = viewport.update_dev_state(event)
    viewport.docproxy.draw_end()
    viewport.repaint_cursor(*state.cpos)
    viewport.show_brush_cursor(True)
    KeymapManager.restore_map()

@eventoperator(_T("vp-stroke-append"))
def vp_stroke_append(ctx, event, viewport):
    viewport.update_dev_state(event)
    viewport.docproxy.record()

@eventoperator(_T("vp-scroll-start"))
def vp_scroll_start(ctx, event, viewport):
    state = viewport.update_dev_state(event)
    viewport.show_brush_cursor(False)
    x, y = state.cpos
    viewport.storage['x0'] = x
    viewport.storage['y0'] = y
    viewport.storage['x'] = x
    viewport.storage['y'] = y
    viewport.storage['offset'] = viewport.offset
    KeymapManager.save_map()
    KeymapManager.use_map("Scroll")

@eventoperator(_T("vp-scroll-confirm"))
def vp_scroll_confirm(ctx, event, viewport):
    state = viewport.update_dev_state(event)
    viewport.show_brush_cursor(True)
    viewport.storage.clear()
    KeymapManager.restore_map()

@eventoperator(_T("vp-scroll-delta"))
def vp_scroll_delta(ctx, event, viewport):
    state = viewport.update_dev_state(event)
    x, y = state.cpos
    st = viewport.storage
    viewport.scroll(x - st['x'], y - st['y'])
    st['x'] = x
    st['y'] = y

@eventoperator(_T("vp-scroll-left"))
def vp_scroll_left(ctx, event, viewport):
    viewport.scroll(-NORMAL_DIST, 0)

@eventoperator(_T("vp-scroll-right"))
def vp_scroll_right(ctx, event, viewport):
    viewport.scroll(NORMAL_DIST, 0)

@eventoperator(_T("vp-scroll-up"))
def vp_scroll_up(ctx, event, viewport):
    viewport.scroll(0, -NORMAL_DIST)

@eventoperator(_T("vp-scroll-down"))
def vp_scroll_down(ctx, event, viewport):
    viewport.scroll(0, NORMAL_DIST)

@eventoperator(_T("vp-scale-up"))
def vp_scale_up(ctx, event, viewport):
    viewport.scale_up(*GdkEventParser.get_cursor_position(event))

@eventoperator(_T("vp-scale-down"))
def vp_scale_down(ctx, event, viewport):
    viewport.scale_down(*GdkEventParser.get_cursor_position(event))

@eventoperator(_T("vp-rotate-right"))
def vp_rotate_right(ctx, event, viewport, angle=DEFAULT_ROT_ANGLE):
    viewport.rotate(angle)

@eventoperator(_T("vp-rotate-left"))
def vp_rotate_left(ctx, event, viewport, angle=DEFAULT_ROT_ANGLE):
    viewport.rotate(-angle)

@eventoperator(_T("vp-swap-x"))
def vp_swap_x(ctx, event, viewport):
    pos = viewport._cur_pos
    viewport.swap_x(pos[0])

@eventoperator(_T("vp-swap-y"))
def vp_swap_y(ctx, event, viewport):
    pos = viewport._cur_pos
    viewport.swap_y(pos[1])

@eventoperator(_T("vp-reset-all"))
def vp_reset_all(ctx, event, viewport):
    viewport.reset()

@eventoperator(_T("vp-reset-rotation"))
def vp_reset_rotation(ctx, event, viewport):
    viewport.reset_rotation()

@eventoperator(_T("vp-clear-layer"))
def vp_clear_layer(ctx, event, viewport):
    viewport.docproxy.clear_layer()

@eventoperator(_T("vp-insert-layer"))
def vp_insert_layer(ctx, event, viewport):
    dp = viewport.docproxy
    doc = dp.document
    vo = model.vo.GenericVO(docproxy=dp,
                            pos=doc.index(doc.active)+1,
                            layer=None,
                            name=_T("untitled"))
    dp.sendNotification(main.DOC_LAYER_ADD, vo)
