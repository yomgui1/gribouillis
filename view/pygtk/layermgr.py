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

import model

from gi.repository import Gtk as gtk
from gi.repository import Gdk as gdk
from gi.repository import GdkPixbuf
from gi.repository import GObject as gobject

from .common import SubWindow

__all__ = [ 'LayerManager', 'LayerCtrl' ]

def _new_signal(name):
    return gobject.signal_new(name, gtk.Object,
                              gobject.SIGNAL_ACTION,
                              gobject.TYPE_BOOLEAN, (gobject.TYPE_PYOBJECT, ))

sig_layer_active = _new_signal('layer-active-event')
sig_layer_name = _new_signal('layer-name-changed')
sig_layer_visibility = _new_signal('layer-visibility-event')
sig_layer_operator = _new_signal('layer-operator-event')

def ask_for_name(widget, title, default):
    window = widget.get_toplevel()
    d = gtk.Dialog(title,
                   window,
                   gtk.DIALOG_MODAL,
                   (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                    gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))

    hbox = gtk.HBox()
    d.vbox.pack_start(hbox)
    hbox.pack_start(gtk.Label('Name'))

    d.e = e = gtk.Entry()
    e.set_text(default)
    e.select_region(0, len(default))
    def responseToDialog(entry, dialog, response):
        dialog.response(response)
    e.connect("activate", responseToDialog, d, gtk.RESPONSE_ACCEPT)

    hbox.pack_start(e)
    d.vbox.show_all()
    if d.run() == gtk.RESPONSE_ACCEPT:
        result = d.e.get_text()
    else:
        result = None
    d.destroy()
    return result


class EyeArea(gtk.DrawingArea):
    def __init__(self, size=20):
        super(EyeArea, self).__init__()

        self._active = 0
        self.eye_img = [ gdk.pixbuf_new_from_file('data/icons/edit.png'),
                         gdk.pixbuf_new_from_file('data/icons/edit.png') ]

        self.set_size_request(self.eye_img[0].get_width(), self.eye_img[0].get_height())

        self.connect('expose-event', self.draw)

    def set_active(self, v):
        self._active = int(v)
        self.queue_draw()

    def get_active(self):
        return self._active

    def draw(self, w, e):
        pb = self.eye_img[self._active]
        self.window.draw_pixbuf(self.window.new_gc(), pb, 0, 0, 0, 0)

    active = property(fget=get_active, fset=set_active)


class EyeButton(gtk.ToggleButton):
    def __init__(self, active=True):
        super(EyeButton, self).__init__()
        self.eye = EyeArea()
        self.eye.set_active(active)
        self.set_active(active)
        self.add(self.eye)
        self.connect('toggled', self.on_toggled)

    def on_toggled(self, w):
        self.eye.active = not self.eye.active


class LayerCtrl(gtk.EventBox):
    def __init__(self, layer):
        super(LayerCtrl, self).__init__()
        self.set_border_width(2)

        self.layer = layer

        # Display widget
        self.disp = EyeButton(layer.visible)
        self.disp.connect('toggled', self._on_disp_toggled)

        # Layer operator
        self.operator = gtk.combo_box_new_text()
        ope = model.Layer.OPERATORS_LIST
        for name in ope:
            self.operator.append_text(name)
        self.operator.set_active(ope.index(layer.operator))
        self.operator.connect('changed', lambda *a: self.get_toplevel().emit('layer-operator-event', self))

        # Name widget
        self.label = gtk.Label()
        self.label.set_text(layer.name)
        self.label.set_selectable(True)

        # Pack them all
        self.topbox = gtk.HBox()
        self.topbox.pack_start(self.disp, expand=False)
        self.topbox.pack_start(self.operator, expand=False)
        self.topbox.pack_start(self.label)
        self.add(self.topbox)

        self.show_all()

    def _on_disp_toggled(self, w):
        self.get_toplevel().emit('layer-visibility-event', (self.layer, w.get_active()))

    def set_active(self, v):
        style = self.get_style()
        color = (style.bg[gtk.STATE_SELECTED] if v else None)
        def mark(w):
            w.modify_bg(gtk.STATE_NORMAL, color)
            if isinstance(w, gtk.Box):
                w.foreach(mark)
        mark(self)
        self.topbox.foreach(mark)

    def update(self):
        self.disp.set_active(self.layer.visible)
        self.label.set_text(self.layer.name)

    def change_name(self):
        oldname = self.label.get_text()
        name = ask_for_name(self, "Change Layer Name", oldname)
        if name:
            if name == oldname: return
            self.label.set_text(name)
        return name


class LayerManager(SubWindow):
    """
    Frame window to display as a list all layers of a document.

    This frame is unique for the application (singleton).
    So each time a document obtains the focus this frame is updated
    for this document's layer list.

    The layer
    """

    def __init__(self):
        super(LayerManager, self).__init__()

        self._active = None

        topbox = gtk.VBox()

        # Layers virtual window
        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        self.layers_container = gtk.VBox()
        scroll.add_with_viewport(self.layers_container)

        # Control buttons box
        btnbox = gtk.HBox()
        self.btnbox = btnbox

        # Button binding made by the ApplicationMediator class
        def addButton(name, stock):
            bt = self.btn[name] = gtk.Button()
            im = gtk.Image()
            im.set_from_stock(stock, gtk.ICON_SIZE_BUTTON)
            bt.set_image(im)
            btnbox.pack_start(bt)

        self.btn = {}

        addButton('add',  gtk.STOCK_ADD)
        addButton('del',  gtk.STOCK_DELETE)
        addButton('top',  gtk.STOCK_GOTO_TOP)
        addButton('up',   gtk.STOCK_GO_UP)
        addButton('down', gtk.STOCK_GO_DOWN)
        addButton('bot',  gtk.STOCK_GOTO_BOTTOM)
        addButton('dup',  gtk.STOCK_COPY)
        addButton('merge',  gtk.STOCK_CONVERT)

        # Packing all
        topbox.pack_start(scroll)
        topbox.pack_start(btnbox, expand=False)
        self.add(topbox)
        topbox.show_all()

        self.set_title('Layers')

    def __len__(self):
        return len(self.layers_container.get_children())

    def _set_active_ctrl(self, ctrl):
        if ctrl is self._active: return
        ctrl.set_active(True)
        if self._active:
            self._active.set_active(False)
        self._active = ctrl
        self.emit('layer-active-event', ctrl.layer)

    def on_ctrl_label_press(self, label, evt):
        ctrl = label.parent.parent
        if evt.type == gdk.BUTTON_PRESS:
            self._set_active_ctrl(ctrl)
        elif evt.type == gdk._2BUTTON_PRESS:
            name = label.parent.parent.change_name()
            if name:
                self.emit('layer-name-changed', (ctrl.layer, name))

    def clear(self):
        self.layers_container.foreach(self.remove_child)

    def remove_child(self, child):
        self.layers_container.remove(child)
        child.destroy()

    def add_layer_ctrl(self, layer, pos=0):
        ctrl = LayerCtrl(layer)
        ctrl.label.connect('button-press-event', self.on_ctrl_label_press)
        self.layers_container.pack_start(ctrl, expand=False)
        self.layers_container.reorder_child(ctrl, len(self)-pos-1)

    def set_layers(self, layers, active=None):
        self.clear()
        for layer in layers:
            ctrl = self.add_layer_ctrl(layer)
        self.active = active

    def add_layer(self, layer, pos):
        ctrl = self.add_layer_ctrl(layer, pos)
        self.active = layer
        return ctrl
        
    def del_layer(self, layer):
        for ctrl in self.layers_container.get_children():
            if ctrl.layer is layer:
                self.layers_container.remove(ctrl)
                self.active = layer
                return

    def update_layer(self, layer):
        for ctrl in self.layers_container.get_children():
            if ctrl.layer is layer:
                ctrl.update()
                return

    def move_layer(self, layer, pos):
        for ctrl in self.layers_container.get_children():
            if ctrl.layer is layer:
                self.layers_container.reorder_child(ctrl, len(self)-pos-1)
                return

    def get_active_position(self):
        children = self.layers_container.get_children()
        return len(children) - children.index(self._active) - 1

    def get_active(self):
        return self._active.layer

    def set_active(self, layer):
        for ctrl in self.layers_container.get_children():
            if (not layer) or (ctrl.layer is layer):
                self._set_active_ctrl(ctrl)
                return

    active = property(fget=get_active, fset=set_active)


