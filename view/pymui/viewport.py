# -*- coding: latin-1 -*-

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

import pymui
import time
import math
import cairo
import sys
import traceback as tb

from pymui.mcc.betterbalance import BetterBalance
from math import ceil
from random import random

import model
import main
import utils

import view
import view.viewport
import view.cairo_tools as tools

from view.keymap import KeymapManager
from model.devices import *
from utils import resolve_path, _T

from .eventparser import MUIEventParser
from .app import Application
from .widgets import Ruler
from .const import *


__all__ = [ 'DocViewport' ]

class DocViewport(pymui.Rectangle, view.viewport.BackgroundMixin):
    """DocViewport class.

    This class is responsible to display a given document.
    It owns and handles display properties like affine transformations,
    background, and so on.
    It handles user events from input devices to modify the document.
    This class can also dispay tools and cursor.
    """

    _MCC_ = True
    width = height = None
    _clip = None
    _cur_area = None
    _cur_pos = (0,0)
    _cur_on = False
    _filter = None
    _swap_x = _swap_y = None
    _focus = False
    _docs_strip = None
    _debug = 0
    selpath = None
    ctx = None

    # Tools
    line_guide = None
    ellipse_guide = None

    # Class only
    __focus_lock = None

    def __init__(self, docproxy=None, rulers=None):
        super(DocViewport, self).__init__(InnerSpacing=0, FillArea=False, DoubleBuffer=False)

        self.device = InputDevice()

        self._km = KeymapManager()
        self._km.use_map("Viewport")
        self._ev = pymui.EventHandler()

        # Viewports
        self._docvp = view.DocumentViewPort()
        self._toolsvp = view.ToolsViewPort()
        self._curvp = tools.Cursor()

        # Tools
        self.line_guide = tools.LineGuide(300, 200)
        self.ellipse_guide = tools.EllipseGuide(300, 200)

        # Aliases
        self.get_view_area = self._docvp.get_view_area
        self.enable_fast_filter = self._docvp.enable_fast_filter
        self.get_handler_at_pos = self._toolsvp.get_handler_at_pos

        self.set_background(resolve_path(main.Gribouillis.TRANSPARENT_BACKGROUND))

        if rulers:
            self._hruler, self._vruler = rulers
        else:
            self._do_rulers = lambda self: None
            self._update_rulers = lambda self, ev: None

        if docproxy is not None:
            self.set_docproxy(docproxy)

    def set_docproxy(self, docproxy):
        self.docproxy = docproxy
        self._docvp.docproxy = docproxy
        fill = docproxy.document.fill or resolve_path(main.Gribouillis.TRANSPARENT_BACKGROUND)
        self.set_background(fill)
        self.width = self.height = None

    def _update_rulers(self, ev):
        self._hruler.set_pos(ev.MouseX)
        self._vruler.set_pos(ev.MouseY)

    # MUI interface
    #

    @pymui.muimethod(pymui.MUIM_Setup)
    def MCC_Setup(self, msg):
        self._win = self.WindowObject.object
        self._ev.install(self, pymui.IDCMP_RAWKEY | pymui.IDCMP_MOUSEBUTTONS | pymui.IDCMP_MOUSEOBJECTMUI)
        return msg.DoSuper()

    @pymui.muimethod(pymui.MUIM_Cleanup)
    def MCC_Cleanup(self, msg):
        self._ev.uninstall()
        return msg.DoSuper()

    @pymui.muimethod(pymui.MUIM_HandleEvent)
    def MCC_HandleEvent(self, msg):
        try:
            ev = self._ev
            ev.readmsg(msg)
            cl = ev.Class

            if cl == pymui.IDCMP_MOUSEMOVE:
                if self.focus:
                    self._update_rulers(ev)
                    name = "cursor-motion"
                else:
                    return

            elif cl == pymui.IDCMP_MOUSEOBJECTMUI:
                if ev.InObject:
                    self.focus = True
                    if self.focus:
                        name = "cursor-enter"
                    else:
                        return
                else:
                    self.focus = False
                    if not self.focus:
                        name = "cursor-leave"
                    else:
                        return

            elif cl == pymui.IDCMP_MOUSEBUTTONS or cl == pymui.IDCMP_RAWKEY:
                if ev.Up:
                    name = "%s-release"
                elif ev.InObject:
                    name = "%s-press"
                else:
                    return

                name = name % MUIEventParser.get_key(ev)

            else:
                return

            mods = MUIEventParser.get_modificators(ev)
            eat = self._km.process(ev, name, mods, viewport=self)
            return eat and pymui.MUI_EventHandlerRC_Eat

        except:
            tb.print_exc(limit=20)

    @pymui.muimethod(pymui.MUIM_AskMinMax)
    def _mcc_AskMinMax(self, msg):
        msg.DoSuper()
        mmi = msg.MinMaxInfo.contents
        mmi.MaxWidth = mmi.MaxWidth.value + pymui.MUI_MAXMAX
        mmi.MaxHeight = mmi.MaxHeight.value + pymui.MUI_MAXMAX

    @pymui.muimethod(pymui.MUIM_Draw)
    def _mcc_Draw(self, msg):
        msg.DoSuper()
        if not (msg.flags.value & pymui.MADF_DRAWOBJECT): return

        self.AddClipping()
        try:
            width = self.MWidth
            height = self.MHeight

            # Update and redraw everything when size has changed
            if self.width != width or self.height != height:
                self.width = width
                self.height = height

                # Rendering context
                self._new_render_context(width, height)

                # Now viewport has a size we can initialize gfx elements
                self._docvp.set_view_size(width, height)
                self._toolsvp.set_view_size(width, height)

                # Repaint all viewports
                self._docvp.repaint()
                self._toolsvp.repaint()

                if self._clip:
                    x, y, w, h = self._clip
                    self._clip = None
                else:
                    x = y = 0
                    w = width
                    h = height

                # Redraw the internal pixels buffer
                self._redraw(x, y, w, h)

                # Set HRuler range
                self._do_rulers()

            elif self._clip:
                x, y, w, h = self._clip
                self._clip = None
            else:
                x = y = 0
                w = width
                h = height

            # Blit the internal buffer using computed/requested clip area
            self._rp.Blit8(self._drawbuf, self._drawbuf.stride, self.MLeft + x, self.MTop + y, w, h, x, y)

            if self._debug:
                self._rp.Rect(int(random()*255), self.MLeft + x, self.MTop + y, self.MLeft + x + w - 1, self.MTop + y + h - 1, 0)

        except:
            tb.print_exc(limit=20)

        finally:
            self.RemoveClipping()

    # Private API
    #

    def _new_render_context(self, width, height):
        # As we are doing the double buffering ourself we create
        # a pixel buffer suitable to be blitted on the window RastPort (ARGB no-alpha premul)
        self._drawbuf = model._pixbuf.Pixbuf(model._pixbuf.FORMAT_ARGB8_NOA, width, height)
        self._drawsurf = cairo.ImageSurface.create_for_data(self._drawbuf, cairo.FORMAT_ARGB32, width, height)
        self._drawcr = cairo.Context(self._drawsurf)
        return self._drawbuf

    # Public API
    #

    def get_model_distance(self, *a):
        return self._docvp.get_model_distance(*a)

    def get_model_point(self, *a):
        return self._docvp.get_model_point(*a)

    def enable_motion_events(self, state=True):
        self._ev.uninstall()
        if state:
            idcmp = self._ev.idcmp | pymui.IDCMP_MOUSEMOVE
        else:
            idcmp = self._ev.idcmp & ~pymui.IDCMP_MOUSEMOVE
        self._ev.install(self, idcmp)

    def lock_focus(self):
        cl = self.__class__
        if self._focus and cl.__focus_lock is None:
            cl.__focus_lock = self

    def unlock_focus(self):
        cl = self.__class__
        if cl.__focus_lock is self:
            cl.__focus_lock = None

    def set_focus(self, focus):
        """Set focus on viewport

        Viewport with focus is able to process events during MCC_HandleEvent call.
        But this fonction works only if another viewport doens't have lock it
        by a call to lock_focus.
        When a Viewport has the focus, Viewport mediator active attribute is set.
        """

        cl = self.__class__
        if focus:
            if cl.__focus_lock is not None:
                return
            self._focus = True
            self.mediator.active = self
        elif self._focus and cl.__focus_lock is None:
            self._focus = False

    def is_tool_hit(self, tool, *pos):
        return self._toolsvp.is_tool_hit(tool, *pos)

    def pick_mode(self, state):
        if state:
            self._win.pointer = DocWindow.POINTERTYPE_PICK
        else:
            self._win.pointer = DocWindow.POINTERTYPE_NORMAL

    def set_docs_strip(self, proxies):
        strip = pymui.Menustrip()
        menu = pymui.Menu(_T('Documents'))
        strip.AddTail(menu)

        for p in proxies:
            item = pymui.Menuitem(p.docname)
            menu.AddChild(item)

        self.ContextMenu = strip
        if self._docs_strip:
            self._docs_strip.Dispose()
        self._docs_strip = strip

    @property
    def scale(self):
        return self._docvp.scale

    def get_offset(self):
        return self._docvp.offset

    def set_offset(self, offset):
        self._docvp.offset = offset
        self._docvp.update_matrix()

    offset = property(get_offset, set_offset)
    focus = property(fget=lambda self: self._focus, fset=set_focus)

    #### Rendering ####

    def _check_clip(self, x, y, w, h):
        # Check for RastPort boundaries
        if x < 0: x = 0; w += x
        if y < 0: y = 0; h += y
        return x, y, w, h

    def _redraw(self, x, y, w, h):
        # For each viewport convert to the correct pixels format and blit result on rastport
        args = (self._drawbuf, x, y, x, y, w, h)
        self._docvp.pixbuf.compose(*args)
        self._toolsvp.pixbuf.compose(*args)

        # Blit a cursor?
        if self._cur_on:
            self._curvp.pixbuf.compose(self._drawbuf, self._cur_area[0], self._cur_area[1], 0, 0, self._cur_area[2], self._cur_area[3])

    def redraw(self, clip=None):
        # Compute the redraw area (user/full clip + cursor clip to remove)
        if clip and self._cur_area:
            clip = utils.join_area(clip, self._cur_area)
            self._cur_area = None

        # new cursor clip
        if self._cur_on:
            self._curvp.render()
            self._cur_area = self._get_cursor_clip(*self._cur_pos)
            if clip:
                clip = utils.join_area(clip, self._cur_area)

        if clip:
            self._clip = self._check_clip(*clip)
        else:
            self._clip = (0, 0, self.width, self.height)


        self._redraw(*self._clip)
        self.Redraw()

    def repaint(self, clip=None, redraw=True):
        self._docvp.repaint(clip)
        if redraw:
            self.redraw(clip)

    def repaint_tools(self, clip=None, redraw=False):
        self._toolsvp.repaint(clip)
        if redraw:
            self.redraw(clip)

    def repaint_cursor(self, *pos):
        if self._focus:
            # Draw the new one
            self._cur_on = True
            self._cur_pos = pos
            self.redraw(self._get_cursor_clip(*pos))

    def clear_tools_area(self, clip, redraw=False):
        self._toolsvp.clear_area(clip)
        if redraw:
            self.redraw(clip)

    def enable_passepartout(self, state=True):
        self._docvp.passepartout = state
        self.repaint()

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

    def show_brush_cursor(self, state=True):
        if state and self.device.current:
            self.repaint_cursor(*self.device.current.cpos)
        else:
            self._cur_on = False
            # Remove the cursor if was blit and not needed
            if self._cur_area:
                self.redraw(self._cur_area)
        return self._cur_pos

    #### Document viewport methods ####

    def _do_rulers(self):
        x0, y0 = self.get_model_point(0, 0)
        x1, y1 = self.get_model_point(self.width, self.height)

        # Set HRuler range
        self._hruler.lo = x0
        self._hruler.hi = x1
        self._hruler.Redraw()

        # Set VRuler range
        self._vruler.lo = y0
        self._vruler.hi = y1
        self._vruler.Redraw()

    def get_view_pos(self, mx, my):
        "Convert Mouse coordinates from intuition event into viewport coordinates"
        return mx-self.MLeft, my-self.MTop

    def reset_transforms(self):
        self._swap_x = self._swap_y = None
        self._docvp.reset_view()
        self._curvp.set_scale(self._docvp.scale)
        self.repaint()
        self._do_rulers()

    def reset_translation(self):
        dvp = self._docvp
        if dvp.reset_translation():
            dvp.update_matrix()
            self.repaint()
            self._do_rulers()

    def reset_scaling(self, cx=0, cy=0):
        dvp = self._docvp
        x, y = dvp.get_model_point(cx, cy)

        # Reset scaling
        if dvp.reset_scale():
            dvp.update_matrix()

            # Sync cursor size
            self._curvp.set_scale(dvp.scale)

            # Center vp on current cursor position
            x, y = dvp.get_view_point(x, y)
            self.scroll(int(cx-x), int(cy-y))

            self.repaint_cursor(cx, cy)

    def reset_rotation(self, cx=0, cy=0):
        dvp = self._docvp
        x, y = dvp.get_model_point(cx, cy)

        if dvp.reset_rotation():
            dvp.update_matrix()

            # Center vp on current cursor position
            x, y = dvp.get_view_point(x, y)
            self.scroll(int(cx-x), int(cy-y))

    def scale_up(self, cx=.0, cy=.0):
        x, y = self._docvp.get_model_point(cx, cy)
        if self._docvp.scale_up():
            self._curvp.set_scale(self._docvp.scale)
            self._docvp.update_matrix()
            x, y = self._docvp.get_view_point(x, y)
            self._docvp.scroll(cx-x, cy-y)
            self._docvp.update_matrix()
            self.repaint()
            self._do_rulers()

    def scale_down(self, cx=.0, cy=.0):
        x, y = self._docvp.get_model_point(cx, cy)
        if self._docvp.scale_down():
            self._curvp.set_scale(self._docvp.scale)
            self._docvp.update_matrix()
            x, y = self._docvp.get_view_point(x, y)
            self._docvp.scroll(cx-x, cy-y)
            self._docvp.update_matrix()
            self.repaint()
            self._do_rulers()

    def scroll(self, *delta):
        # Scroll the document viewport
        self._docvp.scroll(*delta)
        self._docvp.update_matrix()

        dx, dy = delta

        # Scroll the internal docvp buffer
        self._docvp.pixbuf.scroll(dx, dy)

        ## Compute the damaged rectangles list...
        # 4 damaged rectangles possible, but only two per delta:
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

        drects = []

        if dy > 0:
            drects.append([0, 0, w, dy]) #3
        elif dy < 0:
            drects.append([0, h+dy, w, h]) #4

        if dx > 0:
            if dy >= 0:
                drects.append([0, dy, dx, h]) #1
            else:
                drects.append([0, 0, dx, h+dy]) #1
        elif dx < 0:
            if dy >= 0:
                drects.append([w+dx, dy, w, h]) #2
            else:
                drects.append([w+dx, 0, w, h+dy]) #2

        # Re-render only damaged parts
        for clip in drects:
            self._docvp.repaint(clip)

        # Rasterize full area
        clip = (0, 0, self.width, self.height)
        self._redraw(*clip)
        self._clip = clip
        self.Redraw()

        self._do_rulers()

    def rotate(self, angle):
        if self._win.rulers:
            return

        self._docvp.rotate(angle)
        self._docvp.update_matrix()

        buf = self._docvp.pixbuf
        w = buf.width
        h = buf.height
        cx = w/2.
        cy = h/2.

        srcbuf = model._pixbuf.Pixbuf(buf.pixfmt, w, h, buf)
        buf.clear_value(0.2)
        del buf

        cr = self._docvp._ctx
        cr.save()
        cr.translate(cx, cy)
        cr.rotate(angle)
        cr.translate(-cx, -cy)
        cr.set_source_surface(cairo.ImageSurface.create_for_data(srcbuf, cairo.FORMAT_ARGB32, w, h), 0, 0)
        cr.get_source().set_filter(cairo.FILTER_FAST)
        cr.paint()
        cr.restore()

        del cr, srcbuf

        # Rasterize full area
        clip = (0, 0, self.width, self.height)
        self._redraw(*clip)
        self._clip = clip
        self.Redraw()

    def swap_x(self, x):
        if self._swap_x is None:
            self._swap_x = x
            self._docvp.swap_x(self._swap_x)
        else:
            self._docvp.swap_x(self._swap_x)
            self._swap_x = None

        self._docvp.update_matrix()
        self.repaint()
        self._do_rulers()

    def swap_y(self, y):
        if self._swap_y is None:
            self._swap_y = y
            self._docvp.swap_y(self._swap_y)
        else:
            self._docvp.swap_y(self._swap_y)
            self._swap_y = None

        self._docvp.update_matrix()
        self.repaint()
        self._do_rulers()

    def get_exact_color(self, *pos):
        try:
            return self._docvp.pixbuf.get_pixel(*pos)[:-1] # alpha last
        except:
            return

    def get_average_color(self, *pos):
        try:
            return self._docvp.pixbuf.get_average_pixel(self._curvp.radius, *pos)[:-1] # alpha last
        except:
            return

    #### Device state handling ####

    def get_device_state(self, event):
        state = DeviceState()

        state.time = MUIEventParser.get_time(event)

        # Get raw device position
        state.cpos = self.get_view_pos(*MUIEventParser.get_screen_position(event))
        state.vpos = state.cpos

        # Tablet stuffs
        state.pressure = MUIEventParser.get_pressure(event)
        state.xtilt = MUIEventParser.get_cursor_xtilt(event)
        state.ytilt = MUIEventParser.get_cursor_ytilt(event)

        # Filter view pos by tools
        if self._filter:
            self._filter(state)

        # Translate to surface coordinates (using layer offset) and record
        pos = self._docvp.get_model_point(*state.vpos)
        state.spos = self.docproxy.get_layer_pos(*pos)
        self.device.add_state(state)
        return state

    #### Tools/Handlers ####

    def add_tool(self, tool):
        if tool.added:
            return

        if hasattr(tool, 'filter'):
            self._filter = tool.filter
        self._toolsvp.add_tool(tool)
        tool.added = True
        self.redraw(tool.area)

    def rem_tool(self, tool):
        if not tool.added:
            return

        if hasattr(tool, 'filter') and self._filter == tool.filter:
            self._filter = None
        area = tool.area # saving because may be destroyed during rem_tool
        self._toolsvp.rem_tool(tool)
        tool.added = False
        self.redraw(area)

    def toggle_tool(self, tool):
        if tool.added:
            self.rem_tool(tool)
        else:
            self.add_tool(tool)
        return tool.added

    def toggle_guide(self, name):
        if name == 'line':
            if self.toggle_tool(self.line_guide) and self.ellipse_guide.added:
                self.rem_tool(self.ellipse_guide)
        elif name == 'ellipse':
            if self.toggle_tool(self.ellipse_guide) and self.line_guide.added:
                self.rem_tool(self.line_guide)

    @property
    def tools(self):
        return self._toolsvp.tools

