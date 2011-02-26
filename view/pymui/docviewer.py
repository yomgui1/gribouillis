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

import pymui, cairo, time

import model, view, main

from model.devices import *
from utils import Mediator, mvcHandler, RECORDABLE_COMMAND, idle_cb
from .app import Application

__all__ = [ 'DocViewer', 'DocumentMediator' ]

IECODE_UP_PREFIX = 0x80
IECODE_LBUTTON   = 0x68
IECODE_RBUTTON   = 0x69
IECODE_MBUTTON   = 0x6A

IEQUALIFIER_LSHIFT   = 0x0001
IEQUALIFIER_RSHIFT   = 0x0002
IEQUALIFIER_CONTROL  = 0x0008
IEQUALIFIER_LALT     = 0x0010
IEQUALIFIER_RALT     = 0x0020
IEQUALIFIER_LCOMMAND = 0x0040
IEQUALIFIER_RCOMMAND = 0x0080

IEQUALIFIER_SHIFT = IEQUALIFIER_LSHIFT | IEQUALIFIER_RSHIFT

ALL_QUALIFIERS  = IEQUALIFIER_LSHIFT | IEQUALIFIER_RSHIFT | IEQUALIFIER_CONTROL
ALL_QUALIFIERS |= IEQUALIFIER_LALT | IEQUALIFIER_RALT | IEQUALIFIER_LCOMMAND
ALL_QUALIFIERS |= IEQUALIFIER_RCOMMAND

NM_WHEEL_UP      = 0x7a
NM_WHEEL_DOWN    = 0x7b

PRESSURE_MAX     = 0x7ffff800
ANGLE_MAX        = 4294967280.0

TABLETA_ToolType = pymui.TABLETA_Dummy + 20

class ViewPort(pymui.Rectangle, view.ViewPort):
    _MCC_ = True
    docproxy = None
    __viewFormat = 'ARGB'
    _redraw_area = None

    EVENTMAP = {
        pymui.IDCMP_MOUSEBUTTONS : 'mouse-button',
        pymui.IDCMP_MOUSEMOVE    : 'mouse-motion',
        pymui.IDCMP_RAWKEY       : 'rawkey',
        }

    @pymui.muimethod(pymui.MUIM_Setup)
    def MCC_Setup(self, msg):
        self._ev.install(self, pymui.IDCMP_RAWKEY | pymui.IDCMP_MOUSEBUTTONS)
        return msg.DoSuper()

    @pymui.muimethod(pymui.MUIM_Cleanup)
    def MCC_Cleanup(self, msg):
        self._ev.uninstall()
        return msg.DoSuper()

    @pymui.muimethod(pymui.MUIM_HandleEvent)
    def MCC_HandleEvent(self, msg):
        self._ev.readmsg(msg)
        t = self._watchers.get(ViewPort.EVENTMAP.get(self._ev.Class))
        if t: return t[0](self._ev, *t[1])

    @pymui.muimethod(pymui.MUIM_AskMinMax)
    def _mcc_AskMinMax(self, msg):
        msg.DoSuper()

        minmax = msg.MinMaxInfo.contents

        minmax.MinWidth = 100
        minmax.MinHeight = 100
        minmax.MaxWidth = pymui.MUI_MAXMAX
        minmax.MaxHeight = pymui.MUI_MAXMAX

    @pymui.muimethod(pymui.MUIM_Draw)
    def _mcc_Draw(self, msg):
        msg.DoSuper()

        if msg.flags.value & pymui.MADF_DRAWOBJECT:
            area = self._redraw_area and map(int, self._redraw_area) or (0,0,self.MWidth,self.MHeight)
            self._redraw_area = None
            
            cr = self.cairo_context
            cr.reset_clip()
            cr.identity_matrix()
            area = self.repaint(cr, self._docproxy, area, self.MWidth, self.MHeight)
            self.ClipCairoPaintArea(*area)

    def __init__(self, dv):
        super(ViewPort, self).__init__(InnerSpacing=(0,)*4,
                                       FillArea=False,
                                       DoubleBuffer=True)
        self.dv = dv
        self._docproxy = dv.docproxy
        self._ev = pymui.EventHandler()
        self._watchers = {}

        self.set_background(main.Gribouillis.DEFAULT_BACKGROUND)

    def _set_background(self, filename):
        self.Background = '5:'+filename

    def set_watcher(self, name, cb, *args):
        self._watchers[name] = (cb, args)

    def enable_mouse_motion(self, state=True):
        self._ev.uninstall()
        if state:
            idcmp = self._ev.idcmp | pymui.IDCMP_MOUSEMOVE
        else:
            idcmp = self._ev.idcmp & ~pymui.IDCMP_MOUSEMOVE
        self._ev.install(self, idcmp)

    def get_view_mouse(self, x, y):
        return x-self.MLeft, y-self.MTop

    def redraw(self, area=None, model=True, tools=True, cursor=True):
        self.set_repaint(model, tools, cursor)
        self._redraw_area = area
        self.Redraw()

    def scale_up(self, cx=.0, cy=.0):
        x, y = self.get_model_point(cx, cy)
        if view.ViewPort.scale_up(self):
            self.update_model_matrix()
            x, y = self.get_view_point(x, y)
            self.scroll(cx-x, cy-y)
            self.redraw(tools=False)

    def scale_down(self, cx=.0, cy=.0):
        x, y = self.get_model_point(cx, cy)
        if view.ViewPort.scale_down(self):
            self.update_model_matrix()
            x, y = self.get_view_point(x, y)
            self.scroll(cx-x, cy-y)
            self.redraw(tools=False)

    def scroll(self, *delta):
        view.ViewPort.scroll(self, *delta)
        self.update_model_matrix()
        self.redraw(tools=False)

    def rotate(self, dr):
        view.ViewPort.rotate(self, dr)
        self.update_model_matrix()
        self.redraw() ## redraw tools also for the rotation helper

    def reset(self):
        view.ViewPort.reset(self)
        self.update_model_matrix()
        self.redraw(tools=False)


class DocViewer(pymui.Window):

    # Pointers type from C header file 'intuition/pointerclass.h'
    POINTERTYPE_NORMAL = 0
    POINTERTYPE_DRAW   = 6
    POINTERTYPE_PICK   = 5

    _mode = 'idle'
    _qualifier = 0
    _new_states = None
    _old_states = None
    _shift = False
    _t0 = None
    _tool = None # the one who has the focus

    #### Private API ####

    def __init__(self, docproxy):
        self.title_header = 'Document: '
        super(DocViewer, self).__init__('',
                                        ID=0,       # The haitian power
                                        LeftEdge=0,
                                        TopDeltaEdge=0,
                                        WidthScreen=70,
                                        HeightScreen=90,
                                        TabletMessages=True, # enable tablet events support
                                        )

        self._watchers = {'pick': None}
        self._on_motion = idle_cb
        self.dev = InputDevice()

        self.docproxy = docproxy
        name = docproxy.docname

        self.vp = ViewPort(self)
        self.RootObject = self.vp

        self.set_doc_name(name)

        # pointer is a PyMUI r233 feature
        if 'pointer' in pymui.Window.__dict__:
            self.Notify('Activate', self.__on_activate)

        self.mode = 'idle'

    def set_watcher(self, name, cb, *args):
        self._watchers[name] = (cb, args)

    def __on_activate(self, evt):
        if evt.value:
            self.pointer = self.POINTERTYPE_DRAW
            self.vp.enable_mouse_motion(True)
        else:
            self.pointer = self.POINTERTYPE_NORMAL
            self.vp.enable_mouse_motion(False)

    def _set_mode(self, mode):
        if mode != self._mode:
            if mode.startswith('drag'):
                self._on_motion = self._drag_on_motion
            elif mode == 'draw':
                self._on_motion = self._draw_on_motion
            elif mode == 'rotation':
                self._on_motion = self._rotate_on_motion
            elif mode == 'tool-hit':
                self._on_motion = self._tool_on_motion
            else:
                self._on_motion = idle_cb
                if self.vp.draw_rot:
                    self.vp.draw_rot = False
                    self.vp.redraw() ## redraw all

                if mode == 'pick':
                    self.pointer = self.POINTERTYPE_PICK

            #self.vp.enable_mouse_motion(self._on_motion is not idle_cb)
            self._mode = mode

    def _action_start(self, evt, mode):
        self.mode = mode
        self.update_dev_state(evt)

        if mode == 'rotation':
            self.__rox, self.__roy = self.vp.get_view_point(0, 0)
            x, y = self.dev.current.vpos
            self.__angle = self.vp.compute_angle(x - self.__rox, self.__roy - y)
            self.vp.draw_rot = True
            self.vp.redraw() ## redraw all
        elif mode == 'draw':
            self.docproxy.draw_start(self.dev)

        self.mode = mode

    def _action_cancel(self, evt):
        if self.mode == 'rotation':
            del self.__angle, self.__rox, self.__roy
        elif self.mode == 'draw':
            self.docproxy.draw_end()
            self.vp.stroke_end()
        elif self.mode == 'pick':
            self.pointer = self.POINTERTYPE_NORMAL
        self.mode = 'idle'

    def _action_ok(self, evt):
        mode = self.mode
        if mode == 'draw':
            self.on_mouse_motion(evt)
            self.docproxy.draw_end()
            self.vp.stroke_end()
        elif mode == 'rotation':
            del self.__angle, self.__rox, self.__roy
        elif mode == 'scale-up':
            pos = self.vp.get_view_mouse(evt.MouseX, evt.MouseY)
            self.vp.scale_up(*pos)
        elif mode == 'scale-down':
            pos = self.vp.get_view_mouse(evt.MouseX, evt.MouseY)
            self.vp.scale_down(*pos)
        elif mode == 'pick':
            pos = self.vp.get_view_mouse(evt.MouseX, evt.MouseY)
            cb, args = self._watchers['pick']
            cb(self.vp.get_model_point(*pos), *args)
            self.pointer = self.POINTERTYPE_NORMAL

        self.mode = 'idle'

    def _drag_on_motion(self):
        delta = self.vp.compute_motion(self.dev)
        if self.mode == 'drag-view':
            self.vp.scroll(*delta)
        else:
            self.docproxy.scroll_layer(*self.vp.get_model_distance(*delta))

    def _draw_on_motion(self):
        area = self.docproxy.draw_stroke()
        if area:
            self.vp.redraw(self.vp.get_view_area(*area), tools=False, cursor=False)

    def _rotate_on_motion(self):
        x, y = self.dev.current.vpos
        a = self.vp.compute_angle(x-self.__rox, self.__roy-y)
        da = self.__angle - a
        self.__angle = a
        self.vp.rotate(da)

    def _tool_on_motion(self):
        if self.vp.tool_motion(self._tool, self.dev.current):
            self._tool = None
            self.mode = 'idle'

    #### Public API ####

    mode = property(fget=lambda self: self._mode, fset=_set_mode)

    def set_doc_name(self, name):
        self.Title = self.title_header + name

    def reset_view(self):
        self.vp.reset()

    def confirm_close(self):
        # TODO
        return True

    def update_dev_state(self, evt, t0=int(time.time())-252460800.):
        state = DeviceState()

        # Get raw device position
        state.vpos = self.vp.get_view_mouse(evt.MouseX, evt.MouseY)

        if evt.td_Tags:
            td = evt.td_Tags
            state.pressure = float(td.get(pymui.TABLETA_Pressure, PRESSURE_MAX/2)) / PRESSURE_MAX

            # Get device tilt
            state.xtilt = 2.0 * float(td.get(pymui.TABLETA_AngleX, 0)) / ANGLE_MAX - 1.0
            state.ytilt = 1.0 - 2.0 * float(td.get(pymui.TABLETA_AngleY, 0)) / ANGLE_MAX
        else:
            state.pressure = .5
            state.xtilt = state.ytilt = .0

        # timestamp
        state.time = evt.Seconds - t0 + evt.Micros*1e-6

        if self._tool and self.mode == 'draw':
            self._tool.filter(state)

        # Translate to surface coordinates (using layer offset) and record
        state.spos = self.vp.get_model_point(*state.vpos)
        self.dev.add_state(state)
        self.vp.move_cursor(*state.vpos)

    def set_cursor_radius(self, r):
        self.vp.set_cursor_radius(r)

    def toggle_line_ruler(self):
        self._tool = self.vp.toggle_line_ruler()

    def toggle_ellipse_ruler(self):
        self._tool = self.vp.toggle_ellipse_ruler()

    def on_mouse_button(self, evt):
        rawkey = evt.RawKey
        if self._mode == 'idle':
            if not evt.InObject: return
            if rawkey == IECODE_LBUTTON:
                if not evt.Up:
                    self.update_dev_state(evt)
                    tool = self.vp.tool_hit(self.dev.current)
                    if tool:
                        self._tool = tool
                        self._action_start(evt, 'tool-hit')
                    else:
                        self._action_start(evt, 'draw')
                    return pymui.MUI_EventHandlerRC_Eat
            elif rawkey == IECODE_MBUTTON:
                if not evt.Up:
                    q = self._qualifier
                    if q & IEQUALIFIER_CONTROL:
                        self._action_start(evt, 'rotation')
                    elif q & (IEQUALIFIER_LSHIFT|IEQUALIFIER_RSHIFT):
                        self._action_start(evt, 'drag-layer')
                    else:
                        self._action_start(evt, 'drag-view')
                    return pymui.MUI_EventHandlerRC_Eat
        elif self._mode == 'draw':
            if rawkey == IECODE_LBUTTON:
                if evt.Up:
                    self._action_ok(evt)
                    return pymui.MUI_EventHandlerRC_Eat
        elif self._mode.startswith('drag-'):
            if rawkey == IECODE_MBUTTON:
                if evt.Up:
                    self._action_ok(evt)
                    return pymui.MUI_EventHandlerRC_Eat
            elif rawkey == IECODE_RBUTTON:
                if not evt.Up:
                    self._action_cancel(evt)
                    return pymui.MUI_EventHandlerRC_Eat
        elif self._mode == 'pick':
            if rawkey == IECODE_LBUTTON:
                if evt.Up:
                    self._action_ok(evt)
                    return pymui.MUI_EventHandlerRC_Eat
            elif rawkey == IECODE_RBUTTON:
                if evt.Up:
                    self._action_cancel(evt)
                    return pymui.MUI_EventHandlerRC_Eat
        elif self._mode == 'rotation':
            if rawkey == IECODE_MBUTTON:
                if evt.Up:
                    self._action_ok(evt)
                    return pymui.MUI_EventHandlerRC_Eat
            elif rawkey == IECODE_RBUTTON:
                if not evt.Up:
                    self._action_cancel(evt)
                    return pymui.MUI_EventHandlerRC_Eat
        elif self._mode == 'tool-hit':
            if rawkey == IECODE_LBUTTON:
                if evt.Up:
                    self._action_ok(evt)
                    return pymui.MUI_EventHandlerRC_Eat

    def on_mouse_motion(self, evt):
        # Constrained mode?
        self._shift = bool(evt.Qualifier & IEQUALIFIER_SHIFT)

        # Transform device dependent data into independent data
        self.update_dev_state(evt)

        # Call the mode dependent motion callback
        self._on_motion()

    def on_key(self, evt, docproxy):
        self._qualifier = evt.Qualifier & ALL_QUALIFIERS
        if evt.InObject and self.mode == 'idle':
            key = evt.Key or evt.RawKey
            if evt.Up:
                if key == '+':
                    docproxy.add_brush_radius(3)
                    self.vp.redraw(model=False, tools=False)
                    return pymui.MUI_EventHandlerRC_Eat
                elif key == '-':
                    docproxy.add_brush_radius(-3)
                    self.vp.redraw(model=False, tools=False)
                    return pymui.MUI_EventHandlerRC_Eat
                elif key == 'p':
                    self.mode = 'pick'
                    return pymui.MUI_EventHandlerRC_Eat
            else:
                if key == NM_WHEEL_UP:
                    self.mode = 'scale-up'
                    self._action_ok(evt)
                    return pymui.MUI_EventHandlerRC_Eat
                elif key == NM_WHEEL_DOWN:
                    self.mode = 'scale-down'
                    self._action_ok(evt)
                    return pymui.MUI_EventHandlerRC_Eat


class DocumentMediator(Mediator):
    NAME = "DocumentMediator"

    __docproxy = None

    #### Private API ####

    def __init__(self, component):
        assert isinstance(component, Application)
        super(DocumentMediator, self).__init__(viewComponent=component)

        self.__doc_proxies = {}

    def __create_viewer(self, docproxy):
        dv = DocViewer(docproxy)
        self.viewComponent.AddChild(dv)

        dv.Notify('CloseRequest', lambda e: self._safe_close_viewer(e.Source), when=True)
        dv.Notify('Activate', self._on_activate, when=True)

        # Inputs comes from the ViewPort
        dv.vp.set_watcher('mouse-button', dv.on_mouse_button)
        dv.vp.set_watcher('mouse-motion', dv.on_mouse_motion)
        dv.vp.set_watcher('rawkey', dv.on_key, docproxy)
        dv.set_watcher('pick', self._on_color_pick, dv, docproxy)

        dv.Open = True

        self.__doc_proxies[dv] = docproxy

        return dv

    def __len__(self):
        return len(self.__doc_proxies)

    def _get_viewer(self, docproxy):
        for dv, proxy in self.__doc_proxies.iteritems():
            if proxy == docproxy:
                return dv

    def _safe_close_viewer(self, dv):
        docproxy = self.__doc_proxies[dv]
        if not docproxy.document.empty and not dv.confirm_close():
            return
        self.sendNotification(main.Gribouillis.DOC_DELETE, docproxy)

    def _on_color_pick(self, pos, dv, docproxy):
        #color = docproxy.read_pixel_rgb(pos)
        for layer in docproxy.iter_visible_layers():
            color = layer.surface.read_pixel(*pos)
            if color:
                docproxy.set_brush_color_rgb(*color)
                return

    ### UI events handlers ###

    def _on_activate(self, evt):
        self.sendNotification(main.Gribouillis.DOC_ACTIVATE, self.__doc_proxies[evt.Source])

    ### notification handlers ###

    @mvcHandler(main.Gribouillis.NEW_DOCUMENT_RESULT)
    def _on_new_document_result(self, docproxy):
        if not docproxy:
            self.sendNotification(main.Gribouillis.SHOW_ERROR_DIALOG,
                                  "Failed to create document.")
            return

        self.__create_viewer(docproxy)

    @mvcHandler(main.Gribouillis.DOC_SAVE_RESULT)
    def _on_save_document_result(self, docproxy, result):
        dv = self._get_viewer(docproxy)
        dv.set_doc_name(docproxy.document.name)

    @mvcHandler(main.Gribouillis.DOC_ACTIVATED)
    def _on_activate_document(self, docproxy):
        dv = self._get_viewer(docproxy)
        if dv is None:
            # Act as NEW_DOCUMENT_RESULT command
            dv = self.__create_viewer(docproxy)
        else:
            if not dv.Activate:
                dv.NNSet('Activate', True)
            dv.ToFront()
            
    @mvcHandler(main.Gribouillis.DOC_LAYER_ADDED)
    def _on_doc_layer_added(self, docproxy, layer, *args):
        dv = self._get_viewer(docproxy)
        dv.vp.update_model_matrix(layer.x, layer.y)
        if not layer.empty:
            dv.vp.redraw(tools=False)
            
    @mvcHandler(main.Gribouillis.DOC_LAYER_MOVED)
    @mvcHandler(main.Gribouillis.DOC_LAYER_UPDATED)
    @mvcHandler(main.Gribouillis.DOC_LAYER_DELETED)
    @mvcHandler(main.Gribouillis.DOC_UPDATED)
    def _on_doc_layer_updated(self, docproxy, layer=None, *args):
        dv = self._get_viewer(docproxy)
        if layer is None:
            layer = docproxy.active_layer
        dv.vp.update_model_matrix(layer.x, layer.y)
        dv.vp.redraw(tools=False)
        
    @mvcHandler(main.Gribouillis.DOC_LAYER_ACTIVATED)
    def _on_doc_layer_activate(self, docproxy, layer):
        dv = self._get_viewer(docproxy)
        dv.vp.update_model_matrix(layer.x, layer.y)

    @mvcHandler(main.Gribouillis.BRUSH_PROP_CHANGED)
    def _on_doc_brush_prop_changed(self, brush, name):
        if name is 'color': return
        for docproxy in self.__doc_proxies.itervalues():
            if docproxy.brush is brush:
                setattr(docproxy.document.brush, name, getattr(brush, name))

    #### Public API ####

    def delete_docproxy(self, docproxy):
        dv = self._get_viewer(docproxy)
        del self.__doc_proxies[dv]
        dv.Open = False
        self.viewComponent.RemChild(dv)

    def load_background(self):
        docproxy = model.DocumentProxy.get_active()
        dv = self._get_viewer(docproxy)
        filename = self.viewComponent.get_image_filename(parent=dv, pat='#?.png')
        if filename:
            try:
                dv.vp.set_background(filename)
            except:
                self.sendNotification(main.Gribouillis.SHOW_ERROR_DIALOG,
                                      "Failed to load background image %s.\n" % filename +
                                      "(Note: Only PNG files are supported as background).")
            else:
                dv.vp.redraw(tools=False)

    def reset_view(self):
        docproxy = model.DocumentProxy.get_active()
        dv = self._get_viewer(docproxy)
        dv.reset_view()

    def load_image_as_layer(self):
        docproxy = model.DocumentProxy.get_active()
        dv = self._get_viewer(docproxy)
        filename = self.viewComponent.get_image_filename(parent=dv)
        if filename:
            self.sendNotification(main.Gribouillis.DOC_LOAD_IMAGE_AS_LAYER,
                                  model.vo.LayerConfigVO(docproxy=docproxy, filename=filename),
                                  type=RECORDABLE_COMMAND)

    def set_background_rgb(self, rgb):
        dv = self._get_viewer(model.DocumentProxy.get_active())
        dv.vp.set_background_rgb(rgb)
        dv.vp.redraw()

    def toggle_line_guide(self):
        dv = self._get_viewer(model.DocumentProxy.get_active())
        dv.toggle_line_ruler()
        
    def toggle_ellipse_guide(self):
        dv = self._get_viewer(model.DocumentProxy.get_active())
        dv.toggle_ellipse_ruler()
