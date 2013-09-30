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

import math

from math import ceil, pi, hypot

import utils
from utils import delayedmethod, _T

from view import cairo_tools as tools

class MetaEventHandler(type):
    def __new__(meta, name, bases, dct):
        cl = type.__new__(meta, name, bases, dct)
        return cl

class EventHandler(object):
    __metaclass__ = MetaEventHandler
    
    def start(self, vp): pass
    def stop(self, vp): pass
    def on_enter(self, vp, state, evt): pass
    def on_leave(self, vp, state, evt): pass
    def on_motion(self, vp, dev, evt): pass
    def on_key_pressed(self, vp, qual, key, evt): pass
    def on_key_released(self, vp, qual, key, evt): pass
    def on_button_pressed(self, vp, state, bt, evt): pass
    def on_button_released(self, vp, state, bt, evt): pass
    def on_scroll(self, vp, state, direction, evt): pass

class IdleHandler(EventHandler):
    def __init__(self):
        super(IdleHandler, self).__init__()
        
    def start(self, vp):
        vp.enable_mouse_motion()
        if vp.dev.current:
            vp.repaint_cursor(*vp.dev.current.cpos)
        else:
            vp.Redraw()
        
    def stop(self, vp):
        vp.enable_mouse_motion(False)
        vp.hide_cursor()
        
    def on_enter(self, vp, state, *a):
        if vp.focus:
            vp.enable_mouse_motion()
            vp.repaint_cursor(*state.cpos)
        
    def on_leave(self, vp, state, *a):
        vp.enable_mouse_motion(False)
        vp.hide_cursor()

    def on_motion(self, vp, dev, *e):
        vp.repaint_cursor(*dev.current.cpos)
        return True

    def on_button_pressed(self, vp, state, bt, evt):
        # Then itself
        if bt == IECODE_LBUTTON:
            vp.docproxy.draw_start(vp.dev)
            vp.set_evt_handler('draw')
            return True
        elif bt == IECODE_MBUTTON:
            qual = evt.Qualifier
            if qual & IEQUALIFIER_CONTROL:
                vp.set_evt_handler('rotate-view')
            elif qual & IEQUALIFIER_SHIFT:
                vp.set_evt_handler('drag-layer')
            else:
                vp.set_evt_handler('drag-view')
            return True

    def on_scroll(self, vp, state, direction, *a):
        if direction == NM_WHEEL_UP:
            vp.scale_up(*state.cpos)
        else:
            vp.scale_down(*state.cpos)

    def on_key_pressed(self, vp, qual, key, evt):
        k = (qual, key or evt.RawKey)
        func = self.KEYMAP_PRESSED.get(k) or self.KEYMAP_PRESSED.get(key)
        if func:
            return func(self, vp, evt)

    def on_reset(self, vp, *a):
        vp.reset()
        return True

    def on_free_sel(self, vp, *a):
        vp.set_evt_handler('draw-free-sel')
        return True

    def on_tool_sel(self, vp, *a):
        vp.set_evt_handler('tool-sel')
        return True
        
    def on_set_radius_max(self, vp, *a):
        vp.set_evt_handler('set-radius-max')
        return True
        
    KEYMAP_PRESSED = {'=': on_reset,
                      's': on_free_sel,
                      ' ': on_tool_sel,
                      'r': on_set_radius_max,
                      }

class DrawHandler(EventHandler):
    def start(self, vp):
        vp.lock_focus()
        vp.enable_mouse_motion()
    
    def stop(self, vp):
        vp.unlock_focus()
        vp.enable_mouse_motion(False)
        
    def on_button_released(self, vp, state, bt, *a):
        if bt == IECODE_LBUTTON:
            vp.docproxy.draw_end()
            vp.set_evt_handler('idle')
            return True

    def on_motion(self, vp, *a):
        vp.docproxy.record()
        return True

class DragViewHandler(EventHandler):
    def __init__(self):
        super(DragViewHandler, self).__init__()
        self._text = tools.Text()

    def start(self, vp):
        vp.lock_focus()
        vp.enable_mouse_motion()
        self.x = 0
        self.y = 0
        self._text.set_text("Dx=%-4u, Dy=%-4u" % (0,0))
        vp.add_tool(self._text)

    def stop(self, vp):
        vp.unlock_focus()
        vp.enable_mouse_motion(False)
        vp.rem_tool(self._text)
        
    def on_motion(self, vp, dev, *a):
        delta = dev.view_motion
        vp.scroll(*delta)
        self.x += delta[0]
        self.y += delta[1]
        self._text.set_text("Dx=%-4u, Dy=%-4u" % (self.x, self.y))
        vp.repaint_tools()
        return True

    def on_button_released(self, vp, state, bt, *a):
        if bt == IECODE_MBUTTON:
            vp.set_evt_handler('idle')
            return True

class DragLayerHandler(EventHandler):    
    def __init__(self):
        super(DragLayerHandler, self).__init__()
        self._text = tools.Text()

    def start(self, vp):
        vp.lock_focus()
        vp.enable_mouse_motion()
        layer = vp.docproxy.active_layer
        self.x = 0
        self.y = 0
        self._text.set_text("Dx=%-4u, Dy=%-4u" % (0,0))
        vp.add_tool(self._text)

    def stop(self, vp):
        vp.unlock_focus()
        vp.enable_mouse_motion(False)
        vp.rem_tool(self._text)
        
    def on_motion(self, vp, dev, *a):
        delta = dev.view_motion
        layer = vp.docproxy.active_layer
        self.x += delta[0]
        self.y += delta[1]
        self._text.set_text("Dx=%-4u, Dy=%-4u" % (self.x, self.y))
        area = self._text.area
        vp.docproxy.scroll_layer(*vp.get_model_distance(*delta))
        vp.update_matrix(layer.x, layer.y)
        vp.repaint_tools(area)
        vp.Redraw(area)
        return True

    def on_button_released(self, vp, state, bt, *a):
        if bt == IECODE_MBUTTON:
            vp.set_evt_handler('idle')
            return True

class RotateViewHandler(EventHandler):
    def __init__(self):
        super(RotateViewHandler, self).__init__()
        self._rot = tools.Rotate()
        self._text = tools.Text()
        
    def start(self, vp):
        vp.lock_focus()
        vp.enable_mouse_motion()
        self._angle = 0.
        self._rot.set_cursor_pos(vp.dev.current.cpos)
        self._text.set_text("Angle: 0")
        vp.add_tool(self._rot)
        vp.add_tool(self._text)

    def stop(self, vp,):
        vp.unlock_focus()
        vp.enable_mouse_motion(False)
        vp.rem_tool(self._rot)
        vp.rem_tool(self._text)

    def on_motion(self, vp, dev, *a):
        self._rot.set_cursor_pos(dev.current.cpos)
        self._text.set_text("Angle: %u" % math.degrees(self._angle))
        vp.repaint_tools()
        vp.rotate(-self._rot.dr)
        self._angle = (self._angle + self._rot.dr) % (2*pi)

    def on_button_released(self, vp, state, bt, *a):
        if bt == IECODE_MBUTTON:
            vp.set_evt_handler('idle')
            return True

class SelectionHandler(EventHandler):
    _move = False
    
    def __init__(self):
        super(SelectionHandler, self).__init__()
        self._tool = tools.SelectionDisplay()

    def start(self, vp):
        vp.enable_mouse_motion()
        # TODO: get a surface from the path by cutting the model
        self._tool.set_path(vp.selpath)
        vp.add_tool(self._tool)

    def stop(self, vp):
        vp.enable_mouse_motion(False)
        vp.rem_tool(self._tool)
        
    def on_motion(self, vp, dev, *a):
        if self._move:
            area = self._tool.area # save old area before move
            self._tool.move(*dev.view_motion)
            area = utils.join_area(area, self._tool.area) # add dirty areas
            vp.repaint_tools(area)
            vp.Redraw(area)
        return True

    def on_button_pressed(self, vp, state, bt, *a):
        if bt == IECODE_LBUTTON:
            self._move = True
            vp.lock_focus()
            return True

    def on_button_released(self, vp, state, bt, *a):
        if bt == IECODE_LBUTTON:
            self._move = False
            vp.unlock_focus()
            return True

    def on_key_pressed(self, vp, qual, key, evt):
        if key in ('\r', ' '):
            if key == '\r':
                # TODO: fix the selection
                pass
            vp.selpath = None
            vp.set_evt_handler('idle')
            return True

class DrawFreeSelectionHandler(EventHandler):
    _draw = False
    
    def __init__(self):
        super(DrawFreeSelectionHandler, self).__init__()
        self._tool = tools.DrawFreeSelection()
        self._label = tools.Text()
        self._label.set_text(_T('Enter to confirm or space'))

    def start(self, vp):
        vp.add_tool(self._tool)
        vp.add_tool(self._label)

    def stop(self, vp):
        vp.enable_mouse_motion(False)
        vp.rem_tool(self._tool)
        vp.rem_tool(self._label)

    def on_button_pressed(self, vp, state, bt, *a):
        if bt == IECODE_LBUTTON:
            vp.lock_focus()
            self._draw = True
            vp.enable_mouse_motion()
            self._tool.add_pt(state)
            vp.repaint_tools()
            vp.Redraw(self._tool.area)
            return True

    def on_button_released(self, vp, state, bt, *a):
        if bt == IECODE_LBUTTON:
            vp.unlock_focus()
            self._draw = False
            vp.enable_mouse_motion(False)
            self._tool.add_pt(state)
            vp.repaint_tools()
            vp.Redraw(self._tool.area)
            return True

    def on_motion(self, vp, dev, *a):
        if self._draw:
            self._tool.add_pt(dev.current)
            vp.repaint_tools()
            vp.Redraw(self._tool.area)
        return True

    def on_key_pressed(self, vp, qual, key, evt):
        if key in ('\r', ' '):
            if key == '\r':
                vp.selpath = self._tool.path
                vp.set_evt_handler('selection')
            else:
                vp.set_evt_handler('idle')
            return True

class ToolSelectorHandler(EventHandler):
    _move = False
    
    def __init__(self):
        super(ToolSelectorHandler, self).__init__()
        self._tool = tools.CircleTools()

    def start(self, vp):
        vp.enable_mouse_motion()
        if vp.dev.current:
            self._tool.set_center(vp.dev.current.cpos)
        vp.add_tool(self._tool)

    def stop(self, vp):
        vp.enable_mouse_motion(False)
        vp.rem_tool(self._tool)

    def on_key_released(self, vp, qual, key, evt):
        if key == ' ':
            vp.unlock_focus()
            vp.set_evt_handler('idle')
            return True
        
    def on_motion(self, vp, dev, *a):
        self._tool.cpos = dev.current.cpos
        vp.repaint_tools(self._tool.area)
        vp.Redraw(self._tool.area)
        return True

    def on_button_pressed(self, vp, state, bt, *a):
        if bt == IECODE_LBUTTON:
            return True

    def on_button_released(self, vp, state, bt, *a):
        if bt == IECODE_LBUTTON:
            return True
            
class ResizeRadiusMaxHandler(EventHandler):
    def __init__(self):
        super(ResizeRadiusMaxHandler, self).__init__()

    def start(self, vp):
        vp.lock_focus()
        vp.enable_mouse_motion()
        self.pos = vp.dev.current.cpos
        vp.repaint_cursor(*self.pos)

    def stop(self, vp):
        vp.unlock_focus()
        vp.enable_mouse_motion(False)
        vp.hide_cursor()

    def on_motion(self, vp, dev, *e):
        dr = -dev.view_motion[1]
        vp.docproxy.add_brush_radius_max(dr*.25)
        vp.repaint_cursor(*self.pos)
        return True
        
    def on_key_released(self, vp, qual, key, evt):
        if key == 'r':
            vp.set_evt_handler('idle')
            return True

