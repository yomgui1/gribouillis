from __future__ import with_statement
import os, sys
from pymui import *
from brush import Brush

from DrawWindow import DrawWindow
from ColorChooser import ColorChooser
from BrushSelect import BrushSelect

class Gribouillis(Application):
    VERSION = 1.0
    DATE    = "05/09/2009"

    def __init__(self, datapath, userpath=None):
        if userpath is None:
            userpath = datapath

        self.paths = dict(data=datapath, user=userpath) 

        # Create Windows
        self.win_Draw = DrawWindow("Draw Area")
        self.win_Color = ColorChooser("Color Selection")
        self.win_BSel = BrushSelect("Brush Selection")

        # Create Menus
        strip = Menustrip()
        
        menu = Menu('Project')
        strip.AddTail(menu)

        item = Menuitem('Quit', 'Q')
        item.action(self.Quit)
        menu.AddTail(item)

        menu = Menu('Edit')
        strip.AddTail(menu)
        
        item = Menuitem('Increase Zoom', '+')
        item.action(self.win_Draw.AddZoom, +0.5)
        menu.AddTail(item)

        item = Menuitem('Decrease Zoom', '-')
        item.action(self.win_Draw.AddZoom, -0.5)
        menu.AddTail(item)

        item = Menuitem('Reset Zoom', '0')
        item.action(self.win_Draw.ResetZoom)
        menu.AddTail(item)

        for i, name in enumerate(os.listdir("backgrounds")[:9]):
            item = Menuitem('Set background #%u' % i, str(i))
            item.action(self.win_Draw.SetBackground, os.path.join("backgrounds", name))
            menu.AddTail(item)

        menu = Menu('Windows')
        strip.AddTail(menu)

        item = Menuitem('Draw Surface', 'D')
        item.action(self.win_Draw.Open)
        menu.AddTail(item)
 
        item = Menuitem('Color Chooser', 'C')
        item.action(self.win_Color.Open)
        menu.AddTail(item)

        item = Menuitem('Brush Selection', 'B')
        item.action(self.win_BSel.Open)
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

        self.win_Draw.Notify('CloseRequest', True, self.Quit)
        self.win_Color.Notify('CloseRequest', True, self.win_Color.Close)
        self.win_BSel.Notify('CloseRequest', True, self.win_BSel.Close)

        # We can't open a window if it has not been attached to the application
        self.AddWindow(self.win_Draw)
        self.AddWindow(self.win_Color)
        self.AddWindow(self.win_BSel)

        self.init_brushes()     

        self.win_Color.add_watcher(self.OnColorChanged)
        self.set_active_brush(self.brushes[0])
        self.set_color(0, 0, 0)

        self.win_Draw.Open()
        self.win_Color.Open()
        self.win_BSel.Open()

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

    brush = property(fget=lambda self: self._main_brush, fset=set_active_brush)

