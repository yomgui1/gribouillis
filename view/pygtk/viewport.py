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

import gtk
import gtk.gdk as gdk
import cairo

from math import floor

import view
import view.viewport
import view.context as ctx
import view.cairo_tools as tools

import main
import utils
import model.devices

from view.keymap import KeymapManager

from .eventparser import GdkEventParser

def _check_key(key, evt):
    if not key:
        key = evt.keyval
        if key <= 0xff:
            key = chr(evt.keyval).lower()
        else:
            key = hex(evt.keyval)
    return key


class DocViewport(gtk.DrawingArea, view.viewport.BackgroundMixin):
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
    storage = {}
    selpath = None

    def __init__(self, win, docproxy=None):
        super(DocViewport, self).__init__()

        self._win = win
        self.docproxy = docproxy
        self.device = model.devices.InputDevice()

        self._km = KeymapManager()
        self._km.use_map("Viewport")

        # Viewport's
        self._docvp = view.DocumentViewPort()
        self._toolsvp = view.ToolsViewPort()
        self._curvp = tools.Cursor()
        self._curvp.render()

        # Aliases
        self.get_view_area = self._docvp.get_view_area
        self.enable_fast_filter = self._docvp.enable_fast_filter

        self.set_events(gdk.EXPOSURE_MASK
                        | gdk.BUTTON_PRESS_MASK
                        | gdk.BUTTON_RELEASE_MASK
                        | gdk.POINTER_MOTION_MASK
                        | gdk.SCROLL_MASK
                        | gdk.ENTER_NOTIFY_MASK
                        | gdk.LEAVE_NOTIFY_MASK
                        | gdk.KEY_PRESS_MASK
                        | gdk.KEY_RELEASE_MASK)

        self.set_can_focus(True)
        self.set_sensitive(True)

        self.connect("expose-event"        , self._on_expose)
        self.connect("motion-notify-event" , self._on_motion_notify)
        self.connect("button-press-event"  , self._on_button_press)
        self.connect("button-release-event", self._on_button_release)
        self.connect("scroll-event"        , self._on_scroll)
        self.connect("enter-notify-event"  , self._on_enter)
        self.connect("leave-notify-event"  , self._on_leave)
        self.connect("key-press-event"     , self._on_key_press)
        self.connect("key-release-event"   , self._on_key_release)

        if docproxy is not None:
            self.set_docproxy(docproxy)
    
    # Paint function

    def _paint_composite(self, cr, clip):
        cr.save()
        cr.rectangle(*clip)
        cr.clip()

        # Paint document surface
        cr.set_source_surface(self._docvp.cairo_surface, 0, 0)
        cr.paint()

        # Paint tools surface
        cr.set_source_surface(self._toolsvp.cairo_surface, 0, 0)
        cr.paint()

        cr.restore()

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

        area = evt.area
        
        width = self.allocation.width
        height = self.allocation.height

        # surface resized?
        if self.width != width or self.height != height:
            # full repaint
            self.width = width
            self.height = height

            self._docvp.set_view_size(width, height)
            self._toolsvp.set_view_size(width, height)

            self._docvp.repaint()
            self._toolsvp.repaint()

        # display doc + tools surfaces (Cairo)
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

    # Events dispatchers

    def _on_motion_notify(self, widget, evt):
        mods = evt.state.value_nicks
        if 'mod2-mask' in mods:
            mods.remove('mod2-mask')
        return self._km.process(evt, 'cursor-motion', mods, viewport=self)

    def _on_enter(self, widget, evt):
        self.grab_focus()
        ctx.active_viewport = self
        return self._km.process(evt, 'cursor-enter', viewport=self)

    def _on_leave(self, widget, evt):
        return self._km.process(evt, 'cursor-leave', viewport=self)

    def _on_button_press(self, widget, evt):
        if evt.type == gdk.BUTTON_PRESS:
            mods = evt.state.value_nicks
            if 'mod2-mask' in mods:
                mods.remove('mod2-mask')
            return self._km.process(evt, 'button-press-%u' % evt.button,
                                    mods, viewport=self)

    def _on_button_release(self, widget, evt):
        if evt.type == gdk.BUTTON_RELEASE:
            mods = evt.state.value_nicks
            if 'mod2-mask' in mods:
                mods.remove('mod2-mask')
            return self._km.process(evt, 'button-release-%u' % evt.button,
                                    mods, viewport=self)

    def _on_scroll(self, widget, evt):
        mods = evt.state.value_nicks
        if 'mod2-mask' in mods:
            mods.remove('mod2-mask')
        return self._km.process(evt, 'scroll-%s' % evt.direction.value_nick,
                                mods, viewport=self)

    def _on_key_press(self, widget, evt):
        mods = evt.state.value_nicks
        if 'mod2-mask' in mods:
            mods.remove('mod2-mask')
        return self._km.process(evt, 'key-press-%s' % gdk.keyval_name(evt.keyval),
                                mods, viewport=self)

    def _on_key_release(self, widget, evt):
        mods = evt.state.value_nicks
        if 'mod2-mask' in mods:
            mods.remove('mod2-mask')
        if evt.type == gdk.SCROLL:
            name = 'scroll-release-%s' % evt.direction.value_nick,
        else:
            name = 'key-release-%s' % gdk.keyval_name(evt.keyval)
        return self._km.process(evt, name, mods, viewport=self)

    # Public API

    def set_docproxy(self, docproxy):
        self.docproxy = docproxy
        self._docvp.docproxy = docproxy
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

    @utils.delayedmethod(0.5)
    def _force_redraw(self):
        self.window.process_updates(False)

    def redraw(self, clip=None):
        if clip:
            clip = tuple(clip)
        else:
            clip = (0, 0, self.allocation.width, self.allocation.height)
        self.window.invalidate_rect(clip, False)
        self._force_redraw()

    def repaint(self, clip=None, redraw=True):
        self._docvp.repaint(clip)
        if redraw:
            self.redraw(clip)

    def repaint_tools(self, clip=None, redraw=False):
        self._toolsvp.repaint(clip)
        if redraw:
            self.redraw(clip)

    def repaint_cursor(self, *pos):
        if self._cur_on:
            # remove previous blit
            self.redraw(self._cur_area)
            self._cur_area = None

            # draw at the new position
            self._cur_pos = pos
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
        self._curvp.render()
        self.repaint_cursor(*self._cur_pos)

    def show_brush_cursor(self, state=False):
        self._cur_on = state

        if state:
            self.repaint_cursor(*self._cur_pos)

        # Remove the cursor if was blit and not needed
        elif self._cur_area:
            self.redraw(self._cur_area)
            self._cur_area = None

        return self._cur_pos


    # View transformations

    def reset(self):
        self._swap_x = self._swap_y = None
        self._docvp.reset_view()
        self._curvp.set_scale(self._docvp.scale)
        self._curvp.render()
        self.repaint()

    def reset_rotation(self):
        self._docvp.reset_rotation()
        self.repaint()

    def scale_up(self, cx=.0, cy=.0):
        x, y = self._docvp.get_model_point(cx, cy)
        if self._docvp.scale_up():
            self._curvp.set_scale(self._docvp.scale)
            self._curvp.render()
            self._docvp.update_matrix()
            x, y = self._docvp.get_view_point(x, y)
            self._docvp.scroll(int(cx-x), int(cy-y))
            self._docvp.update_matrix()
            self._docvp.repaint()
            self.redraw()

    def scale_down(self, cx=.0, cy=.0):
        x, y = self._docvp.get_model_point(cx, cy)
        if self._docvp.scale_down():
            self._curvp.set_scale(self._docvp.scale)
            self._curvp.render()
            self._docvp.update_matrix()
            x, y = self._docvp.get_view_point(x, y)
            self.scroll(int(cx-x), int(cy-y))

    def scroll(self, *delta):
        dvp = self._docvp
        dvp.scroll(*delta)
        dvp.update_matrix()

        dx, dy = delta

        # Scroll the internal docvp buffer
        dvp.pixbuf.scroll(dx, dy)

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

        w = self.width
        h = self.height

        f = dvp.repaint

        if dy > 0:
            f([0, 0, w, dy]) #3
        elif dy < 0:
            f([0, h+dy, w, h]) #4

        if dx > 0:
            if dy >= 0:
                f([0, dy, dx, h]) #1
            else:
                f([0, 0, dx, h+dy]) #1
        elif dx < 0:
            if dy >= 0:
                f([w+dx, dy, w, h]) #2
            else:
                f([w+dx, 0, w, h+dy]) #2

        self.redraw()

    def rotate(self, angle):
        self._docvp.rotate(angle)
        self._docvp.update_matrix()
        self.repaint()

    def swap_x(self, x):
        if self._swap_x is None:
            self._swap_x = x
            self._docvp.swap_x(self._swap_x)
        else:
            self._docvp.swap_x(self._swap_x)
            self._swap_x = None
        self._docvp.update_matrix()
        self.repaint()

    def swap_y(self, y):
        if self._swap_y is None:
            self._swap_y = y
            self._docvp.swap_y(self._swap_y)
        else:
            self._docvp.swap_y(self._swap_y)
            self._swap_y = None
        self._docvp.update_matrix()
        self.repaint()


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
        self._docvp.update_matrix()

    offset = property(get_offset, set_offset)
