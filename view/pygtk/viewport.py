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
import gobject
import cairo

from random import random
from math import ceil

import view
import main
import utils

from model.devices import *
from model.profile import Transform
from view import cairo_tools as tools
from view import viewport
from utils import delayedmethod, _T

#from .app import Application
#from .cms import *
from .eventparser import EventParser
from .contexts import ViewportCtx

gdk = gtk.gdk

_KEYVALS = { 0x0020: 'space',
             0xfe03: 'ralt',
             0xff08: 'backspace',
             0xff09: 'tab',
             0xff0d: 'enter',
             0xff13: 'pause',
             0xff14: 'scrolllock',
             0xff1b: 'esc',
             0xff50: 'home',
             0xff51: 'left',
             0xff52: 'up',
             0xff53: 'right',
             0xff54: 'down',
             0xff55: 'page_up',
             0xff56: 'page_down',
             0xff57: 'end',
             0xff63: 'insert',
             0xff67: 'menu',
             0xff7f: 'numlock',
             0xff8d: 'return',
             0xffbe: 'f1',
             0xffbf: 'f2',
             0xffc0: 'f3',
             0xffc1: 'f4',
             0xffc2: 'f5',
             0xffc3: 'f6',
             0xffc4: 'f7',
             0xffc5: 'f8',
             0xffc6: 'f9',
             0xffc7: 'f10',
             0xffc8: 'f11',
             0xffc9: 'f12',
             0xffe1: 'lshift',
             0xffe2: 'rshift',
             0xffe3: 'lcontrol',
             0xffe4: 'rcontrol',
             0xffe5: 'capslock',
             0xffe9: 'lalt',
             0xffeb: 'lcommand',
             0xffec: 'rcommand',
             0xffff: 'delete',
             }

def _check_key(key, evt):
    if not key:
        key = evt.keyval
        if key <= 0xff:
            key = chr(evt.keyval).lower()
        else:
            key = hex(evt.keyval)
    return key


class DocViewport(gtk.DrawingArea, viewport.BackgroundMixin):
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
    _ctx = None
    _swap_x = _swap_y = None
    _debug = 0
    selpath = None

    def __init__(self, win, docproxy, ctx):
        super(DocViewport, self).__init__()
        
        self._win = win
        self._ctx = ctx
        self.docproxy = docproxy
        self.device = InputDevice()

        # Viewport's
        self._docvp = view.DocumentViewPort(docproxy)
        self._toolsvp = view.ToolsViewPort()
        
        self._curvp = tools.Cursor()
        self._curvp.set_radius(docproxy.document.brush.radius_max)

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

        fn = utils.resolve_path(main.Gribouillis.TRANSPARENT_BACKGROUND)
        self.set_background(fn)

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
        
        area = evt.area
        width = self.allocation.width
        height = self.allocation.height

        # Full or limited repaint?
        if self.width != width or self.height != height:
            # full repaint
            self.width = width
            self.height = height

            self._docvp.set_view_size(width, height)
            self._toolsvp.set_view_size(width, height)

            self._docvp.repaint()
            self._toolsvp.repaint()
        else:
            # limited repaint
            self._docvp.repaint(area)
            self._toolsvp.repaint(area)

        # Blitting all surfaces now (Cairo)
        #
        cr = self.window.cairo_create()

        cr.rectangle(*area)
        cr.clip()

        # Paint background first
        if 0:
            cr.set_operator(cairo.OPERATOR_SOURCE)
            dx, dy = self._docvp.offset
            cr.translate(dx, dy)
            if self._backpat:
                cr.set_source(self._backpat)
            else:
                cr.set_source_rgb(*self._backcolor)
            cr.paint()
            cr.translate(-dx, -dy)

        # Paint document surface
        cr.set_operator(cairo.OPERATOR_OVER)
        cr.set_source_surface(self._docvp.cairo_surface, 0, 0)
        cr.paint()

        if self._debug:
            cr.set_source_rgba(1,0,0,random()*.7)
            cr.paint()
            
        # Paint tools surface
        cr.set_source_surface(self._toolsvp.cairo_surface, 0, 0)
        cr.paint()

        # Paint cursor surface
        self._cur_area = None
        if self._cur_on:
            self._cur_area = self._get_cursor_clip(*self._cur_pos)
            self._curvp.render()
            x, y = self._cur_pos
            x -= self._cur_area[2]/2
            y -= self._cur_area[3]/2
            cr.set_source_surface(self._curvp.cairo_surface, x, y)
            cr.paint()
            
        return True

    # Events dispatchers
    #
    
    def _on_button_press(self, widget, evt):
        # ignore double-click events
        if evt.type == gdk.BUTTON_PRESS:
            name = 'mouse-bt-%u-press' % evt.button
            return self._ctx.on_event(EventParser(evt, name))

    def _on_button_release(self, widget, evt):
        # ignore double-click events
        if evt.type == gdk.BUTTON_RELEASE:
            name = 'mouse-bt-%u-release' % evt.button
            return self._ctx.on_event(EventParser(evt, name))
        
    def _on_motion_notify(self, widget, evt):
        return self._ctx.on_event(EventParser(evt, 'cursor-motion'))

    def _on_enter(self, widget, evt):
        self.grab_focus()
        self._ctx.switch(ViewportCtx, viewport=self)
        return self._ctx.on_event(EventParser(evt, 'cursor-enter'))

    def _on_leave(self, widget, evt):
        return self._ctx.on_event(EventParser(evt, 'cursor-leave'))

    def _on_scroll(self, widget, evt):
        name = 'scroll-%s' % evt.direction.value_nick
        return self._ctx.on_event(EventParser(evt, name))

    def _on_key_press(self, widget, evt):
        name = 'key-%s-press' % _check_key(_KEYVALS.get(evt.keyval), evt)
        return self._ctx.on_event(EventParser(evt, name))

    def _on_key_release(self, widget, evt):
        if evt.type == gdk.SCROLL:
            name = 'scroll-%s-release' % evt.direction.value_nick
        else:
            name = 'key-%s-release' % _check_key(_KEYVALS.get(evt.keyval), evt)
        return self._ctx.on_event(EventParser(evt, name))
        
    # Public API
    #

    def enable_motion_events(self, state=True):
        pass # Possible?
    
    def is_tool_hit(self, tool, *pos):
        return self._toolsvp.is_tool_hit(tool, *pos)

    def get_model_distance(self, *a):
        return self._docvp.get_model_distance(*a)

    def get_model_point(self, *a):
        return self._docvp.get_model_point(*a)
    
    @property
    def cursor_position(self):
        return self._cur_pos

    #### Rendering ####

    def redraw(self, clip=None):
        if clip:
            clip = tuple(clip)
        else:
            clip = (0, 0, self.allocation.width, self.allocation.height)
        self.window.invalidate_rect(clip, False)
        self._force_redraw()

    @delayedmethod(0.5)
    def _force_redraw(self):
        self.window.process_updates(False)
    
    def repaint(self, clip=None, redraw=True):
        self._docvp.repaint(clip)
        if redraw:
            self.redraw(clip)

    def repaint_tools(self, clip=None, redraw=False):
        self._toolsvp.repaint(clip)
        if redraw:
            self.redraw(clip)
    
    def repaint_cursor(self, *pos):
        if self._cur_area:
            self._cur_on = False
            self.redraw(self._cur_area)

        # Draw the new one
        self._cur_on = True
        self._cur_pos = pos
        self.redraw(self._get_cursor_clip(*pos))
    
    #### Cursor related ####

    def _get_cursor_clip(self, dx, dy):
        w = self._curvp.width
        h = self._curvp.height
        dx -= w/2
        dy -= h/2
        return dx, dy, w, h

    def set_cursor_radius(self, r):
        self._curvp.set_radius(r)
        self.repaint_cursor(*self._cur_pos)
    
    def show_brush_cursor(self, state=False):
        if state:
            self.repaint_cursor(*self._cur_pos)
        else:
            self._cur_on = False

            # Remove the cursor if was blit and not needed
            if self._cur_area:
                self.redraw(self._cur_area)
        return self._cur_pos
    
    #### View transformations ####

    def reset(self):
        self._swap_x = self._swap_y = None
        self._docvp.reset_view()
        self._curvp.set_scale(self._docvp.scale)
        self.repaint()
        
    def scale_up(self, cx=.0, cy=.0):
        x, y = self._docvp.get_model_point(cx, cy)
        if self._docvp.scale_up():
            self._curvp.set_scale(self._docvp.scale)
            self._docvp.update_matrix()
            x, y = self._docvp.get_view_point(x, y)
            self.scroll(cx-x, cy-y)

    def scale_down(self, cx=.0, cy=.0):
        x, y = self._docvp.get_model_point(cx, cy)
        if self._docvp.scale_down():
            self._curvp.set_scale(self._docvp.scale)
            self._docvp.update_matrix()
            x, y = self._docvp.get_view_point(x, y)
            self.scroll(cx-x, cy-y)

    def scroll(self, *delta):
        self._docvp.scroll(*delta)
        self._docvp.update_matrix()
        self.repaint()

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

    #### Device state handling ####
    def update_dev_state(self, evt):
        state = DeviceState()

        # Get raw device position and pressure
        state.cpos = evt.get_cursor_position()
        state.pressure = evt.get_pressure()

        # Get device tilt
        state.xtilt = evt.get_cursor_xtilt()
        state.ytilt = evt.get_cursor_ytilt()

        # timestamp
        state.time = evt.get_time()

        # vpos = cpos + tools filters
        state.vpos = state.cpos  # TODO

        # Translate to surface coordinates
        pos = self._docvp.get_model_point(*state.vpos)
        state.spos = self.docproxy.get_layer_pos(*pos)

        self.device.add_state(state) # for recording
        return state

    #### Tools ####

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

    #### UI ####

    def to_front(self):
        self.get_toplevel().present()
