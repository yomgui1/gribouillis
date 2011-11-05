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

import gtk, gobject, cairo

from gtk import gdk
from random import random
from math import ceil

import view, main

from model.devices import *
from model.profile import Transform

from utils import delayedmethod
from view import cairo_tools as tools
from view import event, viewport

from .app import Application
from .cms import *
from .eventparser import EventParser

__all__ = [ 'DocViewer' ]

def _menu_signal(name):
    return gobject.signal_new(name, gtk.Window,
                              gobject.SIGNAL_ACTION,
                              gobject.TYPE_BOOLEAN, ())

# signal used to communicate between viewer's menu and document mediator
sig_menu_quit                = _menu_signal('menu_quit')
sig_menu_new_doc             = _menu_signal('menu_new_doc')
sig_menu_load_doc            = _menu_signal('menu_load_doc')
sig_menu_save_doc            = _menu_signal('menu_save_doc')
sig_menu_close_doc           = _menu_signal('menu_close_doc')
sig_menu_clear_layer         = _menu_signal('menu_clear_layer')
sig_menu_undo                = _menu_signal('menu_undo')
sig_menu_redo                = _menu_signal('menu_redo')
sig_menu_redo                = _menu_signal('menu_flush')
sig_menu_load_background     = _menu_signal('menu_load_background')
sig_menu_load_image_as_layer = _menu_signal('menu_load_image_as_layer')


class DocDisplayArea(gtk.DrawingArea, viewport.BackgroundMixin):
    """DocDisplayArea class.

    This class is responsible to display a given document.
    It owns and handles display properties like affine transformations,
    background, and so on.
    It handles user events from input devices to modify the document.
    This class can also dispay tools and cursor.
    """

    width = height = 0
    _cur_area = None
    _cur_pos = (0,0)
    _cur_on = False
    _evtcontext = None
    _swap_x = _swap_y = None
    _debug = 0
    selpath = None

    def __init__(self, win, docproxy):
        super(DocDisplayArea, self).__init__()
        
        self._win = win
        self.docproxy = docproxy
        self.device = InputDevice()

        # Viewport's
        self._docvp = view.DocumentViewPort(docproxy)
        self._toolsvp = view.ToolsViewPort()
        
        self._curvp = tools.Cursor()
        self._curvp.set_radius(docproxy.document.brush.radius_max)

        self._evmgr = event.EventManager(vp=self)
        self._evmgr.set_current('Viewport')

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

        self.set_background(main.Gribouillis.TRANSPARENT_BACKGROUND)

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
        
        eat, self._evtcontext = self._evtcontext.process('cursor-motion', EventParser(evt))
        return eat

    def on_scroll(self, widget, evt):
        # There is only one event in GDK for mouse wheel change,
        # so split it as two key events.
        ep = EventParser(evt)
        eat1, self._evtcontext = self._evtcontext.process('key-pressed', ep)
        eat2, self._evtcontext = self._evtcontext.process('key-released', ep)
        return eat1 or eat2

    def on_enter(self, widget, evt):
        eat, self._evtcontext = self._evtcontext.process('cursor-enter', EventParser(evt))
        return eat
        
    def on_leave(self, widget, evt):
        eat, self._evtcontext = self._evtcontext.process('cursor-leave', EventParser(evt))
        return eat

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

class DocWindow(gtk.Window):
    #### Private API ####

    __title_fmt = "Document: %s"
    
    def __init__(self, docproxy):
        super(DocWindow, self).__init__()

        self.viewports = []
        self.docproxy = docproxy        
        self.set_can_focus(True)

        ui = '''<ui>
        <menubar name="MenuBar">
            <menu action='File'>
                <menuitem action="new-doc"/>
                <menuitem action="open-doc"/>
                <menuitem action="save-doc"/>
                <menuitem action="close-doc"/>
                <separator/>
                <menuitem action="quit"/>
            </menu>
            <menu action='Edit'>
                <menuitem action="cmd-undo"/>
                <menuitem action="cmd-redo"/>
                <menuitem action="cmd-flush"/>
                <menuitem action="cmd-win"/>
            </menu>
            <menu action='View'>
                <menuitem action="view-reset"/>
                <menuitem action="view-load-background"/>
            </menu>
            <menu action='Layers'>
                <menuitem action="layers-win"/>
                <menuitem action="layers-load-image"/>
                <menuitem action="layers-clear-active"/>
            </menu>
            <menu action='Color'>
                <menuitem action="color-win"/>
                <menuitem action="assign-profile"/>
                <menuitem action="convert-profile"/>
            </menu>
            <menu action='Tools'>
                <menuitem action="brush-house-win"/>
                <menuitem action="brush-win"/>
                <menuitem action="brush-radius-inc"/>
                <menuitem action="brush-radius-dec"/>
                <separator/>
                <menuitem action="line-ruler-toggle"/>
                <menuitem action="ellipse-ruler-toggle"/>
                <menuitem action="navigator-toggle"/>
            </menu>
        </menubar>
        </ui>
        '''

        # UI
        uimanager = gtk.UIManager()
        accelgroup = uimanager.get_accel_group()
        self.add_accel_group(accelgroup)

        uimanager.add_ui_from_string(ui) ## UI description

        self._topbox = topbox = gtk.VBox(False, 1)
        topbox.set_border_width(1)
        self.add(topbox)

        # Actions
        actiongroup = gtk.ActionGroup('GribouillisActionGroup')
        self.actiongroup = actiongroup

        actiongroup.add_actions([
            ('File', None, 'Gribouillis'),
            ('Edit', None, 'Edit'),
            ('Layers', None, 'Layers'),
            ('Brush', None, 'Brush'),
            ('Color', None, 'Color'),
            ('View', None, 'View'),
            ('Tools', None, 'Tools'),
            #('', None, ''),

            ('new-doc', gtk.STOCK_NEW, 'New Document...', None, None, lambda *a: self.emit('menu_new_doc')),
            ('open-doc', gtk.STOCK_OPEN, 'Open Document...', None, None, lambda *a: self.emit('menu_load_doc')),
            ('save-doc', gtk.STOCK_SAVE, 'Save Document...', None, None, lambda *a: self.emit('menu_save_doc')),
            ('close-doc', gtk.STOCK_CLOSE, 'Close Document', None, None, lambda *a: self.emit('menu_close_doc')),
            ('quit', gtk.STOCK_QUIT, 'Quit!', None, 'Quit the Program', lambda *a: self.emit('menu_quit')),
            ('cmd-undo', gtk.STOCK_UNDO, 'Undo last command', '<Control>z', None, lambda *a: self.emit('menu_undo')),
            ('cmd-redo', gtk.STOCK_REDO, 'Redo last command', '<Control><Shift>z', None, lambda *a: self.emit('menu_redo')),
            ('cmd-flush', gtk.STOCK_APPLY, 'Flush commands historic', '<Control><Alt>z', None, lambda *a: self.emit('menu_flush')),
            ('cmd-win', gtk.STOCK_PROPERTIES, 'Open commands historic', '<Alt>h', None, lambda *a: Application().open_cmdhistoric()),
            ('layers-load-image', gtk.STOCK_ADD, 'Load image as new layer...', '<Control><Alt>z', None, lambda *a: self.emit('menu_load_image_as_layer')),
            ('layers-win', gtk.STOCK_PROPERTIES, 'Open layers list window', '<Control>l', None, lambda *a: Application().open_layer_mgr()),
            ('layers-clear-active', gtk.STOCK_CLEAR, 'Clear active layer', '<Control>k', None, lambda *a: self.emit('menu_clear_layer')),
            ('view-reset', None, 'Reset', 'equal', None, lambda *a: self.vp.reset()),
            ('view-load-background', None, 'Load background image', '<Control><Alt>b', None, lambda *a: self.emit('menu_load_background')),
            ('color-win', gtk.STOCK_PROPERTIES, 'Open color editor', '<Control>c', None, lambda *a: Application().open_colorwin()),
            ('brush-house-win', None, 'Open brush house window', None, None, lambda *a: Application().open_brush_house()),
            ('brush-win', gtk.STOCK_PROPERTIES, 'Edit brush properties', '<Control>b', None, lambda *a: Application().open_brush_editor()),
            ('brush-radius-inc', gtk.STOCK_ADD, 'Increase brush size', 'plus', None, lambda *a: self.increase_brush_radius()),
            ('brush-radius-dec', gtk.STOCK_REMOVE, 'Decrease brush size', 'minus', None, lambda *a: self.decrease_brush_radius()),
            ('line-ruler-toggle', None, 'Toggle line ruler', None, None, lambda a: self._toggle_line_ruler()),
            ('ellipse-ruler-toggle', None, 'Toggle ellipse ruler', None, None, lambda a: self._toggle_ellipse_ruler()),
            ('navigator-toggle', None, 'Toggle Navigator', None, None, lambda a: self._toggle_navigator()),
            ('assign-profile', None, 'Assign Color Profile', None, None, lambda a: self.assign_icc()),
            ('convert-profile', None, 'Convert to Color Profile', None, None, lambda a: self.convert_icc()),
            #('', None, '', None, None, lambda *a: self.emit('')),
            ])

        #actiongroup.add_toggle_actions([
        #    ])

        uimanager.insert_action_group(actiongroup, 0)

        # MenuBar
        menubar = uimanager.get_widget('/MenuBar')
        topbox.pack_start(menubar, False)

        # Default editor
        vp = DocDisplayArea(self, docproxy)
        self._add_vp(vp)

        #vp = DocDisplayArea(self, docproxy)
        #self._add_vp(vp)

        self.set_default_size(600, 400)
        self.move(0,0)
        self.show_all()

        # Set defaults
        self.set_doc_name(docproxy.document.name)

    def _add_vp(self, vp):
        self.viewports.append(vp)
        self._topbox.pack_start(vp, True, True, 0)
        self.vp = vp

    #### Public API ####

    def set_doc_name(self, name):
        self.set_title(self.__title_fmt % name)

    def confirm_close(self):
        dlg = gtk.Dialog("Sure?", self,
                         gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                         (gtk.STOCK_YES, gtk.RESPONSE_OK,
                          gtk.STOCK_NO, gtk.RESPONSE_CANCEL))
        dlg.set_default_response(gtk.RESPONSE_CANCEL)
        response = dlg.run()
        dlg.destroy()
        return response == gtk.RESPONSE_OK

    def load_background(self, evt=None):
        filename = Application().get_image_filename(parent=self)
        if filename:
            self.vp.set_background(filename)

    def set_cursor_radius(self, r):
        for vp in self.viewports:
            vp.set_cursor_radius(r)

    def assign_icc(self):
        dlg = AssignCMSDialog(self.docproxy, self)
        result = dlg.run()
        if result == gtk.RESPONSE_OK:
            self.docproxy.profile = dlg.get_profile()
        dlg.destroy()

    def convert_icc(self):
        dlg = ConvertDialog(self.docproxy, self)
        result = dlg.run()
        if result == gtk.RESPONSE_OK:
            dst_profile = dlg.get_destination()
            src_profile = self.docproxy.profile
            ope = Transform(src_profile, dst_profile)
            self.vp.apply_ope(ope)
            self.vp.redraw()
        dlg.destroy()
