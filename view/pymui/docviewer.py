# -*- coding: latin-1 -*-

###############################################################################
# Copyright (c) 2009-2011 Guillaume Roguez
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

import pymui, time, math, cairo, sys
import traceback as tb

from pymui.mcc.betterbalance import BetterBalance
from math import ceil
from random import random

import model, view, main, utils

from model.devices import *
from view import viewport, contexts
from view import cairo_tools as tools

from .app import Application
from .widgets import Ruler
from eventparser import *
from const import *


__all__ = [ 'DocWindow' ]

class DocDisplayArea(pymui.Rectangle, viewport.BackgroundMixin):
    """DocDisplayArea class.

    This class is responsible to display a given document.
    It owns and handles display properties like affine transformations,
    background, and so on.
    It handles user events from input devices to modify the document.
    This class can also dispay tools and cursor.
    """
    
    _MCC_ = True
    width = height = 0
    _clip = None
    _cur_area = None
    _cur_pos = (0,0)
    _cur_on = False
    _filter = None
    _swap_x = _swap_y = None
    _focus = False
    _debug = 0
    selpath = None
    ctx = None
    
    # Tools
    line_guide = None
    ellipse_guide = None
    
    # Class only
    __focus_lock = None

    def __init__(self, win, docproxy):
        super(DocDisplayArea, self).__init__(InnerSpacing=0, FillArea=False, DoubleBuffer=False)

        fill = docproxy.document.fill or resolve_path(main.Gribouillis.TRANSPARENT_BACKGROUND)
        self.set_background(fill)

        self._win = win
        self.docproxy = docproxy
        self.device = InputDevice()
        
        # Viewport's
        self._docvp = view.DocumentViewPort(docproxy)
        self._toolsvp = view.ToolsViewPort()

        self._curvp = tools.Cursor()
        self._curvp.set_radius(docproxy.document.brush.radius_max)

        self.line_guide = tools.LineGuide(300, 200)
        self.ellipse_guide = tools.EllipseGuide(300, 200)

        # Aliases
        self.get_view_area = self._docvp.get_view_area
        self.enable_fast_filter = self._docvp.enable_fast_filter
        self.get_handler_at_pos = self._toolsvp.get_handler_at_pos
        
        self._ev = pymui.EventHandler()

    # MUI interface
    #
    
    @pymui.muimethod(pymui.MUIM_Setup)
    def MCC_Setup(self, msg):
        self._ev.install(self, pymui.IDCMP_RAWKEY | pymui.IDCMP_MOUSEBUTTONS | pymui.IDCMP_MOUSEOBJECTMUI)
        self.mediator.active = self
        return msg.DoSuper()

    @pymui.muimethod(pymui.MUIM_Cleanup)
    def MCC_Cleanup(self, msg):
        self._ev.uninstall()
        return msg.DoSuper()

    @pymui.muimethod(pymui.MUIM_HandleEvent)
    def MCC_HandleEvent(self, msg):
        try:
            self._ev.readmsg(msg)
            cl = self._ev.Class
            if cl == pymui.IDCMP_MOUSEMOVE:
                if self.focus:
                    self._hruler.set_pos(self._ev.MouseX)
                    self._vruler.set_pos(self._ev.MouseY)
                    event = CursorMoveEvent(self._ev, self)
                else:
                    return
            elif cl == pymui.IDCMP_MOUSEOBJECTMUI:
                if self._ev.InObject:
                    self.focus = True
                    if self.focus:
                        event = GetFocusEvent(self._ev, self)
                    else:
                        return
                else:
                    self.focus = False
                    if not self.focus:
                        event = LooseFocusEvent(self._ev, self)
                    else:
                        return
            elif cl == pymui.IDCMP_MOUSEBUTTONS or cl == pymui.IDCMP_RAWKEY:
                if self._ev.Up:
                    event = KeyReleasedEvent(self._ev, self)
                elif self._ev.InObject:
                    event = KeyPressedEvent(self._ev, self)
                else:
                    return
            else:
                return

            eat, self.ctx = self.ctx.process(event)
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
                
                # Now viewport has a size we can initialize gfx elements
                self._docvp.set_view_size(width, height)
                self._toolsvp.set_view_size(width, height)
                
                # Repaint all viewports
                self._docvp.repaint()
                self._toolsvp.repaint()

                # As we are doing the double buffering ourself we create
                # a pixel buffer suitable to be blitted on the window RastPort (ARGB no-alpha premul)
                self._drawbuf = model._pixbuf.Pixbuf(model._pixbuf.FORMAT_ARGB8_NOA, width, height)
                self._drawsurf = cairo.ImageSurface.create_for_data(self._drawbuf, cairo.FORMAT_ARGB32, width, height)
                self._drawcr = cairo.Context(self._drawsurf)
                
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
                
                if not self.ctx:
                    self.ctx = self._win.ctx.enter_context('Viewport', viewport=self)

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
       
    # Public API
    #

    def split(self, *args):
        return self._win.add_viewport(self, *args)
        
    def remove(self):
        self._win.rem_viewport(self)
        
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
            
    @property
    def scale(self):
        return self._docvp.scale
        
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
        
        # Unlock rulers display
        self._win.permit_rulers = True

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
            self.scroll(cx-x, cy-y)
    
    def reset_rotation(self, cx=0, cy=0):
        dvp = self._docvp
        x, y = dvp.get_model_point(cx, cy)
        
        if dvp.reset_rotation():
            dvp.update_matrix()
            
            # Center vp on current cursor position
            x, y = dvp.get_view_point(x, y)
            self.scroll(cx-x, cy-y)
            
        # Unlock rulers display
        self._win.permit_rulers = True
    
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
        self._do_rulers()

    def rotate(self, angle):
        self._win.permit_rulers = False
        if self._win.rulers:
            self._win.toggle_rulers()
            
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
        
        state.time = event.get_time()

        # Get raw device position
        state.cpos = event.get_cursor_position()
        state.vpos = state.cpos
        
        # Tablet stuffs
        state.pressure = event.get_pressure()
        state.xtilt = event.get_cursor_xtilt()
        state.ytilt = event.get_cursor_ytilt()

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
    
    def to_front(self):
        self.WindowObject.contents.Activate = True

class DocWindow(pymui.Window):

    # Pointers type from C header file 'intuition/pointerclass.h'
    POINTERTYPE_NORMAL = 0
    POINTERTYPE_DRAW   = 6
    POINTERTYPE_PICK   = 5

    focus = 0 # used by viewport objects
    permit_rulers = True
    _name = None
    _scale = 1.0
    
    # Private API
    #

    def __init__(self, ctx, docproxy):
        self.title_header = 'Document: %s @ %u%%'
        super(DocWindow, self).__init__('',
                                        ID=0,       # The haitian power
                                        LeftEdge='centered',
                                        TopEdge='centered',
                                        WidthVisible=50,
                                        HeightVisible=50,
                                        #WidthScreen=70,
                                        #HeightScreen=90,
                                        #Backdrop=True,
                                        #Borderless=True,
                                        TabletMessages=True, # enable tablet events support
                                        )

        self.disp_areas = []
        self._watchers = {'pick': None}
        self.ctx = ctx.enter_context('Document', docproxy=docproxy, window=self)

        self.docproxy = docproxy
        name = docproxy.docname

        root = pymui.ColGroup(2, InnerSpacing=0, Spacing=0)
        self.RootObject = root
        
        # Rulers space
        obj = pymui.List(SourceArray=[ Ruler.METRICS[k][0] for k in Ruler.METRIC_KEYS ],
                         AdjustWidth=True,
                         MultiSelect=pymui.MUIV_List_MultiSelect_None)
        pop = pymui.Popobject(Object=obj,
                              Button=pymui.Image(Frame='ImageButton',
                                                 Spec=pymui.MUII_PopUp,
                                                 InputMode='RelVerify'))
        obj.Notify('DoubleClick', self._on_ruler_metric, pop, obj)
        root.AddChild(pop)
        self._popruler = pop
        
        # Top ruler
        self._hruler = Ruler(Horiz=True)
        root.AddChild(self._hruler)
        
        # Left ruler
        self._vruler = Ruler(Horiz=False)
        root.AddChild(self._vruler)
        
        self._vpgrp = pymui.HGroup(InnerSpacing=0, Spacing=0)
        root.AddChild(self._vpgrp)
        
        # Default editor area
        da, _ = self.add_viewport()
        
        # Status bar - TODO
        #root.AddChild(pymui.HVSpace())
        #self._status = pymui.Text(Frame='Text', Background='Text')
        #root.AddChild(self._status)

        self.Notify('Activate', self._on_activate)
        self.set_doc_name(name)
        
        # defaults
        self._popruler.ShowMe = False
            
    def _on_activate(self, evt):
        if evt.value:
            self.pointer = self.POINTERTYPE_DRAW
            #self.Opacity = -1
        else:
            self.pointer = self.POINTERTYPE_NORMAL
            #self.Opacity = 128
        
    def _on_ruler_metric(self, evt, pop, lister):
        pop.Close(0)
        k = Ruler.METRIC_KEYS[lister.Active.value]
        self._hruler.set_metric(k)
        self._vruler.set_metric(k)
        
    def add_viewport(self, master=None, horiz=False):
        da = DocDisplayArea(self, self.docproxy)
        da._hruler = self._hruler
        da._vruler = self._vruler
        self.disp_areas.append(da)

        if not master:
            if len(self.disp_areas) > 1:
                self._vpgrp.AddChild(BetterBalance())
                da.location = 1
            else:
                da.location = 0
            self._vpgrp.AddChild(da)
            da.group = self._vpgrp
            da.other = da2 = None
            self._vpgrp.da = [da, da2]
        else:
            parent = master.group
            if horiz:
                grp = pymui.VGroup(InnerSpacing=0, Spacing=0)
            else:
                grp = pymui.HGroup(InnerSpacing=0, Spacing=0)
            
            parent.InitChange()
            try:
                grp.location = master.location
                da2 = DocDisplayArea(self, self.docproxy)
                self.disp_areas.append(da2)
                grp.AddChild(da, BetterBalance(), da2)
                da.location = 0
                da.group = grp
                da.other = da2
                da2.location = 1
                da2.group = grp
                da2.other = da
                grp.da = [da, da2]
                if master.location == 0:
                    parent.AddHead(grp)
                else:
                    parent.AddTail(grp)
                parent.RemChild(master)
                self.disp_areas.remove(master)
            finally:
                parent.ExitChange()
                
        return da, da2

    def set_watcher(self, name, cb, *args):
        self._watchers[name] = (cb, args)

    def _refresh_title(self):
        self.Title = self.title_header % (self._name, self._scale*100)
        
    # Public API
    #

    def set_doc_name(self, name):
        self._name = name
        self._refresh_title()
        
    def set_scale(self, scale):
        self._scale = scale
        self._refresh_title()

    def confirm_close(self):
        return pymui.DoRequest(pymui.GetApp(),
                               gadgets= "_Yes|*_No",
                               title  = "Need confirmation",
                               format = "This document is modified and not saved yet.\nSure to close it?")

    def set_cursor_radius(self, r):
        for da in self.disp_areas:
            da.set_cursor_radius(r)
            
    def set_background_rgb(self, rgb):
        for da in self.disp_areas:
            da.set_background_rgb(rgb)
            
    def toggle_rulers(self):
        state = self.permit_rulers and not self._popruler.ShowMe.value
        root = self.RootObject.contents
        root.InitChange()
        try:
            self._popruler.ShowMe = state
            # I don't know why... but hidding only the pop, hiding all rulers...
        finally:
            root.ExitChange()

    def set_status(self, **kwds):
        pass # TODO

    @property
    def rulers(self):
        return self._popruler.ShowMe.value