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

from view.operator import operator
from utils import _T
from .eventparser import GdkEventParser

SCROLL_DIST = 16
DEFAULT_ROT_ANGLE = radians(22.5)
del radians


##
## Exec operators
##

'''
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
'''

@operator(_T('cleanup workspace'))
def cleanup_workspace(ctx):
    ctx.application.close_all_non_drawing_windows()

@operator(_T('undo'))
def hist_undo(ctx):
    ctx.active_docproxy.undo()

@operator(_T('redo'))
def hist_redo(ctx):
    ctx.active_docproxy.redo()

@operator(_T('flush'))
def hist_flush(ctx):
    ctx.active_docproxy.flush()

@operator(_T('clear active layer'))
def clear_active_layer(ctx):
    ctx.active_docproxy.clear_layer()

@operator(_T('quit'))
def quit_request(ctx):
    ctx.app_mediator.quit()


##
## Event operators
##

@operator(_T("vp-enter"))
def vp_enter(ctx, event):
    ctx.active_viewport.show_brush_cursor(True)

@operator(_T("vp-leave"))
def vp_leave(ctx, event):
    ctx.active_viewport.show_brush_cursor(False)

@operator(_T("vp-move-cursor"))
def vp_move_cursor(ctx, event):
    ctx.active_viewport.repaint_cursor(*GdkEventParser.get_cursor_position(event))

@operator(_T("vp-stroke-start"))
def vp_stroke_start(ctx, event):
    vp = ctx.active_viewport
    vp.update_dev_state(event)
    vp.show_brush_cursor(False)
    vp.docproxy.draw_start(vp.device)
    ctx.keymgr.push('Brush-Stroke')

@operator(_T("vp-stroke-confirm"))
def vp_stroke_confirm(ctx, event):
    vp = ctx.active_viewport
    state = vp.update_dev_state(event)
    vp.docproxy.draw_end()
    vp.show_brush_cursor(True, state.cpos)
    ctx.keymgr.pop()

@operator(_T("vp-stroke-append"))
def vp_stroke_append(ctx, event):
    vp = ctx.active_viewport
    vp.update_dev_state(event)
    vp.docproxy.record()

@operator(_T("vp-scroll-start"))
def vp_scroll_start(ctx, event):
    vp = ctx.active_viewport
    state = vp.update_dev_state(event)
    vp.show_brush_cursor(False)
    x, y = state.cpos
    ctx._scroll = dict(x0=x, y0=y, x=x, y=y, offset=vp.offset)
    ctx.keymgr.push('Viewport-Scroll')

@operator(_T("vp-scroll-confirm"))
def vp_scroll_confirm(ctx, event):
    vp = ctx.active_viewport
    state = vp.update_dev_state(event)
    vp.show_brush_cursor(True, state.cpos)
    del ctx._scroll
    ctx.keymgr.pop()

@operator(_T("vp-scroll-delta"))
def vp_scroll_delta(ctx, event):
    vp = ctx.active_viewport
    state = vp.update_dev_state(event)
    x, y = state.cpos
    d = ctx._scroll
    vp.scroll(x - d['x'], y - d['y'])
    d['x'] = x
    d['y'] = y

@operator(_T("vp-scroll-left"))
def vp_scroll_left(ctx, event):
    ctx.active_viewport.scroll(-SCROLL_DIST, 0)

@operator(_T("vp-scroll-right"))
def vp_scroll_right(ctx, event):
    ctx.active_viewport.scroll(SCROLL_DIST, 0)

@operator(_T("vp-scroll-up"))
def vp_scroll_up(ctx, event):
    ctx.active_viewport.scroll(0, -SCROLL_DIST)

@operator(_T("vp-scroll-down"))
def vp_scroll_down(ctx, event):
    ctx.active_viewport.scroll(0, SCROLL_DIST)

@operator(_T("vp-scale-up"))
def vp_scale_up(ctx, event,):
    ctx.active_viewport.scale_up(*GdkEventParser.get_cursor_position(event))

@operator(_T("vp-scale-down"))
def vp_scale_down(ctx, event):
    ctx.active_viewport.scale_down(*GdkEventParser.get_cursor_position(event))

@operator(_T("vp-rotate-right"))
def vp_rotate_right(ctx, event, angle=DEFAULT_ROT_ANGLE):
    ctx.active_viewport.rotate(angle)

@operator(_T("vp-rotate-left"))
def vp_rotate_left(ctx, event, angle=DEFAULT_ROT_ANGLE):
    ctx.active_viewport.rotate(-angle)

@operator(_T("vp-swap-x"))
def vp_swap_x(ctx, event):
    vp = ctx.active_viewport
    pos = vp._cur_pos
    vp.swap_x(pos[0])

@operator(_T("vp-swap-y"))
def vp_swap_y(ctx, event):
    vp = ctx.active_viewport
    pos = vp._cur_pos
    vp.swap_y(pos[1])

@operator(_T("vp-reset-all"))
def vp_reset_all(ctx, event):
    ctx.active_viewport.reset()

@operator(_T("vp-reset-rotation"))
def vp_reset_rotation(ctx, event):
    ctx.active_viewport.reset_rotation()

@operator(_T("vp-clear-layer"))
def vp_clear_layer(ctx, event):
    ctx.active_viewport.docproxy.clear_layer()

@operator(_T("vp-insert-layer"))
def vp_insert_layer(ctx, event):
    dp = ctx.active_viewport.docproxy
    doc = dp.document
    vo = model.vo.GenericVO(docproxy=dp,
                            pos=doc.index(doc.active)+1,
                            layer=None,
                            name=_T("untitled"))
    dp.sendNotification(main.DOC_LAYER_ADD, vo)
