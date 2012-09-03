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
from math import ceil, radians

import view
import view.viewport
import main
import model
import utils


from model.devices import *
from model.profile import Transform
from view import cairo_tools as tools
from view.keymap import KeymapManager
from view.operator import eventoperator
from utils import delayedmethod, _T

from .eventparser import GdkEventParser

gdk = gtk.gdk
NORMAL_DIST = 16
ANGLE = radians(22.5)
del radians


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
    _swap_x = _swap_y = None
    _debug = 0
    storage = {}
    selpath = None

    def __init__(self, win, docproxy):
        super(DocViewport, self).__init__()
        
        self._win = win
        self.docproxy = docproxy
        self.device = InputDevice()

        self._km = KeymapManager()
        self._km.use_map("Viewport")

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
    
    
    def _on_motion_notify(self, widget, evt):
        mods = evt.state.value_nicks
        return self._km.process(evt, 'cursor-motion', mods, viewport=self)

    def _on_enter(self, widget, evt):
        self.grab_focus()
        return self._km.process(evt, 'cursor-enter', viewport=self)

    def _on_leave(self, widget, evt):
        return self._km.process(evt, 'cursor-leave', viewport=self)

    def _on_button_press(self, widget, evt):
        if evt.type == gdk.BUTTON_PRESS:
            mods = evt.state.value_nicks
            return self._km.process(evt, 'button-press-%u' % evt.button,
                                    mods, viewport=self)

    def _on_button_release(self, widget, evt):
        if evt.type == gdk.BUTTON_RELEASE:
            mods = evt.state.value_nicks
            return self._km.process(evt, 'button-release-%u' % evt.button,
                                    mods, viewport=self)
    
    def _on_scroll(self, widget, evt):
        mods = evt.state.value_nicks
        return self._km.process(evt, 'scroll-%s' % evt.direction.value_nick,
                                mods, viewport=self)

    def _on_key_press(self, widget, evt):
        mods = evt.state.value_nicks
        return self._km.process(evt, 'key-press-%s' % gdk.keyval_name(evt.keyval),
                                mods, viewport=self)

    def _on_key_release(self, widget, evt):
        mods = evt.state.value_nicks
        if evt.type == gdk.SCROLL:
            name = 'scroll-release-%s' % evt.direction.value_nick,
        else:
            name = 'key-release-%s' % gdk.keyval_name(evt.keyval)
        return self._km.process(evt, name, mods, viewport=self)

    
    # Public API
    
    
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
    
    
    # Cursor related
    
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
    
    
    # View transformations
    
    def reset(self):
        self._swap_x = self._swap_y = None
        self._docvp.reset_view()
        self._curvp.set_scale(self._docvp.scale)
        self.repaint()

    def reset_rotation(self):
        self._docvp.reset_rotation()
        self.repaint()
        
    def scale_up(self, cx=.0, cy=.0):
        x, y = self._docvp.get_model_point(cx, cy)
        if self._docvp.scale_up():
            self._curvp.set_scale(self._docvp.scale)
            self._docvp.update_matrix()
            x, y = self._docvp.get_view_point(x, y)
            self.scroll(int(cx-x), int(cy-y))

    def scale_down(self, cx=.0, cy=.0):
        x, y = self._docvp.get_model_point(cx, cy)
        if self._docvp.scale_down():
            self._curvp.set_scale(self._docvp.scale)
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
    
    def update_dev_state(self, evt):
        state = DeviceState()

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


@eventoperator("vp-enter")
def vp_enter(event, viewport):
    KeymapManager.use_map("Viewport")
    viewport.show_brush_cursor(True)

@eventoperator("vp-leave")
def vp_leave(event, viewport):
    viewport.show_brush_cursor(False)

@eventoperator("vp-move-cursor")
def vp_move_cursor(event, viewport):
    viewport.repaint_cursor(*GdkEventParser.get_cursor_position(event))

@eventoperator("vp-stroke-start")
def vp_stroke_start(event, viewport):
    viewport.update_dev_state(event)
    viewport.show_brush_cursor(False)
    viewport.docproxy.draw_start(viewport.device)
    KeymapManager.save_map()
    KeymapManager.use_map("Stroke")

@eventoperator("vp-stroke-confirm")
def vp_stroke_confirm(event, viewport):
    state = viewport.update_dev_state(event)
    viewport.docproxy.draw_end()
    viewport.repaint_cursor(*state.cpos)
    viewport.show_brush_cursor(True)
    KeymapManager.restore_map()

@eventoperator("vp-stroke-append")
def vp_stroke_append(event, viewport):
    viewport.update_dev_state(event)
    viewport.docproxy.record()

@eventoperator("vp-scroll-start")
def vp_scroll_start(event, viewport):
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

@eventoperator("vp-scroll-confirm")
def vp_scroll_confirm(event, viewport):
    state = viewport.update_dev_state(event)
    viewport.show_brush_cursor(True)
    viewport.storage.clear()
    KeymapManager.restore_map()

@eventoperator("vp-scroll-delta")
def vp_scroll_delta(event, viewport):
    state = viewport.update_dev_state(event)
    x, y = state.cpos
    st = viewport.storage
    viewport.scroll(x - st['x'], y - st['y'])
    st['x'] = x
    st['y'] = y

@eventoperator("vp-scroll-left")
def vp_scroll_left(event, viewport):
    viewport.scroll(-NORMAL_DIST, 0)

@eventoperator("vp-scroll-right")
def vp_scroll_right(event, viewport):
    viewport.scroll(NORMAL_DIST, 0)

@eventoperator("vp-scroll-up")
def vp_scroll_up(event, viewport):
    viewport.scroll(0, -NORMAL_DIST)

@eventoperator("vp-scroll-down")
def vp_scroll_down(event, viewport):
    viewport.scroll(0, NORMAL_DIST)

@eventoperator("vp-scale-up")
def vp_scale_up(event, viewport):
    viewport.scale_up(*GdkEventParser.get_cursor_position(event))

@eventoperator("vp-scale-down")
def vp_scale_down(event, viewport):
    viewport.scale_down(*GdkEventParser.get_cursor_position(event))

@eventoperator("vp-rotate-right")
def vp_rotate_right(event, viewport):
    viewport.rotate(ANGLE)

@eventoperator("vp-rotate-left")
def vp_rotate_left(event, viewport):
    viewport.rotate(-ANGLE)

@eventoperator("vp-swap-x")
def vp_swap_x(event, viewport):
    pos = viewport._cur_pos
    viewport.swap_x(pos[0])

@eventoperator("vp-swap-y")
def vp_swap_y(event, viewport):
    pos = viewport._cur_pos
    viewport.swap_y(pos[1])

@eventoperator("vp-reset-all")
def vp_reset_all(event, viewport):
    viewport.reset()

@eventoperator("vp-reset-rotation")
def vp_reset_rotation(event, viewport):
    viewport.reset_rotation()

@eventoperator("vp-clear-layer")
def vp_clear_layer(event, viewport):
    viewport.docproxy.clear_layer()


RALT_MASK = 'mod5-mask'
LALT_MASK = 'mod1-mask'


KeymapManager.register_keymap("Viewport", {
        # Brush related
        "cursor-enter": "vp-enter",
        "cursor-leave": "vp-leave",
        "cursor-motion": "vp-move-cursor",

        # Drawing
        "button-press-1": "vp-stroke-start",
        "key-press-BackSpace": "vp-clear-layer",

        # View motions
        "button-press-2": "vp-scroll-start",
        "scroll-down": "vp-scale-down",
        "scroll-up": "vp-scale-up",
        "key-press-bracketright": ("vp-rotate-right", None),
        "key-press-bracketleft": ("vp-rotate-left", None),
        "key-press-x": "vp-swap-x",
        "key-press-y": "vp-swap-y",
        "key-press-equal": "vp-reset-all",
        "key-press-plus": ("vp-reset-rotation", None),
        "key-press-Left": "vp-scroll-left",
        "key-press-Right": "vp-scroll-right",
        "key-press-Up": "vp-scroll-up",
        "key-press-Down": "vp-scroll-down",
        })

KeymapManager.register_keymap("Stroke", {
        "cursor-motion": ("vp-stroke-append", ['button1-mask']),
        "button-release-1": ("vp-stroke-confirm", None),
        })

KeymapManager.register_keymap("Scroll", {
        "cursor-motion": ("vp-scroll-delta", ['button2-mask']),
        "button-release-2": ("vp-scroll-confirm", None),
        })
