###############################################################################
# Copyright (c) 2009 Guillaume Roguez
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

from __future__ import with_statement
import os, sys

import pymui
from pymui import *
from brush import Brush
from DrawWindow import DrawWindow, DrawControler
from ColorChooser import ColorChooser
from BrushSelect import BrushSelect
from BGSelect import MiniBackgroundSelect
from layers import LayerModel

class Gribouillis(Application):
    VERSION = 0.1
    DATE    = "05/09/2009"

    def __init__(self, datapath, userpath=None):
        if userpath is None:
            userpath = datapath

        self.paths = dict(data=datapath, user=userpath) 
        self.last_loaded_dir = None

        # Create Windows
        self.win_Color = ColorChooser("Color Selection")
        self.win_BSel = BrushSelect("Brush Selection")
        self.win_MiniBGSel = MiniBackgroundSelect()

        # Create Menus
        menu_def = { 'Project': (('Load Image...', 'L', self.OnLoadImage),
                                 None, # Separator
                                 ('Quit',          'Q', self.OnQuitRequest, None),
                                ),
                     'Edit':    (('Increase Zoom', '+', None),
                                 ('Decrease Zoom', '-', None),
                                 ('Reset Zoom',    '=', None),
                                ),
                     'Window':  (('#Fullscreen',     'F', self.ToggleFullscreen),
                                 None, # Separator
                                 ('Draw Surface',    'D', self.OpenDraw),
                                 ('Color Chooser',   'C', self.win_Color.Open),
                                 ('Brush Selection', 'B', self.win_BSel.Open),
                                 ('Mini Background Selection', 'G', self.win_MiniBGSel.Open),
                                ),
                   }

        strip = Menustrip()   
        for k, v in menu_def.iteritems():
            menu = Menu(k)
            strip.AddTail(menu)

            if v is None:
                menu.AddTail(Menuitem('-')) # Separator
            else:
                for t in v:
                    if t[0][0] == '#': # toggled item
                        item = Menuitem(t[0][1:], t[1], Toggle=True)
                    else:
                        item = Menuitem(t[0], t[1])
                    item.action(*t[2:])
                    menu.AddTail(item)
 
        # Create Application object
        super(Gribouillis, self).__init__(
            Title       = "Gribouillis",
            Version     = "$VER: Gribouillis %s (%s)" % (self.VERSION, self.DATE),
            Copyright   = "\xa92009, Guillaume ROGUEZ",
            Author      = "Guillaume ROGUEZ",
            Description = "Simple Painting program for MorphOS",
            Base        = "Gribouillis",
            Menustrip   = strip,
        )

        # Be sure that all windows can be closed
        self.win_Color.Notify('CloseRequest', True, self.win_Color.Close)
        self.win_BSel.Notify('CloseRequest', True, self.win_BSel.Close)
        self.win_MiniBGSel.Notify('CloseRequest', True, self.win_MiniBGSel.Close)

        # We can't open a window if it has not been attached to the application
        self.AddWindow(self.win_Color)
        self.AddWindow(self.win_BSel)
        self.AddWindow(self.win_MiniBGSel)

        # Create draw window
        self.InitDrawWindow()

        # Init brushes
        self.init_brushes()

        # Init color
        self.win_Color.add_watcher(self.OnColorChanged)
        self.set_active_brush(self.brushes[0])
        self.set_color(0, 0, 0)

        # Init backgrounds selection window
        self.win_MiniBGSel.add_watcher(self.UseBackground)
        for name in sorted(os.listdir("backgrounds")):
            self.win_MiniBGSel.AddImage(os.path.join("backgrounds", name))

        # Open windows now
        self.win_BSel.Open()
        self.win_Color.Open()
        self.win_Draw.Open()

    def OpenDrawWindow(self):
        self.win_Draw.Open()

    def InitDrawWindow(self, fullscreen=False):
        if self.win_Draw: return
        
        self.win_Draw = DrawWindow("Draw Area", fullscreen)
        self.win_Draw.Notify('CloseRequest', True, self.Quit)
        
        model = LayerModel()
        view = self.win_Draw.raster
        self.controler = DrawControler(view, model)

    def TermDrawWindow(self):
        if not self.win_Draw: return
        
        self.win_Draw.Close()
        del self.controler
        self.RemWindow(self.win_Draw)
        del self.win_Draw
        self.win_Draw = None

    def init_brushes(self):
        self._main_brush = self.win_BSel.brush
        self._brush = None
        
        self.paths['builtins_brushes'] = os.path.join(self.paths['data'], 'brushes')
        self.paths['user_brushes'] = os.path.join(self.paths['user'], 'brushes')

        def listbrushes(path):
            return [fn[:-4] for fn in os.listdir(path) if fn.endswith('.myb')]

        builtins_brushes = listbrushes(self.paths['builtins_brushes'])
        user_brushes = listbrushes(self.paths['user_brushes'])

        # remove duplicates from builtins
        builtins_brushes = [name for name in builtins_brushes if name not in user_brushes]

        # sorting brushes
        unsorted_brushes = user_brushes + builtins_brushes
        sorted_brushes = []
        for path in (self.paths['user_brushes'], self.paths['builtins_brushes']):
            fn = os.path.join(path, 'order.conf')
            if not os.path.exists(fn): continue
            with open(fn) as f:
                for line in f:
                    name = line.strip()
                    if name not in unsorted_brushes: continue
                    unsorted_brushes.remove(name)
                    sorted_brushes.append(name)

        self.brushes_names = unsorted_brushes + sorted_brushes

        paths = (self.paths['user_brushes'], self.paths['builtins_brushes'])
        self.brushes = []
        for name in self.brushes_names:
            b = Brush()
            b.load(paths, name)
            b.Notify(MUIA_Selected, MUIV_EveryTime, self.OnSelectBrush, b)
            self.brushes.append(b)
        self.win_BSel.SetBrushes(self.brushes)

    def set_color(self, *rgb):
        self.win_Color.color = rgb # Coloradjust object will call OnColor method

    def OnColorChanged(self, color): # Called by the ColorChooser window
        self.brush.color = color

    def OnSelectBrush(self, brush):
        if not self._brush is brush:
            self.brush = brush
        else:
            brush.NNSet(MUIA_Selected, True)

    def set_active_brush(self, brush):
        self._main_brush.copy(brush)
        if self._brush:
            self._brush.NNSet(MUIA_Selected, False)
        self._brush = brush
        brush.NNSet(MUIA_Selected, True)
        self.controler.model.SetBrush(self.brush)

    brush = property(fget=lambda self: self._main_brush, fset=set_active_brush)

    def UseBackground(self, bg):
        self.win_Draw.SetBackground(bg.Name)

    def OnLoadImage(self):
        filename = pymui.getfilename(self.win_Draw, "Select image to load", self.last_loaded_dir, "#?.(png|jpeg|jpg|targa|tga|gif)", False)
        if filename:
            self.last_loaded_dir = os.path.dirname(filename)
            self.win_Draw.LoadImage(filename)

    def OnQuitRequest(self):
        self.Quit()

    def ToggleFullscreen(self):
        state = self.win_Draw.fullscreen
        self.TermDrawWindow()
        self.InitDrawWindow(not state)
