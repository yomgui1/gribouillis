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

from view.context2 import *

class ViewportCtx(Context):
    EVENTS_MAP = {
        "mouse-bt-1-press": "viewport-draw-start",
        "cursor-motion": "viewport-cursor-move",
        }

    @staticmethod
    def setup(ctx):
        if ctx.viewport.device.current:
            ctx.viewport.show_brush_cursor(True)

    @command("viewport-draw-start")
    def draw_start(self, evt):
        self.switch(ViewportDrawingCtx)

    @command("viewport-cursor-move")
    def on_motion(self, evt):
        pos = evt.get_cursor_position()
        self.viewport.repaint_cursor(*pos)


class ViewportDrawingCtx(ModalContext):
    EVENTS_MAP = {
        "cursor-motion": "draw-stroke",
        "mouse-bt-1-release": "draw-stop",
        }

    @staticmethod
    def setup(ctx):
        vp = ctx.viewport

        # Hide cursor during drawing
        vp.show_brush_cursor(False)
        vp.docproxy.draw_start(vp.device)

    @staticmethod
    def cleanup(ctx):
        vp = ctx.viewport
        vp.docproxy.draw_end(vp.device)
        vp.show_brush_cursor(True)

    @command("draw-stop")
    def stop(self, evt):
        self.switch(ViewportCtx)
    
    @command("draw-stroke")
    def draw(self, evt):
        vp = self.viewport
        vp.docproxy.record(vp.device.current)
        
