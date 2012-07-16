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
#from .eventparser import EventParser

gdk = gtk.gdk


class DocViewport(gtk.DrawingArea, viewport.BackgroundMixin):
    """DocDisplayArea class.

    This class is responsible to display a given document.
    It owns and handles display properties like affine transformations,
    background, and so on.
    It handles user events from input devices to modify the document.
    This class can also dispay tools and cursor.
    """

    width = height = 0
    _cur_area = None
    _cur_pos = (0, 0)
    _cur_on = False
    _evtcontext = None
    _swap_x = _swap_y = None
    _debug = 0
    selpath = None

    def __init__(self, win, docproxy):
        super(DocViewport, self).__init__()
        
        self._win = win
        self.docproxy = docproxy
        self.device = InputDevice()

        # Viewport's
        self._docvp = view.DocumentViewPort(docproxy)
        self._toolsvp = view.ToolsViewPort()
        
        self._curvp = tools.Cursor()
        self._curvp.set_radius(docproxy.document.brush.radius_max)

        #self._evmgr = event.EventManager(vp=self)
        #self._evmgr.set_current('Viewport')

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
        
        self.connect("expose-event"        , self.on_expose)
        self.connect("motion-notify-event" , self.on_motion_notify)
        self.connect("button-press-event"  , self.on_button_press)
        self.connect("button-release-event", self.on_button_release)
        self.connect("scroll-event"        , self.on_scroll)
        self.connect("enter-notify-event"  , self.on_enter)
        self.connect("leave-notify-event"  , self.on_leave)
        self.connect("key-press-event"     , self.on_key_pressed)
        self.connect("key-release-event"   , self.on_key_released)

        fn = utils.resolve_path(main.Gribouillis.TRANSPARENT_BACKGROUND)
        self.set_background(fn)

    # PyGTK events
    #

    def on_expose(self, widget, evt):
        width = self.allocation.width
        height = self.allocation.height

        # Update ViewPorts size if size changed
        if self.width != width or self.height != height:
            self.width = width
            self.height = height

            # Process document and tools viewports
            self._docvp.set_view_size(width, height)
            self._toolsvp.set_view_size(width, height)

            self._docvp.repaint()
            self._toolsvp.repaint()

        # Blit model and tools viewports on window RastPort (pixfmt compatible = ARGB)
        cr = self.window.cairo_create()

        cr.rectangle(*evt.area)
        cr.clip()

        cr.set_operator(cairo.OPERATOR_SOURCE)
        
        # Paint background first
        dx, dy = self._docvp.offset
        cr.translate(dx, dy)
        if self._backpat:
            cr.set_source(self._backpat)
        else:
            cr.set_source_rgb(*self._backcolor)
        cr.paint()
        cr.translate(-dx, -dy)

        cr.set_operator(cairo.OPERATOR_OVER)
        cr.set_source_surface(self._docvp.cairo_surface, 0, 0)
        cr.paint()
    
        if self._debug:
            cr.set_source_rgba(1,0,0,random()*.7)
            cr.paint()
            
        cr.set_source_surface(self._toolsvp.cairo_surface, 0, 0)
        cr.paint()

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
    
    def on_button_press(self, widget, evt):
        # ignore double-click events
        if evt.type == gdk.BUTTON_PRESS:
            eat, self._evtcontext = self._evtcontext.process('key-pressed', EventParser(evt))
            return eat

    def on_button_release(self, widget, evt):
        if evt.type == gdk.BUTTON_RELEASE:
            eat, self._evtcontext = self._evtcontext.process('key-released', EventParser(evt))
            return eat
        
    def on_motion_notify(self, widget, evt):
        # We always receive the event event if not in focus
        if not self.has_focus():
            return
        
        #eat, self._evtcontext = self._evtcontext.process('cursor-motion', EventParser(evt))
        #return eat

    def on_scroll(self, widget, evt):
        # There is only one event in GDK for mouse wheel change,
        # so split it as two key events.
        ep = EventParser(evt)
        eat1, self._evtcontext = self._evtcontext.process('key-pressed', ep)
        eat2, self._evtcontext = self._evtcontext.process('key-released', ep)
        return eat1 or eat2

    def on_enter(self, widget, evt):
        #eat, self._evtcontext = self._evtcontext.process('cursor-enter', EventParser(evt))
        #return eat
        pass

    def on_leave(self, widget, evt):
        #eat, self._evtcontext = self._evtcontext.process('cursor-leave', EventParser(evt))
        #return eat
        pass

    def on_key_pressed(self, widget, evt):
        eat, self._evtcontext = self._evtcontext.process('key-pressed', EventParser(evt))
        return eat

    def on_key_released(self, widget, evt):
        eat, self._evtcontext = self._evtcontext.process('key-released', EventParser(evt))
        return eat
        
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

    def lock_focus(self): pass
    def unlock_focus(self): pass
    
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
            self.repaint_cursor(self.devices.current.cpos)
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

    def swap_x(self):
        if self._swap_x is None:
            self._swap_x = self.device.current.vpos[0]
            self._docvp.swap_x(self._swap_x)
        else:
            self._docvp.swap_x(self._swap_x)
            self._swap_x = None
        self._docvp.update_matrix()
        self.repaint()
        
    def swap_y(self):
        if self._swap_y is None:
            self._swap_y = self.device.current.vpos[1]
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
        state.vpos = (evt.get_axis(gdk.AXIS_X)), int(evt.get_axis(gdk.AXIS_Y))
        state.cpos = self.get_pointer()
        state.pressure = self.get_pressure(evt)

        # Get device tilt
        state.xtilt = evt.get_axis(gdk.AXIS_XTILT) or 0.
        state.ytilt = evt.get_axis(gdk.AXIS_YTILT) or 0.

        # timestamp
        state.time = evt.time * 1e-3 # GDK timestamp in milliseconds

        # Filter view pos by tools
        # TODO

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
