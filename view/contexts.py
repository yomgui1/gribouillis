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

import os
import math
from . import cairo_tools as tools
from functools import wraps, partial

import cairo
from glob import glob

import view, main
from model import prefs
from utils import _T, resolve_path

# Defaults for prefs
prefs.add_default('view-toolswheel-binding',
    ['new layer',
     'open layer manager window',
     'save document as',
     'open preferences window',
     'open color manager window',
     'undo',
     'load document',
     'redo'])

# This list uses Higlander icons
prefs.add_default('view-icons-names',
    ['AddLayer_0',
     'Layer_0',
     'Save_0',
     'Prefs_0',
     'Color_0',
     'Undo_0',
     'Open_0',
     'Redo_0',

     'AddLayer_1', 
     'Layer_1',
     'Save_1',
     'Prefs_1',
     'Color_1',
     'Undo_1',
     'Open_1',
     'Redo_1'])

ICONS = {}
ALL_CONTEXTS = {}
ALL_EVENT_TYPES = []
EVENT_TAG_REPEAT = 0x40000000
EVENT_TAG_ANY    = 0x80000000

def reload_icons(path):
    for name in glob(os.path.join(resolve_path(path), '*.png')):
        ICONS[os.path.splitext(os.path.basename(name))[0]] = cairo.ImageSurface.create_from_png(name)
        
reload_icons(prefs['view-icons-path'])

new_context = lambda name, **kwds: ALL_CONTEXTS[name](**kwds)

#===================================================================================
# Commands handling
#

ALL_COMMANDS = {}
def command(name):
    def decorator(func):
        ALL_COMMANDS[name] = func
        return func
    return decorator

#===================================================================================
# Event base classes
#

class MetaEvent(type):
    def __new__(metacl, name, bases, dct):
        cl = type.__new__(metacl, name, bases, dct)
        if dct.pop('NAME', None):
            ALL_EVENT_TYPES.append(cl)
        return cl

    def __str__(cl):
        return cl.NAME

class EventBase(metaclass=MetaEvent):
    repeat = False
    
    def __str__(self):
        return self.NAME
        
    @property
    def fullkey(self): pass
        
    @property
    def key(self):
        return self.fullkey
        
class SetupEvent(EventBase):
    def __str__(self):
        return 'setup'
        
    @property
    def fullkey(self):
        return 0x0FFFFFFF

    @classmethod
    def encode(cl, key):
        return 0x0FFFFFFF

class CleanupEvent(EventBase):
    def __str__(self):
        return 'cleanup'
        
    @property
    def fullkey(self):
        return 0x0FFFFFFE

    @classmethod
    def encode(cl, key):
        return 0x0FFFFFFE


#===================================================================================
# Context base classes and functions
#

def action(name):
    def decorator(func):
        func._act_name = name
        func._act_ctx = None
        return func
    return decorator

class MetaContext(type):
    def __new__(meta, clname, bases, dct):
        cl = type.__new__(meta, clname, bases, dct)
        if clname != 'Context':
            if clname != 'ModalContext':
                ALL_CONTEXTS[dct['NAME']] = cl
            
            cl.AVAIL_ACTIONS = {}
            cl.BINDINGS = {}
                        
            # Inherit BINDINGS and AVAIL_ACTIONS dicts
            for base in bases:
                if hasattr(base, 'AVAIL_ACTIONS'):
                    cl.AVAIL_ACTIONS.update(base.AVAIL_ACTIONS)
        
            # Construct a list of all available actions for this context
            actdict = cl.AVAIL_ACTIONS
            for v in dct.values():
                if hasattr(v, '_act_name'):
                    if v in actdict:
                        raise SystemError("Already defined action for context %s: %s" % (clname, v._act_name))
                    v._act_ctx = cl
                    actdict[v._act_name] = v

            cl.AVAIL_ACTION_NAMES = sorted(cl.AVAIL_ACTIONS.keys())
        return cl
        
    def __init__(cl, clname, bases, dct):
        type.__init__(cl, clname, bases, dct)
        cl.reset_bindings()
            

class Context(metaclass=MetaContext):
    __parent = None
    __next = None
    
    def __init__(self, **kwds):
        self._data = kwds
        self.__dict__.update(kwds)
    
    @classmethod
    def reset_bindings(cl):
        cl.BINDINGS = {0x0FFFFFFF: cl.setup, 0x0FFFFFFE: cl.cleanup}
        
    @classmethod
    def get_action(cls, event):
        # Search with full key (mods+key)
        name = cls.BINDINGS.get(event.fullkey)
        if not name:
            # Repeat events are not accepted
            name = cls.BINDINGS.get(EVENT_TAG_REPEAT | event.fullkey)
            if not name:
                # Search for key + 'any' mods
                name = cls.BINDINGS.get(EVENT_TAG_ANY | event.key)
                if not name:
                    name = cls.BINDINGS.get(EVENT_TAG_ANY | EVENT_TAG_REPEAT | event.key)
                    if not name:
                        return
        elif event.repeat:
            return
                
        if callable(name):
            return name
        
        try:
            return getattr(cls, name)
        except:
            return name
        
    def process(self, event):
        """process(event) -> eat_state, new_context
        
        Check if context has action to process for the given event.
        
        Returns 2-tuple:
            - eat_state is a boolean set to True if the system shall stop the event progression.
            - new_context is the next context to use (could be the same one).
        """
                
        # Check for action in context itself
        action = self.get_action(event)
        #print("[%s] Event: %s: %s" % (self, event, action))

        # If not found check parent if we're not a modal context
        if not action and not isinstance(self, ModalContext):
            ctx = self
            while not action and ctx.__parent:
                ctx = ctx.__parent
                action = ctx.get_action(event)
        else:
            ctx = self
            
        if action:
            ctx.__next = self
            eat = not action(ctx, event)
            if ctx.__next != self:
                return eat, ctx.__next
            return eat, self
        
        return False, self
        
    def enter_context(self, name, **kwds):
        for k, v in self._data.items():
            kwds.setdefault(k, v)
        self.__next = new_context(name, **kwds)
        self.__next.__parent = self
        self.__next.process(SetupEvent())
        return self.__next
        
    def exit_context(self):
        self.process(CleanupEvent())
        self.__next = self.__parent
        self.__next.process(SetupEvent())
        return self.__next
        
    def swap_context(self, name, **kwds):
        self.process(CleanupEvent())
        self.__next = new_context(name, **kwds)
        return self.__next

    def _set_parent(self, ctx):
        self.__parent = ctx
        
    ## Internal actions
    
    def setup(self, *a): pass
    def cleanup(self, *a): pass
    
    # User trigged Actions
    #
    
    @action(_T('eat event'))
    def eat_event(self, event): pass
    
class ModalContext(Context):
    def on_confirm(ctx, event): pass

    # User trigged Actions
    #
    
    @action(_T('confirm'))
    def confirm(ctx, event):
        try:
            ctx.viewport.get_device_state(event)
            cmd = ctx.on_confirm(event)
        finally:
            newctx = ctx.exit_context()
            
        if cmd in ALL_COMMANDS:
            res = ALL_COMMANDS[cmd](view.app.ctx)
            if res:
                # TODO: horrible trick! change me soon!
                ctx.enter_context(res)._set_parent(newctx)

    @action(_T('cancel'))
    def cancel(ctx, event):
        ctx.exit_context()
    
    @action(_T('eat event'))
    def eat_event(self, event): pass

#===================================================================================
# Contexts
#

class ApplicationCtx(Context):
    NAME = 'Application'
        
    @action(_T('new-document'))
    def undo(self, event):
        self.app.mediator.new_document()
    
    @action(_T('load-document'))
    def undo(self, event):
        self.app.mediator.load_document()
        
class DocumentCtx(Context):
    NAME = 'Document'
    
    # User trigged Actions
    #
    
    @action(_T('save-document'))
    def save_document(self, event):
        self.app.mediator.save_document()
        
    @action(_T('save-as-document'))
    def save_as_document(self, event):
        self.app.mediator.save_as_document()
        
    @action(_T('undo'))
    def undo(self, event):
        self.docproxy.sendNotification(main.UNDO)
        
    @action(_T('redo'))
    def redo(self, event):
        self.docproxy.sendNotification(main.REDO)
    
    @action(_T('lighten brush color of 10%'))
    def color_lighten(self, event):
        self.docproxy.multiply_color(1.0, 1.0, 1.1)
        
    @action(_T('darken brush color of 10%'))
    def color_darken(self, event):
        self.docproxy.multiply_color(1.0, 1.0, 0.9)
        
    @action(_T('saturate brush color of 10%'))
    def color_saturate(self, event):
        self.docproxy.multiply_color(1.0, 1.1, 1.0)
        
    @action(_T('desaturate brush color of 10%'))
    def color_desaturate(self, event):
        self.docproxy.multiply_color(1.0, 0.9, 1.0)
    
    @action(_T('clear active layer'))
    def clear_active_layer(self, event):
        self.docproxy.clear_layer(self.docproxy.active_layer)
        
    @action(_T('toggle rulers visibility'))
    def toggle_rulers(self, event):
        self.window.toggle_rulers()
        
class ViewPortCtx(Context):
    NAME = 'Viewport'

    _rot_ruler_warn = True
    
    def __init__(self, **kwds):
        super(ViewPortCtx, self).__init__(**kwds)
        self._text = tools.Text()
    
    # Internal Actions
    #
    
    def setup(self, event):
        vp = self.viewport
        vp.enable_motion_events()
        vp.show_brush_cursor()
    
    # User trigged Actions
    #
    
    @action(_T('activate'))
    def activate(self, event):
        vp = self.viewport
        vp.get_device_state(event)
        vp.show_brush_cursor()
        vp.enable_motion_events()

    @action(_T('desactivate'))
    def desactivate(self, event):
        self.viewport.show_brush_cursor(False)
        self.viewport.enable_motion_events(False)
    
    @action(_T('move brush cursor'))
    def move_cursor(self, event):
        self.viewport.repaint_cursor(*event.get_cursor_position())
        
    ## Model modifying actions
    
    @action(_T('start to stroke or hit handler'))
    def on_selection(self, event):
        handler = self.viewport.get_handler_at_pos(*event.get_cursor_position())
        if handler:
            if handler.kill:
                self.viewport.rem_tool(handler.tool)
            else:
                self.enter_context('Handler', handler=handler)
        else:
            self.viewport.get_device_state(event)
            self.enter_context('Brush Stroke')

    @action(_T('start to drag layer'))
    def start_drag_layer(self, event):
        self.viewport.get_device_state(event)
        self.enter_context('Drag Layer')

    @action(_T('start to rotate layer'))
    def start_rotate_layer(self, event):
        self.viewport.get_device_state(event)
        self.enter_context('Rotate Layer')
        
    @action(_T('pick brush color'))
    def get_brush_color(self, event):
        color = self.viewport.get_average_color(*event.get_cursor_position())
        if color:
            self.docproxy.set_brush_color_rgb(*color)

    ## Brush modifying actions
    
    @action(_T('interactive set max radius'))
    def interactive_radius_max(self, event):
        self.viewport.get_device_state(event)
        self.enter_context('Max Radius Interactive')

    @action(_T('interactive set both radius'))
    def interactive_radius(self, event):
        self.viewport.get_device_state(event)
        self.enter_context('Both Radius Interactive')
        
    @action(_T('set erase mode'))
    def set_erase_mode(self, event):
        self.docproxy.drawbrush.set_erase(0.0)
        
    @action(_T('unset erase mode'))
    def unset_erase_mode(self, event):
        self.docproxy.drawbrush.set_erase(1.0)
        
    @action(_T('pick pixel color'))
    def get_pixel_color(self, event):
        color = self.viewport.get_exact_color(*event.get_cursor_position())
        if color:
            self.docproxy.set_brush_color_rgb(*color)
            
    @action(_T('enter in pick color mode'))
    def enter_pick_mode(self, event):
        self.viewport.get_device_state(event)
        self.enter_context('Pick Mode')
        
    ## View modifying actions
    
    @action(_T('reset all viewport transformations'))
    def reset_view(self, event):
        vp = self.viewport
        vp.mediator.view_reset(vp, event.get_cursor_position())
        
    @action(_T('viewport zoom in'))
    def zoom_in(self, event):
        vp = self.viewport
        vp.mediator.view_scale_up(vp, event.get_cursor_position())
        
    @action(_T('viewport zoom out'))
    def zoom_out(self, event):
        vp = self.viewport
        vp.mediator.view_scale_down(vp, event.get_cursor_position())
        
    @action(_T('reset viewport zoom'))
    def zoom_reset(self, event):
        vp = self.viewport
        vp.mediator.view_scale_reset(vp, event.get_cursor_position())
    
    @action(_T('start to drag view'))
    def start_drag_view(self, event):
        self.viewport.get_device_state(event)
        self.enter_context('Drag Viewport')
        
    @action(_T('reset viewport translation'))
    def drag_view_reset(self, event):
        vp = self.viewport
        vp.mediator.view_translate_reset(vp)
        
    @action(_T('start to rotate view'))
    def start_rotate_view(self, event):
        # Check if rulers are hidden or shown
        # Rulers don't work correctly with a view rotation.
        if self.window.rulers:
            if self._rot_ruler_warn:
                self.docproxy.sendNotification(main.SHOW_WARNING_DIALOG,
                                               "View rotation is not possible when rulers are active.\n"
                                               "The next try will automatically remove them.")
                self._rot_ruler_warn = False
                return
            
        self.viewport.get_device_state(event)
        self.enter_context('Rotate Viewport')
        
    @action(_T('reset viewport rotation'))
    def rotate_view_reset(self, event):
        vp = self.viewport
        vp.mediator.view_rotate_reset(vp, event.get_cursor_position())
        
    @action(_T('swap viewport left-right'))
    def swap_x(self, event):
        vp = self.viewport
        vp.mediator.view_swap_x(vp, event.get_cursor_position()[0])
        
    @action(_T('swap viewport top-bottom'))
    def swap_y(self, event):
        vp = self.viewport
        vp.mediator.view_swap_y(vp, event.get_cursor_position()[1])
        
    ## Tools actions
    
    @action(_T('toggle line guide'))
    def toggle_line_guide(self, event):
        vp = self.viewport
        vp.mediator.toggle_guide(vp, 'line')
    
    @action(_T('toggle ellipse guide'))
    def toggle_ellipse_guide(self, event):
        vp = self.viewport
        vp.mediator.toggle_guide(vp, 'ellipse')
        
    @action(_T('show last colors used'))
    def last_colors_selector(self, event):
        self.viewport.get_device_state(event)
        self.enter_context('Last Colors Selector')

    @action(_T('show tools selector'))
    def start_tools_selector(self, event):
        self.viewport.get_device_state(event)
        self.enter_context('Tools Selector')

class BrushStrokeModal(ModalContext):
    NAME = 'Brush Stroke'
    
    def setup(self, event):
        vp = self.viewport
        vp.lock_focus()
        vp.enable_motion_events()
        vp.show_brush_cursor(False)
        vp.docproxy.draw_start(vp.device)
        
    def cleanup(self, event):
        vp = self.viewport
        vp.docproxy.draw_end()
        vp.unlock_focus()
        
    # User trigged Actions
    #
    
    @action(_T('draw at cursor'))
    def draw(self, event):
        self.viewport.docproxy.record(self.viewport.get_device_state(event))

    @action(_T('set erase mode'))
    def set_erase_mode(self, event):
        self.docproxy.drawbrush.set_erase(0.0)
        
    @action(_T('unset erase mode'))
    def unset_erase_mode(self, event):
        self.docproxy.drawbrush.set_erase(1.0)
        
class DragViewModal(ModalContext):
    NAME = 'Drag Viewport'

    def __init__(self, **kwds):
        super(DragViewModal, self).__init__(**kwds)
        self._text = tools.Text()
    
    def setup(self, event):
        vp = self.viewport
        vp.lock_focus()
        vp.enable_motion_events()
        vp.show_brush_cursor(False)
        
        self._cpos = vp.device.current.cpos
        self._x = 0
        self._y = 0
        self._text.set_text("Dx=%-4u, Dy=%-4u" % (0,0))
        
        vp.add_tool(self._text)
        vp.enable_fast_filter()
        
    def cleanup(self, event):
        vp = self.viewport
        vp.unlock_focus()
        vp.rem_tool(self._text)
        vp.enable_fast_filter(False)
        vp.repaint()
        
    # User trigged Actions
    #

    @action(_T('drag view'))
    def drag_view(self, event):
        vp = self.viewport
        
        # Compute cursor delta's
        cpos = event.get_cursor_position()
        dx = cpos[0] - self._cpos[0]
        dy = cpos[1] - self._cpos[1]
        self._x += dx
        self._y += dy
        self._cpos = cpos
        
        # update display
        self._text.set_text("Dx=%-4u, Dy=%-4u" % (self._x, self._y))
        vp.repaint_tools(clip=self._text.area)
        vp.scroll(dx, dy)

class RotateViewModal(ModalContext):
    NAME = 'Rotate Viewport'
        
    _rot = tools.Rotate()
    _text = tools.Text()
    
    def setup(self, event):
        vp = self.viewport
        vp.lock_focus()
        vp.enable_motion_events()
        vp.show_brush_cursor(False)
        
        self._angle = 0.
        self._rot.set_cursor_pos(vp.device.current.cpos)
        self._text.set_text("Angle: 0")
        
        vp.add_tool(self._rot)
        vp.add_tool(self._text)
        vp.enable_fast_filter()
        
    def cleanup(self, event):
        vp = self.viewport
        vp.unlock_focus()
        
        vp.rem_tool(self._rot)
        vp.rem_tool(self._text)

        vp.enable_fast_filter(False)
        vp.repaint()
        
    @action(_T('rotate view'))
    def rotate_view(self, event):
        vp = self.viewport
        
        self._rot.set_cursor_pos(event.get_cursor_position())
        self._angle = (self._angle + self._rot.dr) % (2*math.pi)
        self._text.set_text("Angle: %u" % math.degrees(self._angle))
        
        vp.repaint_tools()
        vp.rotate(-self._rot.dr)

class LastColorModal(ModalContext):
    NAME = 'Last Colors Selector'
    
    _colors = [ None ] * 8
                
    def __init__(self, **kwds):
        super(LastColorModal, self).__init__(**kwds)
        self._tool = tools.ColorWheel()
        self.push_color(self.viewport.docproxy.get_brush_color_rgb())
    
    @classmethod
    def push_color(cl, rgb):
        if rgb != cl._colors[0]:
            cl._colors.insert(0, rgb)
            cl._colors.pop(-1)
    
    def setup(self, event):
        vp = self.viewport
        vp.enable_motion_events()
        vp.show_brush_cursor(False)
        self._tool.set_colors(self._colors)
        self._tool.set_center(vp.device.current.cpos)
        vp.add_tool(self._tool)
        
    def cleanup(self, event):
        self.viewport.rem_tool(self._tool)
        
    def on_confirm(self, event):
        i = self._tool.selection
        if i >= 0:
            # Slice the historic and put the selected color as first
            rgb = self._colors.pop(i)
            self._colors.insert(0, rgb)
            self.viewport.docproxy.set_brush_color_rgb(*rgb)
        
    # User trigged Actions
    #

    @action(_T('check cursor position'))
    def check_cursor(self, event):
        vp = self.viewport
        cpos = event.get_cursor_position()
        if vp.is_tool_hit(self._tool, *cpos):
            # TODO: CPU eating when pen used
            self._tool.cpos = cpos
        elif self._tool.cpos:
            self._tool.cpos = None
        else:
            return
            
        vp.repaint_tools(self._tool.area)
        vp.redraw(self._tool.area)

class ToolsModal(ModalContext):
    NAME = 'Tools Selector'

    _sel = -1
    
    def __init__(self, **kwds):
        super(ToolsModal, self).__init__(**kwds)
        self._tool = tools.ToolsWheel()
        self.refresh()
    
    def refresh(self):
        icons = []
        for name in prefs['view-icons-names']:
            icons.append(ICONS[name])
        self._tool.set_icons(icons)
        
    def setup(self, event):
        vp = self.viewport
        vp.enable_motion_events()
        vp.show_brush_cursor(False)
        self._tool.set_center(vp.device.current.cpos)
        vp.add_tool(self._tool)
        
    def cleanup(self, event):
        self.viewport.rem_tool(self._tool)
        
    def on_confirm(self, event):
        i = self._tool.selection
        if i >= 0:
            return prefs['view-toolswheel-binding'][i]
        
    # User trigged Actions
    #

    @action(_T('check cursor position'))
    def check_cursor(self, event):
        vp = self.viewport
        cpos = event.get_cursor_position()
        if vp.is_tool_hit(self._tool, *cpos):
            # TODO: CPU eating when pen used
            self._tool.cpos = cpos
        elif self._tool.cpos:
            self._tool.cpos = None
        else:
            return
            
        vp.repaint_tools(self._tool.area)
        vp.redraw(self._tool.area)

class SetMaxRadiusModal(ModalContext):
    NAME = 'Max Radius Interactive'

    def setup(self, event):
        vp = self.viewport
        vp.lock_focus()
        vp.enable_motion_events()
        self._cpos = self._first_cpos = vp.show_brush_cursor()
        
    def cleanup(self, event):
        self.viewport.unlock_focus()
        
    # User trigged Actions
    #
    
    @action(_T('resize brush'))
    def resize_brush(self, event):
        vp = self.viewport
        cpos = event.get_cursor_position()
        dr = self._cpos[1] - cpos[1]
        vp.docproxy.add_brush_radius_max(dr*.25)
        vp.repaint_cursor(*self._first_cpos)
        self._cpos = cpos

class SetBothRadiusModal(ModalContext):
    NAME = 'Both Radius Interactive'

    def setup(self, event):
        vp = self.viewport
        vp.lock_focus()
        vp.enable_motion_events()
        self._cpos = self._first_cpos = vp.show_brush_cursor()
        
    def cleanup(self, event):
        self.viewport.unlock_focus()
        
    # User trigged Actions
    #
    
    @action(_T('resize brush'))
    def resize_brush(self, event):
        vp = self.viewport
        cpos = event.get_cursor_position()
        dr = self._cpos[1] - cpos[1]
        vp.docproxy.add_brush_radius(dr*.25)
        vp.repaint_cursor(*self._first_cpos)
        self._cpos = cpos

class DragLayerModal(ModalContext):
    NAME = 'Drag Layer'
        
    def __init__(self, **kwds):
        super(DragLayerModal, self).__init__(**kwds)
        self._text = tools.Text()
    
    def setup(self, event):
        vp = self.viewport
        vp.lock_focus()
        vp.enable_motion_events()
        vp.show_brush_cursor(False)
        
        self._old_mat = cairo.Matrix(*self.docproxy.document.active.matrix)
        self._cpos = vp.device.current.cpos
        self._x = 0
        self._y = 0
        self._text.set_text("Dx=%-4u, Dy=%-4u" % (0,0))
        
        vp.add_tool(self._text)
        vp.enable_fast_filter()
        
    def cleanup(self, event):
        vp = self.viewport
        vp.unlock_focus()
        vp.rem_tool(self._text)
        vp.enable_fast_filter(False)
        vp.repaint()
        
    def on_confirm(self, event):
        docproxy = self.viewport.docproxy
        layer = docproxy.active_layer
        docproxy.record_layer_matrix(layer, self._old_mat)
        
    # User trigged Actions
    #

    @action(_T('drag layer'))
    def drag_layer(self, event):
        vp = self.viewport
        tool = self._text
        
        # Compute cursor delta's
        cpos = event.get_cursor_position()
        dx = cpos[0] - self._cpos[0]
        dy = cpos[1] - self._cpos[1]
        self._x += dx
        self._y += dy
        self._cpos = cpos
        
        # update display
        tool.set_text("Dx=%-4u, Dy=%-4u" % (self._x, self._y))
        vp.repaint_tools(tool.area, redraw=True)
        vp.docproxy.layer_translate(*vp.get_model_distance(dx, dy))
        
class RotateLayerModal(ModalContext):
    NAME = 'Rotate Layer'
    
    def __init__(self, **kwds):
        super(RotateLayerModal, self).__init__(**kwds)
        self._text = tools.Text()
        self._rot = tools.Rotate()
        
    def setup(self, event):
        vp = self.viewport
        vp.lock_focus()
        vp.enable_motion_events()
        vp.show_brush_cursor(False)

        self._old_mat = cairo.Matrix(*self.docproxy.document.active.matrix)
        pos = vp.width/2, vp.height/2
        pos = vp.get_model_point(*pos)
        self._ro = vp.docproxy.get_layer_pos(*pos)
        
        self._angle = 0.
        self._rot.set_cursor_pos(vp.device.current.cpos)
        self._text.set_text("Angle: 0")

        vp.add_tool(self._rot)
        vp.add_tool(self._text)
        vp.enable_fast_filter()
        
    def cleanup(self, event):
        vp = self.viewport
        vp.unlock_focus()
        vp.rem_tool(self._rot)
        vp.rem_tool(self._text)
        
        # Force fine display
        vp.enable_fast_filter(False)
        vp.repaint()
        
    def on_confirm(self, event):
        docproxy = self.viewport.docproxy
        layer = docproxy.active_layer
        docproxy.record_layer_matrix(layer, self._old_mat)
        
    # User trigged Actions
    #
    
    @action(_T('rotate Layer'))
    def rotate_Layer(self, event):
        vp = self.viewport
        
        self._rot.set_cursor_pos(event.get_cursor_position())
        self._text.set_text("Angle: %u" % math.degrees(self._angle))
        
        # update display
        vp.repaint_tools(self._text.area, redraw=True)
        vp.repaint_tools(self._rot.area, redraw=True)
        vp.docproxy.layer_rotate(-self._rot.dr, *self._ro)
        
        self._angle = (self._angle + self._rot.dr) % (2*math.pi)

class HandlerModal(ModalContext):
    NAME = 'Handler'
    
    def setup(self, event):
        assert hasattr(self, 'handler')
        
        vp = self.viewport
        vp.lock_focus()
        vp.enable_motion_events()
        vp.show_brush_cursor(False)
        
    def cleanup(self, event):
        self.viewport.unlock_focus()
           
    # User trigged Actions
    #
    
    @action(_T('cursor move'))
    def cursor_move(self, event):
        hl = self.handler
        tool = hl.tool
        tool.move_handler(hl, *event.get_cursor_position())
        
        # Clear old and draw new position
        self.viewport.repaint_tools(tool.area, redraw=True)
        self.viewport.repaint_tools(tool.area, redraw=True)

class PickModal(ModalContext):
    NAME = 'Pick Mode'
    
    def __init__(self, **kwds):
        super(PickModal, self).__init__(**kwds)
        
    def setup(self, event):
        vp = self.viewport
        vp.enable_motion_events()
        vp.show_brush_cursor(True)
        vp.pick_mode(True)
        
    def cleanup(self, event):
        self.viewport.pick_mode(False)
                
    def on_confirm(self, event):
        color = self.viewport.get_exact_color(*event.get_cursor_position())
        if color:
            self.docproxy.set_brush_color_rgb(*color)
        
    # User trigged Actions
    #

    @action(_T('move brush cursor'))
    def move_cursor(self, event):
        self.viewport.repaint_cursor(*event.get_cursor_position())
        