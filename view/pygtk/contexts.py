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

from math import radians

import model
import view.context2 as context
import view.cairo_tools as tools

command = context.command
ANGLE = radians(22.5)


class DocWindowCtx(context.Context):
    EVENTS_MAP = {
        }

    @command("doc-hist-undo")
    def hist_undo(ctx):
        ctx.docproxy.undo()

    @command("doc-hist-redo")
    def hist_redo(ctx):
        ctx.docproxy.redo()

    @command("doc-hist-flush")
    def hist_flush(ctx):
        ctx.docproxy.flush()

    @command("increase-brush-radius")
    def more_radius(ctx):
        ctx.docproxy.add_brush_radius_min(0.5)
        ctx.docproxy.add_brush_radius_max(0.5)

    @command("decrease-brush-radius")
    def less_radius(ctx):
        ctx.docproxy.add_brush_radius_min(-0.5)
        ctx.docproxy.add_brush_radius_max(-0.5)


class ViewportCtx(DocWindowCtx):
    EVENTS_MAP = {
        "cursor-enter": "viewport-show-cursor",
        "cursor-leave": "viewport-hide-cursor",
        "mouse-bt-1-press": "viewport-draw-start",
        "mouse-bt-2-press": "viewport-scroll-start",
        "cursor-motion": "viewport-cursor-motion",
        "key-=-press": "viewport-reset",
        "scroll-up": "viewport-scale-up",
        "scroll-down": "viewport-scale-down",
        "key-x-press": "viewport-swap-x",
        "key-y-press": "viewport-swap-y",
        "key-right-press": "viewport-rotate-right",
        "key-left-press": "viewport-rotate-left",
        "key-backspace-press": "viewport-erase-layer",
        }

    @command("viewport-show-cursor")
    def vp_show_cur(ctx):
        ctx.viewport.show_brush_cursor(True)

    @command("viewport-hide-cursor")
    def vp_hide_cur(ctx):
        ctx.viewport.show_brush_cursor(False)

    @command("viewport-draw-start")
    def vp_draw_start(ctx):
        ctx.viewport.update_dev_state(ctx.evt)
        ctx.switch_modal(ViewportDrawingCtx)

    @command("viewport-scroll-start")
    def vp_draw_start(ctx):
        ctx.viewport.update_dev_state(ctx.evt)
        ctx.switch_modal(ViewportScrollCtx)

    @command("viewport-cursor-motion")
    def vp_cursor_move(ctx):
        pos = ctx.evt.get_cursor_position()
        ctx.viewport.repaint_cursor(*pos)

    @command("viewport-reset")
    def vp_reset(ctx):
        ctx.viewport.reset()

    @command("viewport-scale-up")
    def vp_scale_up(ctx):
        pos = ctx.viewport.cursor_position
        ctx.viewport.scale_up(*pos)

    @command("viewport-scale-down")
    def vp_scale_down(ctx):
        pos = ctx.viewport.cursor_position
        ctx.viewport.scale_down(*pos)

    @command("viewport-swap-x")
    def vp_swap_x(ctx):
        pos = ctx.viewport.cursor_position
        ctx.viewport.swap_x(pos[0])

    @command("viewport-swap-y")
    def vp_swap_y(ctx):
        pos = ctx.viewport.cursor_position
        ctx.viewport.swap_y(pos[1])

    @command("viewport-rotate-right")
    def vp_rotate_right(ctx):
        ctx.viewport.rotate(ANGLE)

    @command("viewport-rotate-left")
    def vp_rotate_left(ctx):
        ctx.viewport.rotate(-ANGLE)

    @command("viewport-erase-layer")
    def vp_erase_layer(ctx):
        ctx.docproxy.clear_layer()


class ViewportDrawingCtx(ViewportCtx):
    EVENTS_MAP = {
        "cursor-motion": "drawing-stroke",
        "mouse-bt-1-release": "drawing-stop",
        }

    @staticmethod
    def setup(ctx):
        vp = ctx.viewport
        vp.show_brush_cursor(False)
        vp.docproxy.draw_start(vp.device)

    @command("drawing-stop")
    def stop(ctx):
        vp = ctx.viewport
        vp.docproxy.draw_end()
        ctx.execute("viewport-cursor-motion")
        vp.show_brush_cursor(True)
        ctx.stop_modal()
        ctx.switch(ViewportCtx)

    @command("drawing-stroke")
    def dr_stroke(ctx):
        vp = ctx.viewport
        vp.update_dev_state(ctx.evt)
        vp.docproxy.record()


class ViewportScrollCtx(ViewportCtx):
    EVENTS_MAP = {
        "cursor-motion": "viewport-scroll",
        "mouse-bt-2-release": "scroll-stop",
        "mouse-bt-3-press": "scroll-reset-stop",
        }

    TEXT_FMT = "dx=%d, dy=%d"

    @staticmethod
    def setup(ctx):
        vp = ctx.viewport
        vp.show_brush_cursor(False)
        ctx._x0, ctx._y0 = ctx.evt.get_cursor_position()
        ctx.x = ctx._x0
        ctx.y = ctx._y0
        ctx._offset = vp.offset
        ctx._text = tools.Text()
        ctx._text.set_text(ViewportScrollCtx.TEXT_FMT % (0, 0))
        vp.add_tool(ctx._text)

    @command("scroll-stop")
    def stop(ctx):
        vp = ctx.viewport
        vp.rem_tool(ctx._text)
        ctx.execute("viewport-cursor-motion")
        vp.show_brush_cursor(True)
        ctx.stop_modal()
        ctx.switch(ViewportCtx)

    @command("scroll-reset-stop")
    def scroll_reset(ctx):
        vp = ctx.viewport
        vp.offset = ctx._offset
        ctx.viewport.repaint()
        ctx.execute("scroll-stop")

    @command("viewport-scroll")
    def vp_scroll(ctx):
        x, y = ctx.evt.get_cursor_position()
        vp = ctx.viewport
        d = x - ctx._x0, y - ctx._y0
        ctx._text.set_text(ViewportScrollCtx.TEXT_FMT % d)
        vp.repaint_tools(ctx._text.area, 0)
        vp.scroll(x - ctx.x, y - ctx.y)
        ctx.x = x
        ctx.y = y
