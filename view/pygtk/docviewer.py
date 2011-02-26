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

import gtk
import gobject
import cairo

from gtk import gdk

import model, view, main, utils

from model.devices import *
from utils import Mediator, mvcHandler, idle_cb
from .app import Application

__all__ = [ 'DocViewer', 'DocumentMediator' ]

def _menu_signal(name):
    return gobject.signal_new(name, gtk.Window,
                              gobject.SIGNAL_ACTION,
                              gobject.TYPE_BOOLEAN, ())

# signal used to communicate between viewer's menu and document mediator
sig_menu_quit    = _menu_signal('menu_quit')
sig_menu_new_doc = _menu_signal('menu_new_doc')
sig_menu_load_doc = _menu_signal('menu_load_doc')
sig_menu_save_doc = _menu_signal('menu_save_doc')
sig_menu_close_doc = _menu_signal('menu_close_doc')
sig_menu_clear_layer = _menu_signal('menu_clear_layer')
sig_menu_undo = _menu_signal('menu_undo')
sig_menu_redo = _menu_signal('menu_redo')
sig_menu_redo = _menu_signal('menu_flush')
sig_menu_load_background = _menu_signal('menu_load_background')
sig_menu_load_image_as_layer = _menu_signal('menu_load_image_as_layer')


class Viewport(gtk.DrawingArea, view.ViewPort):
    """Viewport class.

    This class is responsible to display a surface (model) instance to user.
    It owns and handles display properties like affine transformations,
    background, and so on.
    """

    def __init__(self, dv):
        super(Viewport, self).__init__()
        self.dv = dv

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

        self.set_background(main.Gribouillis.DEFAULT_BACKGROUND)

    def _set_background(self, filename):
        pixbuf = gdk.pixbuf_new_from_file(filename)
        pixmap, mask = pixbuf.render_pixmap_and_mask()
        self.window.set_back_pixmap(pixmap, False)

    def on_expose(self, widget, evt, docproxy):
        cr = widget.window.cairo_create()
        self.repaint(cr, docproxy, evt.area, self.allocation.width, self.allocation.height)
        return True

    def redraw(self, area=None, model=True, tools=True, cursor=True):
        self.set_repaint(model, tools, cursor)
        if area:
            self.queue_draw_area(*map(int, area))
        else:
            self.queue_draw()

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


class DocViewer(gtk.Window):
    #### Private API ####

    __mode = None
    __bad_devices = []
    __title_fmt = "Document: %s"
    _shift = False
    _t0 = None
    _tool = None  # the one who has the focus

    KEY_INC_BRUSH_RADIUS = '+'
    KEY_DEC_BRUSH_RADIUS = '-'

    def __init__(self, docproxy):
        super(DocViewer, self).__init__()

        self.docproxy = docproxy
        self.dev = InputDevice()
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

        topbox = gtk.VBox(False, 1)
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
            ('view-reset', None, 'Reset', '<Control>equal', None, lambda *a: self.reset_view()),
            ('view-load-background', None, 'Load background image', '<Control><Alt>b', None, lambda *a: self.emit('menu_load_background')),
            ('color-win', gtk.STOCK_PROPERTIES, 'Open color editor', '<Control>c', None, lambda *a: Application().open_colorwin()),
            ('brush-house-win', None, 'Open brush house window', None, None, lambda *a: Application().open_brush_house()),
            ('brush-win', gtk.STOCK_PROPERTIES, 'Edit brush properties', '<Control>b', None, lambda *a: Application().open_brush_editor()),
            ('brush-radius-inc', gtk.STOCK_ADD, 'Increase brush size', 'plus', None, lambda *a: self.increase_brush_radius()),
            ('brush-radius-dec', gtk.STOCK_REMOVE, 'Decrease brush size', 'minus', None, lambda *a: self.decrease_brush_radius()),
            ('line-ruler-toggle', None, 'Toggle line ruler', None, None, lambda a: self._toggle_line_ruler()),
            ('ellipse-ruler-toggle', None, 'Toggle ellipse ruler', None, None, lambda a: self._toggle_ellipse_ruler()),
            ('navigator-toggle', None, 'Toggle Navigator', None, None, lambda a: self._toggle_navigator()),
            #('', None, '', None, None, lambda *a: self.emit('')),
            ])

        #actiongroup.add_toggle_actions([
        #    ])

        uimanager.insert_action_group(actiongroup, 0)

        # MenuBar
        menubar = uimanager.get_widget('/MenuBar')
        topbox.pack_start(menubar, False)

        # Viewport
        self.vp = Viewport(self)
        topbox.pack_start(self.vp, True, True, 0)

        self.set_default_size(600, 400)
        self.move(0,0)
        self.show_all()

        # Set defaults
        self.set_doc_name(docproxy.document.name)
        self.mode = 'idle'

    def _set_mode(self, mode):
        if mode != self.__mode:
            if mode == 'drag':
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

            self.__mode = mode

    def _action_start(self, evt, mode):
        self.mode = mode
        self.update_dev_state(evt)
        
        if mode == 'rotation':
            state = self.dev.current
            x, y = state.vpos
            self.__rox, self.__roy = self.vp.get_view_point(0, 0)
            self.__angle = self.vp.compute_angle(x-self.__rox, self.__roy-y)
            self.vp.draw_rot = True
            self.vp.redraw() ## redraw all
        elif mode == 'draw':
            self.docproxy.draw_start(self.dev)

    def _action_cancel(self, evt):
        if self.mode == 'rotation':
            del self.__angle, self.__rox, self.__roy
        elif self.mode == 'draw':
            self.docproxy.draw_end()
            self.vp.stroke_end()

        self.mode = 'idle'

    def _action_ok(self, evt):
        mode = self.mode
        if mode == 'rotation':
            del self.__angle, self.__rox, self.__roy
        elif mode == 'scroll':
            if evt.direction == gdk.SCROLL_UP:
                self.vp.scale_up(evt.x, evt.y)
            else:
                self.vp.scale_down(evt.x, evt.y)
        elif mode == 'draw':
            area = self.on_motion_notify(self.vp, evt)
            self.docproxy.draw_end()
            self.vp.stroke_end()
            if area: self.vp.redraw(self.get_view_area(*area), model=True, tools=True)

        self.mode = 'idle'

    def _drag_on_motion(self):
        self.vp.scroll(*self.vp.compute_motion(self.dev))

    def _draw_on_motion(self):
        area = self.docproxy.draw_stroke()
        if area:
            self.vp.redraw(self.vp.get_view_area(*area), tools=False, cursor=False)

    def _rotate_on_motion(self):
        state = self.dev.current
        x, y = state.vpos
        a = self.vp.compute_angle(x-self.__rox, self.__roy-y)
        da = self.__angle - a
        self.__angle = a
        self.vp.rotate(da)

    def _tool_on_motion(self):
        if self.vp.tool_motion(self._tool, self.dev.current):
            self._tool = None
            self.mode = 'idle'

    def _toggle_line_ruler(self):
        self._tool = self.vp.toggle_line_ruler()

    def _toggle_ellipse_ruler(self):
        self._tool = self.vp.toggle_ellipse_ruler()

    def _toggle_navigator(self):
        self.vp.toggle_navigator()

    #### Public API ####

    mode = property(fget=lambda self: self.__mode, fset=_set_mode)

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

    def get_pressure(self, evt):
        # Is pressure value not in supposed range?
        # Note: this code has been taken from MyPaint.
        p = evt.get_axis(gdk.AXIS_PRESSURE)
        if p is not None:
            if p < 0. or p > 1.:
                if evt.device.name not in self.__bad_devices:
                    print 'WARNING: device "%s" is reporting bad pressure %+f' % (evt.device.name, p)
                    self.__bad_devices.append(evt.device.name)
                if p < -10000. or p > 10000.:
                    # https://gna.org/bugs/?14709
                    return .5
        else:
            return .5
        return p

    def update_dev_state(self, evt):
        if self._t0 is None:
            self._t0 = evt.time
            
        state = DeviceState()

        # Get raw device position and pressure
        state.vpos = int(evt.get_axis(gdk.AXIS_X)), int(evt.get_axis(gdk.AXIS_Y))
        state.pressure = self.get_pressure(evt)

        # Get device tilt
        state.xtilt = evt.get_axis(gdk.AXIS_XTILT) or 0.
        state.ytilt = evt.get_axis(gdk.AXIS_YTILT) or 0.

        # timestamp
        state.time = evt.time * 1e-3 # GDK timestamp in milliseconds
        
        # Tools can modify this position
        if self._tool and self.mode == 'draw':
            self._tool.filter(state)

        # Translate to surface coordinates
        state.spos = self.vp.get_model_point(*state.vpos)
        
        self.dev.add_state(state) # add + filter

    def on_button_press(self, widget, evt):
        # ignore double-click events
        if evt.type != gdk.BUTTON_PRESS:
            return

        self.update_dev_state(evt)

        mode = self.mode
        bt = evt.button
        if mode == 'idle':
            if bt == 1:
                tool = self.vp.tool_hit(self.dev.current)
                if tool:
                    self._tool = tool
                    self._action_start(evt, 'tool-hit')
                else:
                    self._action_start(evt, 'draw')
                return True
            elif bt == 2:
                if evt.state & gdk.CONTROL_MASK:
                    self._action_start(evt, 'rotation')
                else:
                    self._action_start(evt, 'drag')
                return True
        elif mode == 'draw':
            if bt == 1:
                self._action_ok(evt)
                return True
        elif mode == 'drag':
            if bt == 2:
                self._action_ok(evt)
                return True
            elif bt == 3:
                self._action_cancel(evt)
                return True
        elif mode == 'pick':
            if bt == 1:
                self._action_ok(evt)
                return True
            elif bt == 3:
                self._action_cancel(evt)
                return True
        elif mode == 'rotation':
            self._action_ok(evt)
            return True

    def on_motion_notify(self, vp, evt):
        # Constrained mode?
        self._shift = bool(evt.state & gdk.SHIFT_MASK)

        # Transform device dependent data into independent data
        self.update_dev_state(evt)

        self.vp.draw_cursor()

        # Call the mode dependent motion callback
        return self._on_motion()

    def on_button_release(self, vp, evt):
        if evt.type != gdk.BUTTON_RELEASE:
            return

        self.update_dev_state(evt)

        mode = self.mode
        if mode == 'draw':
            bt = evt.button
            if bt == 1:
                self._action_ok(evt)
                return True

        self._action_cancel(evt)
        return True

    def on_scroll(self, vp, evt):
        if self.mode == 'idle':
            self.mode = 'scroll'
            self._action_ok(evt)
        return True

    def on_key_press(self, widget, evt, docproxy):
        if evt.string == DocViewer.KEY_INC_BRUSH_RADIUS:
            docproxy.add_brush_radius(1)
            self.vp.draw_cursor()
            return True
        elif evt.string == DocViewer.KEY_DEC_BRUSH_RADIUS:
            docproxy.add_brush_radius(-1)
            self.vp.draw_cursor()
            return True

    def increase_brush_radius(self, delta=1):
        self.docproxy.add_brush_radius(delta)
        self.vp.draw_cursor()

    def decrease_brush_radius(self, delta=-1):
        self.docproxy.add_brush_radius(delta)
        self.vp.draw_cursor()

    def reset_view(self):
        self.vp.reset()

    def load_background(self, evt=None):
        filename = Application().get_image_filename(parent=self)
        if filename:
            self.vp.set_background(filename)


class DocumentMediator(Mediator):
    """
    This class creates one instance for the application.
    This instance handles creation/destruction of document viewer components.
    This instance connects events from these components to its methods
    in a way to do actions on the model/controller.
    """

    NAME = "DocumentMediator"

    #### Private API ####

    def __init__(self, component):
        assert isinstance(component, Application)
        super(DocumentMediator, self).__init__(viewComponent=component)

        # Couple each created doc viewer to a doc proxy.
        # Note: DV instances don't handle directly proxy/model references.
        # That's why we keep the couple here, in the mediator.
        self.__doc_proxies = {}
        self.__focused = None
        self._debug = True

    def _create_viewer(self, docproxy):
        dv = DocViewer(docproxy)

        dv.connect("delete-event", lambda dv, e: self._safe_close_viewer(dv))
        dv.connect("focus-in-event", self._on_focus_in_event)
        dv.connect("menu_quit", self._on_menu_quit)
        dv.connect("menu_new_doc", self._on_menu_new_doc)
        dv.connect("menu_load_doc", self._on_menu_load_doc)
        dv.connect("menu_close_doc", self._on_menu_close_doc)
        dv.connect("menu_save_doc", self._on_menu_save_doc)
        dv.connect("menu_undo", self._on_menu_undo)
        dv.connect("menu_redo", self._on_menu_redo)
        dv.connect("menu_flush", self._on_menu_flush)
        dv.connect("menu_clear_layer", self._on_menu_clear_layer)
        dv.connect("menu_load_image_as_layer", self._on_menu_load_image_as_layer)
        dv.connect("key-press-event", dv.on_key_press, docproxy)

        vp = dv.vp
        vp.connect("expose-event", vp.on_expose, docproxy)
        vp.connect("motion-notify-event", dv.on_motion_notify)
        vp.connect("button-press-event", dv.on_button_press)
        vp.connect("button-release-event", dv.on_button_release)
        vp.connect("scroll-event", dv.on_scroll)

        self.__doc_proxies[dv] = docproxy

    def __len__(self):
        return len(self.__doc_proxies)

    def _get_viewer(self, docproxy):
        for dv, proxy in self.__doc_proxies.iteritems():
            if proxy == docproxy:
                return dv

    def _safe_close_viewer(self, dv):
        docproxy = self.__doc_proxies[dv]
        #if not docproxy.document.empty and not dv.confirm_close():
        #    return True
        self.sendNotification(main.Gribouillis.DOC_DELETE, docproxy)

    ### UI events handlers ###

    def _on_focus_in_event(self, dv, evt):
        self.__focused = dv
        self.sendNotification(main.Gribouillis.DOC_ACTIVATE, self.__doc_proxies[dv])

    def _on_delete_event(self, dv, evt):
        self.sendNotification(main.Gribouillis.DOC_DELETE, self.__doc_proxies[dv])

    def _on_menu_close_doc(self, dv):
        self.sendNotification(main.Gribouillis.DOC_DELETE, self.__doc_proxies[dv])

    def _on_menu_quit(self, dv):
        self.sendNotification(main.Gribouillis.QUIT)

    def _on_menu_new_doc(self, dv):
        vo = model.vo.EmptyDocumentConfigVO('New document')
        if self.viewComponent.get_new_document_type(vo, parent=dv):
            self.sendNotification(main.Gribouillis.NEW_DOCUMENT, vo)

    def _on_menu_load_doc(self, dv):
        filename = self.viewComponent.get_document_filename(parent=dv)
        if filename:
            vo = model.vo.FileDocumentConfigVO(filename)
            self.sendNotification(main.Gribouillis.NEW_DOCUMENT, vo)

    def _on_menu_save_doc(self, dv):
        docproxy = self.__doc_proxies[dv]
        filename = self.viewComponent.get_document_filename(parent=dv, read=False)
        if filename:
            self.sendNotification(main.Gribouillis.DOC_SAVE, (docproxy, filename))
            dv.set_doc_name(docproxy.document.name)

    def _on_menu_clear_layer(self, dv):
        docproxy = self.__doc_proxies[dv]
        self.sendNotification(main.Gribouillis.DOC_LAYER_CLEAR,
                              model.vo.LayerCommandVO(docproxy, docproxy.active_layer),
                              type=utils.RECORDABLE_COMMAND)

    def _on_menu_undo(self, *a):
        self.sendNotification(main.Gribouillis.UNDO)

    def _on_menu_redo(self, *a):
        self.sendNotification(main.Gribouillis.REDO)

    def _on_menu_flush(self, *a):
        self.sendNotification(main.Gribouillis.FLUSH)

    def _on_menu_load_image_as_layer(self, *a):
        self.load_image_as_layer()

    ### notification handlers ###

    @mvcHandler(main.Gribouillis.NEW_DOCUMENT_RESULT)
    def _on_new_document_result(self, docproxy):
        if docproxy:
            self._create_viewer(docproxy)
        else:
            self.sendNotification(main.Gribouillis.SHOW_ERROR_DIALOG,
                                  "Failed to create document.")

    @mvcHandler(main.Gribouillis.DOC_SAVE_RESULT)
    def _on_save_document_result(self, *args):
        pass

    @mvcHandler(main.Gribouillis.DOC_ACTIVATED)
    def _on_activate_document(self, docproxy):
        dv = self._get_viewer(docproxy)
        if dv is None:
            # Act as NEW_DOCUMENT_RESULT command
            self._create_viewer(docproxy)
            return

        if dv is not self.__focused:
            dv.present()
            #Application().brusheditor.set_transient_for(dv)

    #@mvcHandler(main.Gribouillis.LAYER_CREATED)
    #def _on_layer_created(self, layer):
    #    # set a default cairo compositing operator
    #    layer.operator = cairo.OPERATOR_OVER

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
    def _on_brush_prop_changed(self, brush, name):
        if name is 'color': return
        for docproxy in self.__doc_proxies.itervalues():
            if docproxy.brush is brush:
                setattr(docproxy.document.brush, name, getattr(brush, name))

    #### Public API ####

    def delete_docproxy(self, docproxy):
        dv = self._get_viewer(docproxy)
        del self.__doc_proxies[dv]
        dv.destroy()

    def load_image_as_layer(self):
        docproxy = model.DocumentProxy.get_active()
        dv = self._get_viewer(docproxy)
        filename = self.viewComponent.get_image_filename(parent=dv)
        if filename:
            self.sendNotification(main.Gribouillis.DOC_LOAD_IMAGE_AS_LAYER,
                                  model.vo.LayerConfigVO(docproxy=docproxy, filename=filename),
                                  type=utils.RECORDABLE_COMMAND)
