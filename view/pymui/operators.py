# -*- coding: latin-1 -*-
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

import math

import main
import model

from view.operator import operator
from utils import _T
from .eventparser import MUIEventParser
from .const import TABLET_TOOLTYPE_ERASER


# =============================================================================
# Exec operators
#


@operator(_T('undo'))
def hist_undo(ctx):
    ctx.active_docproxy.undo()


@operator(_T('redo'))
def hist_redo(ctx):
    ctx.active_docproxy.redo()


@operator(_T('flush'))
def hist_flush(ctx):
    ctx.active_docproxy.flush()


@operator(_T('Swap X-axis active viewport'))
def actvp_swap_x(ctx):
    vp = ctx.active_viewport
    vp.swap_x(vp.width / 2)


@operator(_T('Swap Y-axis active viewport'))
def actvp_swap_y(ctx):
    vp = ctx.active_viewport
    vp.swap_y(vp.height / 2)


@operator(_T('Rotate active viewport'))
def actvp_rotate(ctx, angle):
    vp = ctx.active_viewport
    vp.rotate(angle)


@operator(_T('clear active layer'))
def clear_active_layer(ctx):
    ctx.active_docproxy.clear_layer()


@operator(_T('reset active viewport'))
def reset_active_viewport(ctx):
    ctx.active_viewport.reset_transforms()


# ----


@operator(_T('cleanup workspace'))
def cmd_cleanup_workspace(ctx):
    ctx.app.close_all_non_drawing_windows()


@operator(_T('new document'))
def cmd_new_doc(ctx):
    ctx.app.mediator.new_document()


@operator(_T('load document'))
def cmd_load_doc(ctx):
    ctx.app.mediator.load_document()


@operator(_T('save document'))
def cmd_save_doc(ctx):
    ctx.app.mediator.document_mediator.save_document()


@operator(_T('save document as'))
def cmd_save_as_doc(ctx):
    ctx.app.mediator.document_mediator.save_as_document()


@operator(_T('new layer'))
def cmd_new_layer(ctx):
    ctx.app.mediator.layermgr_mediator.add_layer()


@operator(_T('remove active layer'))
def cmd_rem_active_layer(ctx):
    ctx.app.mediator.layermgr_mediator.remove_active_layer()


@operator(_T('enter in color pick mode'))
def cmd_enter_color_pick_mode(ctx):
    return 'Pick Mode'


# =============================================================================
# Event operators
#


@operator(_T('toggle fullscreen mode'))
def toggle_fullscreen(ctx, event, viewport=None):
    vp = viewport or ctx.active_viewport
    ctx.app.toggle_fullscreen(vp.WindowObject.object)


@operator(_T("viewport enter"))
def vp_enter(ctx, event, viewport):
    ctx.active_viewport = viewport
    ctx.keymap.use("Viewport")
    viewport.enable_motion_events(True)
    viewport._do_rulers()
    viewport.show_brush_cursor(True)
    if ctx.active_docproxy != viewport.docproxy:
        ctx.app.mediator.sendNotification(main.DOC_ACTIVATE, viewport.docproxy)


@operator("vp-leave")
def vp_leave(ctx, event, viewport):
    viewport.enable_motion_events(False)
    viewport.show_brush_cursor(False)


@operator(_T("Update viewport cursor position"))
def vp_move_cursor(ctx, event, viewport):
    tool = MUIEventParser.get_tooltype(event)

    # trigger on tool change
    if tool != ctx.tool:
        ctx.tool = tool

        # Set erase mode to full if eraser tool used
        if tool == TABLET_TOOLTYPE_ERASER:
            brush = ctx.erase_brush
        else:
            brush = ctx.brush

        # we don't want that this changes becomes visible,
        # so use non-notifying API to update document's brush
        viewport.docproxy.document.brush.set_from_brush(brush)

        viewport.set_cursor_radius(brush.radius_max)

    pos = viewport.get_view_pos(*MUIEventParser.get_screen_position(event))
    viewport.repaint_cursor(*pos)


@operator("vp-stroke-start")
def vp_stroke_start(ctx, event, viewport):
    viewport.get_device_state(event)
    viewport.show_brush_cursor(False)
    viewport.docproxy.draw_start(viewport.device)
    KeymapManager.save_map()
    KeymapManager.use_map("Stroke")


@operator("vp-stroke-confirm")
def vp_stroke_confirm(ctx, event, viewport):
    state = viewport.get_device_state(event)
    viewport.docproxy.draw_end()
    viewport.show_brush_cursor(True)
    KeymapManager.restore_map()


@operator("vp-stroke-append")
def vp_stroke_append(ctx, event, viewport):
    viewport.get_device_state(event)
    viewport.docproxy.record()


@operator(_T("Scale-down at cursor position"))
def scale_down_at_cursor(ctx, event, viewport):
    pos = MUIEventParser.get_screen_position(event)
    viewport.scale_down(*viewport.get_view_pos(*pos))


@operator(_T("Scale-up at cursor position"))
def scale_up_at_cursor(ctx, event, viewport):
    pos = MUIEventParser.get_screen_position(event)
    viewport.scale_up(*viewport.get_view_pos(*pos))


@operator(_T("Scroll viewport start"))
def vp_scroll_start(ctx, event, viewport):
    x, y = viewport.get_device_state(event).cpos
    viewport.show_brush_cursor(False)
    KeymapManager.save_map()
    KeymapManager.use_map("Scroll")
    ctx.storage = dict(x=x, y=y, x0=x, y0=y, offset=viewport.offset)


@operator(_T("Scroll viewport on cursor motion"))
def vp_scroll_on_motion(ctx, event, viewport):
    x, y = viewport.get_device_state(event).cpos
    d = ctx.storage
    viewport.scroll(x - d['x'], y - d['y'])
    d['x'] = x
    d['y'] = y


@operator(_T("Scroll viewport confirm"))
def vp_scroll_confirm(ctx, event, viewport):
    del ctx.storage
    cpos = viewport.get_device_state(event).cpos
    viewport.repaint_cursor(*cpos)
    viewport.show_brush_cursor(True)
    KeymapManager.restore_map()


@operator(_T("Scroll viewport cancel"))
def vp_scroll_cancel(ctx, event, viewport):
    viewport.offset = ctx.storage['offset']
    del ctx.storage
    cpos = viewport.get_device_state(event).cpos
    viewport.repaint_cursor(*cpos)
    viewport.show_brush_cursor(True)
    viewport.repaint()
    KeymapManager.restore_map()
