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
from gi.repository import Gdk as gdk
from gi.repository import GdkPixbuf

import cairo
import random

from math import floor

import view
import view.render
import view.context as ctx
import view.cairo_tools as tools

import main
import utils
import model.devices

from model import _pixbuf
from model._cutils import Area
from .eventparser import GdkEventParser


def _check_key(key, evt):
    if not key:
        key = evt.keyval
        if key <= 0xff:
            key = chr(evt.keyval).lower()
        else:
            key = hex(evt.keyval)
    return key


class DocViewport(gtk.DrawingArea, view.render.BackgroundMixin):
    """DocDisplayArea class.

    This class is responsible to display a given document.
    It owns and handles display properties like affine transformations,
    background, and so on.
    It handles user events from input devices to modify the document.
    This class can also dispay tools and cursor.
    """

    width = height = None

    _cur_area = None
    _cur_pos = (0, 0)
    _cur_on = False
    _swap_x = _swap_y = None
    _debug = 0
    selpath = None
    docproxy = None
    view_area = None # set during expose

    __new_cairo_surface = cairo.ImageSurface.create_for_data

    def __init__(self, win, docproxy=None):
        super(DocViewport, self).__init__()

        self._win = win
        self.device = model.devices.InputDevice()

        # Document data
        self._doc_pb = None
        self._doc_gtk_pb = None
        self._docvp = view.ViewState()
        self._docre = view.render.DocumentRender()

        self._tools_pb = None
        self._toolsvp = view.ViewState()
        self._toolsre = view.render.ToolsCairoRender()

        self._curvp = tools.Cursor()
        self._curvp.repaint()

        # Aliases
        self.get_view_area = self._docvp.get_view_area

        self.set_events(gdk.EventMask.EXPOSURE_MASK
                        | gdk.EventMask.BUTTON_PRESS_MASK
                        | gdk.EventMask.BUTTON_RELEASE_MASK
                        | gdk.EventMask.POINTER_MOTION_MASK
                        | gdk.EventMask.SCROLL_MASK
                        | gdk.EventMask.ENTER_NOTIFY_MASK
                        | gdk.EventMask.LEAVE_NOTIFY_MASK
                        | gdk.EventMask.KEY_PRESS_MASK
                        | gdk.EventMask.KEY_RELEASE_MASK)

        self.set_can_focus(True)
        self.set_sensitive(True)

        self.connect("draw"        , self._on_expose)
        self.connect("motion-notify-event" , self._on_vp_event)
        self.connect("button-press-event"  , self._on_vp_event)
        self.connect("button-release-event", self._on_vp_event)
        self.connect("scroll-event"        , self._on_vp_event)
        self.connect("enter-notify-event"  , self._on_enter)
        self.connect("leave-notify-event"  , self._on_leave)
        self.connect("key-press-event"     , self._on_vp_event)
        self.connect("key-release-event"   , self._on_vp_event)

        if docproxy is not None:
            self.set_docproxy(docproxy)

    # Paint function

    def _on_expose(self, widget, evt):
        "Partial or full viewport repaint"

        # Repainting each layers is the most CPU comsuming task.
        # So the idea is to limit painting surface to the maximum,
        # even if more pre-computation must be done for that.
        # So the painting pipeline is mainly based on rectangulars
        # clipping computations to find the exact surface to redraw.
        #
        # GTK Note: by default widgets paint is double-buffered.
        # So we don't have to support that here.
        #

        area = Area(*evt.area)
        width = self.allocation.width
        height = self.allocation.height

        # full repaint on surface size change
        if self.width != width or self.height != height:
            # free memory
            del self._doc_gtk_pb, self._doc_pb
            #del self._tools_cairo_sf, self._tools_pb

            self.width = width
            self.height = height
            self.view_area = (0, 0, width, height)

            # reconstruct viewports and rasterize
            self._doc_gtk_pb = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, width, height)
            self._doc_pb = _pixbuf.pixbuf_from_gdk_pixbuf(self._doc_gtk_pb, _pixbuf.FORMAT_RGBA8_NOA)
            self._docre.set_pixbuf(self._doc_pb)

            self._docre.reset(width, height)
            self._docvp.set_size(width, height)
            self._doc_offset = self._docvp.offset
            self._doc_scale = self._docvp.scale_idx

            #self._tools_pb = _pixbuf.Pixbuf(_pixbuf.FORMAT_RGBA8, width, height)
            #self._toolsvp.set_view_size(width, height)
            #self._tools_cairo_sf = self.__new_cairo_surface(self._tools_pb, cairo.FORMAT_ARGB32, width, height)
            #self._toolsvp.repaint()

        # Cairo compositing (doc + tools)
        cr = self.window.cairo_create()
        cr.set_operator(cairo.OPERATOR_OVER)
        self._paint_composite(cr, area)

        # paint cursor surface at its new position (if not done yet)
        if self._cur_on and not self._cur_area:
            area = self._get_cursor_clip(*self._cur_pos)
            x, y = self._cur_pos
            x -= area[2]/2.
            y -= area[3]/2.
            cr.set_source_surface(self._curvp.cairo_surface, x, y)
            cr.paint()

            # area to erase the cursor
            self._cur_area = (int(floor(x)), int(floor(y)), area[2]+2, area[3]+2)

        return True

    def _paint_composite(self, cr, clip):
        # Paint document surface

        m2v_mat = self._docvp.view_matrix
        v2m_mat = self._docvp.model_matrix

        # We uses here the knownledge of backend
        # to do some optimizations
        #ox, oy = self._doc_offset
        #nx, ny = self._doc_offset = self._docvp.offset
        #os = self._doc_scale
        #ns = self._doc_scale = self._docvp.scale_idx

        if 0 and os == ns and (nx != ox or ny != oy):
            # Only translation
            self._render_scroll(int(nx - ox), int(ny - oy), mat)
        else:
            # Full transformation
            self._docre.render(clip, m2v_mat)

        self.window.draw_pixbuf(None, self._doc_gtk_pb, 0, 0, 0, 0, dither=gdk.RGB_DITHER_MAX)

        # Paint tools surface

        #cr.set_source_surface(self._tools_cairo_sf, 0, 0)

        #cr.rectangle(*clip)
        #cr.set_source_rgba(0, 0, random.random(), 0.6)
        #cr.paint()

    # Events dispatchers

    def _on_enter(self, widget, evt):
        self.grab_focus()
        ctx.active_viewport = self
        ctx.keymgr.push('Viewport')
        ctx.keymgr.process(evt.type.value_nick, evt)

    def _on_leave(self, widget, evt):
        # I don't set active_viewport to None as leaving a viewport
        # is not necessary followed by entering another VP.
        # So we let a valid VP in the context.
        ctx.keymgr.process(evt.type.value_nick, evt)
        ctx.keymgr.pop()

    def _on_vp_event(self, widget, evt):
        if ctx.active_viewport is self:
            ctx.keymgr.process(evt.type.value_nick, evt)

    # Public API

    def set_docproxy(self, docproxy):
        if self.docproxy is docproxy: return
        if self.docproxy:
            self.docproxy.release()
        docproxy.obtain()
        self.docproxy = docproxy
        self._docre.docproxy = docproxy
        fill = docproxy.document.fill or utils.resolve_path(main.Gribouillis.TRANSPARENT_BACKGROUND)
        self.set_background(fill)
        self.width = self.height = None

    def get_model_distance(self, *a):
        return self._docvp.get_model_distance(*a)

    def get_model_point(self, *a):
        return self._docvp.get_model_point(*a)

    def is_tool_hit(self, tool, *pos):
        return self._toolsvp.is_tool_hit(tool, *pos)

    @property
    def cursor_position(self):
        return self._cur_pos


    # Rendering

    def _render_scroll(self, dx, dy, mat):
        ## Compute and render only damaged area
        #
        # 4 damaged rectangles possible,
        # but in fact only two per delta:
        #
        # +==================+
        # |        #3        |      #1 exists if dx > 0
        # |----+========+----|      #2 exists if dx < 0
        # |    |        |    |      #3 exists if dy > 0
        # | #1 |   OK   | #2 |      #4 exists if dy < 0
        # |    |        |    |
        # |----+========+----|
        # |        #4        |
        # +==================+
        #

        re = self._docre
        w = self.width
        h = self.height

        if dy > 0:
            re.render(Area(0, 0, w, dy), mat) #3
        elif dy < 0:
            re.render(Area(0, h+dy, w, h), mat) #4

        if dx > 0:
            if dy >= 0:
                re.render(Area(0, dy, dx, h), mat) #1
            else:
                re.render(Area(0, 0, dx, h+dy), mat) #1
        elif dx < 0:
            if dy >= 0:
                re.render(Area(w+dx, dy, w, h), mat) #2
            else:
                re.render(Area(w+dx, 0, w, h+dy), mat) #2

    def redraw(self, clip=None):
        if clip is None:
            self.queue_draw()
        else:
            self.queue_draw_area(*clip)

    def forced_redraw(self, clip=None):
        if clip is None:
            self.window.invalidate_rect(self.view_area, False)
        else:
            self.window.invalidate_rect(tuple(clip), False)
        self.window.process_updates(False)

    def repaint_doc(self, clip=None, redraw=True):
        self._docre.render(clip, self._docvp.view_matrix)
        if redraw:
            self.redraw(clip)

    def repaint_tools(self, clip=None, redraw=False):
        return

        self._toolsvp.repaint(clip)
        if redraw:
            self.redraw(clip)

    def repaint_cursor(self, *pos):
        # remove previous blit
        self.redraw(self._cur_area)

        # draw at the new position
        self._cur_pos = pos
        if self._cur_on:
            self._cur_area = None
            self.redraw(self._get_cursor_clip(*pos))

    # Cursor related

    def _get_cursor_clip(self, dx, dy):
        w = self._curvp.width
        h = self._curvp.height
        dx -= w/2
        dy -= h/2
        return dx, dy, w, h

    def set_cursor_radius(self, r):
        self._curvp.set_radius(r)
        self._curvp.repaint()
        self.repaint_cursor(*self._cur_pos)

    def show_brush_cursor(self, state=False, pos=None):
        self._cur_on = state
        self.repaint_cursor(*(pos or self._cur_pos))
        return self._cur_pos


    # View transformations

    def reset(self):
        self._swap_x = self._swap_y = None
        self._docvp.reset_view()
        self._curvp.set_scale(self._docvp.scale)
        self._curvp.repaint()
        self._cur_area = None
        self.repaint_doc()

    def reset_rotation(self):
        self._docvp.reset_rotation()
        self.repaint_doc()

    def scale_up(self, cx=.0, cy=.0):
        # Zooming is space origin centered,
        # but we want it centered around (cx, cy)
        # So a scroll will be made to compensate
        # the movement of this point after scaling.
        x, y = self._docvp.model_matrix.transform_point(cx, cy)
        if self._docvp.scale_up():
            x, y = self._docvp.view_matrix.transform_point(x, y)
            self._docvp.scroll(int(cx-x), int(cy - y))

            # Scale cursor display as well
            self._curvp.set_scale(self._docvp.scale_factor)
            self._curvp.repaint()
            self._cur_area = None # force cursor display

            # Refresh display
            self.redraw()

    def scale_down(self, cx=.0, cy=.0):
        x, y = self._docvp.model_matrix.transform_point(cx, cy)
        if self._docvp.scale_down():
            x, y = self._docvp.view_matrix.transform_point(x, y)
            self._docvp.scroll(int(cx-x), int(cy - y))
            self._curvp.set_scale(self._docvp.scale_factor)
            self._curvp.repaint()
            self._cur_area = None
            self.redraw()

    def scroll(self, *delta):
        # Scroll the view model
        self._docvp.scroll(*delta)
        self.redraw()

    def rotate(self, angle):
        self._docvp.rotate(angle)
        self.repaint_doc()

    def swap_x(self, x):
        if self._swap_x is None:
            self._swap_x = x
            self._docvp.swap_x(self._swap_x)
        else:
            self._docvp.swap_x(self._swap_x)
            self._swap_x = None
        self.repaint_doc()

    def swap_y(self, y):
        if self._swap_y is None:
            self._swap_y = y
            self._docvp.swap_y(self._swap_y)
        else:
            self._docvp.swap_y(self._swap_y)
            self._swap_y = None
        self.repaint_doc()


    # Device state handling

    def update_dev_state(self, evt, new_state=model.devices.DeviceState):
        state = new_state()

        # Get raw device position and pressure
        state.cpos = GdkEventParser.get_cursor_position(evt)
        state.pressure = GdkEventParser.get_pressure(evt)

        # Get device tilt
        state.xtilt = GdkEventParser.get_cursor_xtilt(evt)
        state.ytilt = GdkEventParser.get_cursor_ytilt(evt)

        # timestamp
        state.time = GdkEventParser.get_time(evt)

        # vpos = cpos + tools filters
        state.vpos = state.cpos  # TODO

        # Translate to surface coordinates
        pos = self._docvp.get_model_point(*state.vpos)
        state.spos = self.docproxy.get_layer_pos(*pos)

        self.device.add_state(state) # for recording
        return state


    # Tools

    def add_tool(self, tool):
        self._toolsvp.add_tool(tool)
        self.redraw(tool.area)

    def rem_tool(self, tool):
        area = tool.area # saving because may be destroyed during rem_tool
        self._toolsvp.rem_tool(tool)
        self.redraw(area)

    @property
    def tools(self):
        return self._toolsvp.tools

    @property
    def center(self):
        return self.width/2, self.height/2

    def get_offset(self):
        return self._docvp.offset

    def set_offset(self, offset):
        self._docvp.offset = offset

    offset = property(get_offset, set_offset)
