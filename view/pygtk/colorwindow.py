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
import gtk.gdk as gdk

import main, model, utils, view

from utils import mvcHandler
from .common import SubWindow

__all__ = ['ColorWindow', 'ColorWindowMediator']

class ColorWindow(SubWindow):
    def __init__(self):
        super(ColorWindow, self).__init__()

        top = gtk.VBox()
        self.add(top)

        self.colorsel = gtk.ColorSelection()
        top.pack_start(self.colorsel)

        top.show_all()

    def set_color_rgb(self, rgb):
        color = gdk.Color()
        color.red_float = rgb[0]
        color.green_float = rgb[1]
        color.blue_float = rgb[2]
        self.colorsel.set_current_color(color)


class ColorWindowMediator(utils.Mediator):
    NAME = "ColorWindowMediator"

    #### Private API ####

    def __init__(self, component):
        assert isinstance(component, ColorWindow)
        super(ColorWindowMediator, self).__init__(ColorWindowMediator.NAME, component)

        component.colorsel.connect('color-changed', self._on_color_changed)

    def _on_color_changed(self, widget):
        color = widget.get_current_color()
        model.DocumentProxy.get_active().set_brush_color_rgb(color.red_float, color.green_float, color.blue_float)

    ### notification handlers ###

    @mvcHandler(main.Gribouillis.DOC_ACTIVATE)
    def _on_activate_document(self, docproxy):
        brush = docproxy.document.brush
        self.viewComponent.set_color_rgb(brush.rgb)
