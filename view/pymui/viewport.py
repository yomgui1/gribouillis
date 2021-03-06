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

import pymui
import time
import math
import cairo
import sys
import traceback as tb

from pymui.mcc.betterbalance import BetterBalance
from math import ceil, floor
from random import random

import model
import main
import utils

import view
import view.viewport
import view.cairo_tools as tools
import view.context as ctx
import _glbackend as gl

from model.devices import *
from utils import resolve_path, _T

from .eventparser import MUIEventParser
from .widgets import Ruler
from .render import DocumentOpenGLRender
from .const import *


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
    _cur_area2 = None
    _cur_pos = (0,0)
    _cur_on = False
    _filter = None
    _swap_x = _swap_y = None
    _focus = False
    _docs_strip = None
    _hruler = _vruler = None
    selpath = None
    docproxy = None
    opengl = 0

    # Tools
    line_guide = None
    ellipse_guide = None

    # Class only
    __focus_lock = None

    class Event: pass

    def __init__(self, root, docproxy=None, rulers=None):
        super(DocViewport, self).__init__(InnerSpacing=0, FillArea=False, DoubleBuffer=False)

        self.device = InputDevice()
        self.root = root
        self._ev = pymui.EventHandler()

        # Viewports and Renders
        if self.opengl:
            self._docre = DocumentOpenGLRender()
        else:
            self._docre = view.DocumentCairoRender()
        self._docvp = view.ViewPort(self._docre)
        self._toolsre = view.ToolsCairoRender()
        self._toolsvp = view.ViewPort(self._toolsre)
        self._curvp = tools.Cursor()

        # Tools
        self.line_guide = tools.LineGuide(300, 200)
        self.ellipse_guide = tools.EllipseGuide(300, 200)

        # Aliases
        self.get_view_area = self._docvp.get_view_area
        self.enable_fast_filter = self._docre.enable_fast_filter
        self.get_handler_at_pos = self._toolsre.get_handler_at_pos

        self.set_background(resolve_path(main.Gribouillis.TRANSPARENT_BACKGROUND))

        if rulers:
            self._hruler, self._vruler = rulers
        else:
            self._do_rulers = utils.idle_cb
            self._update_rulers = utils.idle_cb

        if docproxy is not None:
            self.set_docproxy(docproxy)

    # MUI interface
    #

    @pymui.muimethod(pymui.MUIM_Setup)
    def MCC_Setup(self, msg):
        self._ev.install(self, pymui.IDCMP_RAWKEY | pymui.IDCMP_MOUSEBUTTONS | pymui.IDCMP_MOUSEOBJECTMUI)
        self._docrp = pymui.Raster()
        self._toolsrp = pymui.Raster()
        self._currp = pymui.Raster()
        self._render_cursor()
        return msg.DoSuper()

    @pymui.muimethod(pymui.MUIM_Cleanup)
    def MCC_Cleanup(self, msg):
        self._ev.uninstall()
        gl.term_gl_context()
        del self._docrp, self._toolsrp, self._currp
        return msg.DoSuper()

    @pymui.muimethod(pymui.MUIM_HandleEvent)
    def MCC_HandleEvent(self, msg):
        try:
            ev = self._ev
            ev.readmsg(msg)
            cl = ev.Class
            evt_type = None

            if cl == pymui.IDCMP_MOUSEMOVE:
                if self.focus:
                    evt_type = 'cursor-motion'
            elif cl == pymui.IDCMP_MOUSEOBJECTMUI:
                if ev.InObject:
                    self.focus = True
                    if self.focus:
                        evt_type = 'cursor-enter'
                        ctx.active_viewport = self
                        ctx.keymgr.push('Viewport')
                else:
                    self.focus = False
                    if not self.focus:
                        evt_type = 'cursor-leave'
            elif cl ==  pymui.IDCMP_MOUSEBUTTONS or cl == pymui.IDCMP_RAWKEY:
                if ev.Up:
                    name = "%s-release"
                elif ev.InObject:
                    name = "%s-press"
                else:
                    return
                evt_type = name % MUIEventParser.get_key(ev)

            if evt_type:
                result = ctx.keymgr.process(evt_type, ev, self)
                if evt_type is 'cursor-leave':
                    ctx.keymgr.pop()
                return not result and pymui.MUI_EventHandlerRC_Eat

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
                self._new_render_context(width, height)
                
            if self._cur_area2:
                x, y, w, h = self._cur_area2
                args = x + self.MLeft, y + self.MTop, w, h, x, y
                self._docrp.BltBitMapRastPort(self._rp, 0, *args)
                self._toolsrp.BltBitMapRastPort(self._rp, 1, *args)
                self._cur_area2 = None
                
            x, y, w, h = self._clip
            args = x + self.MLeft, y + self.MTop, w, h, x, y
            self._docrp.BltBitMapRastPort(self._rp, 0, *args)
            self._toolsrp.BltBitMapRastPort(self._rp, 1, *args)
            
            if self._cur_on:
                x, y, w, h = self._cur_area2 = self._cur_area
                self._currp.BltBitMapRastPort(self._rp, 1, x + self.MLeft, y + self.MTop, w, h)
        except:
            tb.print_exc(limit=20)
        finally:
            self.RemoveClipping()

    # Public API
    #

    def duplicate(self):
        vp = self.__class__(self.root, self.docproxy)
        vp.like(self)
        return vp
        
    def set_docproxy(self, docproxy):
        if self.docproxy is docproxy: return
        if self.docproxy:
            self.docproxy.release()
        docproxy.obtain()
        self.docproxy = docproxy
        self._docre.docproxy = docproxy
        fill = docproxy.document.fill or resolve_path(main.Gribouillis.TRANSPARENT_BACKGROUND)
        self.set_background(fill)
        self.width = self.height = None
        self.repaint_doc()

    def like(self, other):
        assert isinstance(other, DocViewport)
        self._docvp.like(other._docvp)
        self.set_docproxy(other.docproxy)

    def _update_rulers(self, ev):
        self._hruler.set_pos(ev.MouseX)
        self._vruler.set_pos(ev.MouseY)

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

    focus = property(fget=lambda self: self._focus, fset=set_focus)

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

    #### Rendering ####

    def _new_render_context(self, width, height):
        self._docrp.AllocBitMap(width, height, 32, self, self.opengl)
        self._toolsrp.AllocBitMap(width, height, 32, self)
        
        self._docvp.set_view_size(width, height)
        self._toolsvp.set_view_size(width, height)
        
        gl.init_gl_context(long(self._docrp), width, height)
        
        # Full rendering
        self._docvp.repaint()
        self._toolsvp.repaint()
        
        self._clip = (0, 0, width, height)
        self._blit_doc(*self._clip)
        self._blit_tools(*self._clip)
        self._blit_cursor()

    def _check_clip(self, x, y, w, h):
        # Check for RastPort boundaries
        if x < 0:
            w += x
            x = 0
        if w > self.width:
            w = self.width
        if y < 0:
            h += y
            y = 0
        if h > self.height:
            h = self.height
        return x, y, w, h

    def _blit_doc(self, x, y, w, h):
        buf = self._docre.pixbuf
        if self.opengl:
            gl.blit_pixbuf(buf, x, y, w, h)
        else:
            self._docrp.Blit8(buf, buf.stride, x, y, w, h, x, y)
        
    def _blit_tools(self, x, y, w, h):
        buf = self._toolsre.pixbuf
        self._toolsrp.Blit8(buf, buf.stride, x, y, w, h, x, y)
        
    def _blit_cursor(self):
        buf = self._curvp.pixbuf
        self._currp.Blit8(buf, buf.stride,
            0, 0, self._curvp.width, self._curvp.height)
    
    def _render_cursor(self):
        self._currp.AllocBitMap(self._curvp.width, self._curvp.height, 32, self)
        self._curvp.repaint()
        self._blit_cursor()
        
    def repaint_doc(self, clip=None, redraw=True):
        if not self.width:
            return
        if not clip:
            clip = (0, 0, self.width, self.height)
        self._docvp.repaint(clip)
        if redraw:
            self._blit_doc(*clip)
            self._clip = clip
            self.Redraw()

    def repaint_tools(self, clip=None, redraw=False):
        if not self.width:
            return
        if not clip:
            clip = (0, 0, self.width, self.height)
        self._toolsvp.repaint(clip)
        if redraw:
            self._blit_tools(*clip)
            self._clip = clip
            self.Redraw()

    def repaint_cursor(self, *pos):
        if self._focus:
            self._cur_pos = pos
            self._cur_area = self._get_cursor_clip(*pos)
            self._clip = self._cur_area
            self.Redraw()

    def clear_tools_area(self, clip, redraw=False):
        self._toolsvp.clear_area(clip)
        if redraw:
            self._blit_tools(*clip)
            self._clip = clip
            self.Redraw()

    def enable_passepartout(self, state=True):
        pass

    #### Cursor related ####

    def _get_cursor_clip(self, dx, dy):
        w = self._curvp.width
        h = self._curvp.height
        dx -= w/2
        dy -= h/2
        return dx, dy, w, h

    def set_cursor_radius(self, r):
        self._curvp.set_radius(r)
        self._render_cursor()
        self.repaint_cursor(*self._cur_pos)

    def show_brush_cursor(self, state=True):
        if state:
            self._cur_on = True
            if self.device.current:
                self.repaint_cursor(*self.device.current.cpos)
        elif self._cur_on:
            self._cur_on = False
            if self.device.current:
                self.repaint_cursor(*self.device.current.cpos)
        return self._cur_pos

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

    #### Document viewport methods ####

    def get_model_distance(self, *a):
        return self._docvp.get_model_distance(*a)

    def get_model_point(self, *a):
        return self._docvp.get_model_point(*a)

    def get_view_pos(self, mx, my):
        "Convert Mouse coordinates from intuition event into viewport coordinates"
        return mx-self.MLeft, my-self.MTop

    def reset_transforms(self):
        self._swap_x = self._swap_y = None
        self._docvp.reset_view()
        self._docvp.update_matrix()
        self._curvp.set_scale(self._docvp.scale)
        self._render_cursor()
        self.repaint_doc()
        self._do_rulers()

    def reset_translation(self):
        dvp = self._docvp
        if dvp.reset_translation():
            dvp.update_matrix()
            self.repaint_doc()
            self._do_rulers()

    def reset_scaling(self, cx=0, cy=0):
        dvp = self._docvp
        x, y = dvp.get_model_point(cx, cy)

        # Reset scaling
        if dvp.reset_scale():
            dvp.update_matrix()

            # Sync cursor size
            self._curvp.set_scale(dvp.scale)
            self._render_cursor()

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
            self._render_cursor()
            self._docvp.update_matrix()
            x, y = self._docvp.get_view_point(x, y)
            self._docvp.scroll(cx-x, cy-y)
            self._docvp.update_matrix()
            self.repaint_doc()
            self._do_rulers()

    def scale_down(self, cx=.0, cy=.0):
        x, y = self._docvp.get_model_point(cx, cy)
        if self._docvp.scale_down():
            self._curvp.set_scale(self._docvp.scale)
            self._render_cursor()
            self._docvp.update_matrix()
            x, y = self._docvp.get_view_point(x, y)
            self._docvp.scroll(cx-x, cy-y)
            self._docvp.update_matrix()
            self.repaint_doc()
            self._do_rulers()

    def scroll(self, *delta):
        clip = self.get_view_area(*self.docproxy.document.area)
        
        # Scroll the document viewport
        self._docvp.scroll(*delta)
        self._docvp.update_matrix()
        
        # this is the maximal modified area possible
        clip = utils.join_area(clip, self.get_view_area(*self.docproxy.document.area))

        # Scroll the internal docvp buffer
        self._docre.pixbuf.scroll(*delta)

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

        dx, dy = delta
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
        for area in drects:
            self._docre.repaint(area)

        # Rasterize to the minimal viewable area
        self._clip = clip = self._check_clip(*clip)
        self._blit_doc(*clip)
        self.Redraw()
        
        self._do_rulers()

    def rotate(self, angle):
        if self._hruler:
            return

        self._docvp.rotate(angle)
        self._docvp.update_matrix()

        buf = self._docre.pixbuf
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
        self._clip = 0, 0, w, h
        self._blit_doc(*self._clip)
        self.Redraw()

    def swap_x(self, x):
        if self._swap_x is None:
            self._swap_x = x
            self._docvp.swap_x(self._swap_x)
        else:
            self._docvp.swap_x(self._swap_x)
            self._swap_x = None

        self._docvp.update_matrix()
        self.repaint_doc()
        self._do_rulers()

    def swap_y(self, y):
        if self._swap_y is None:
            self._swap_y = y
            self._docvp.swap_y(self._swap_y)
        else:
            self._docvp.swap_y(self._swap_y)
            self._swap_y = None

        self._docvp.update_matrix()
        self.repaint_doc()
        self._do_rulers()

    def get_exact_color(self, *pos):
        try:
            return self._docre.pixbuf.get_pixel(*pos)[:-1] # alpha last
        except:
            return

    def get_average_color(self, *pos):
        try:
            return self._docre.pixbuf.get_average_pixel(self._curvp.radius, *pos)[:-1] # alpha last
        except:
            return

    @property
    def scale(self):
        return self._docvp.scale

    def get_offset(self):
        return self._docvp.offset

    def set_offset(self, offset):
        self._docvp.offset = offset
        self._docvp.update_matrix()

    offset = property(get_offset, set_offset)
    
    #### Tools/Handlers ####

    def add_tool(self, tool):
        if tool.added:
            return

        if hasattr(tool, 'filter'):
            self._filter = tool.filter
        self._toolsvp.add_tool(tool)
        tool.added = True
        self.repaint_tools(*tool.area)

    def rem_tool(self, tool):
        if not tool.added:
            return

        if hasattr(tool, 'filter') and self._filter == tool.filter:
            self._filter = None
        area = tool.area # saving because may be destroyed during rem_tool
        self._toolsvp.rem_tool(tool)
        tool.added = False
        self.repaint_tools(*tool.area)

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

    def is_tool_hit(self, tool, *pos):
        return self._toolsvp.is_tool_hit(tool, *pos)

    @property
    def tools(self):
        return self._toolsvp.tools

