from __future__ import with_statement
import os, _core, mui, sys
from brush import Brush

class App(mui.Application):
    def __init__(self, datapath, userpath=None):
        super(App, self).__init__(_core.create_app())

        if userpath is None:
            userpath = datapath

        self.paths = dict(data=datapath, user=userpath)
        
        self.init_brushes()

        # GUI creation
        gd = globals()
        ld = locals()
        win_names = ( 'window_drawing',
                      'window_color',
                      'window_brushselect',
                      'window_brusheditor',
                      )
        for name in win_names:
            m = __import__(name, gd, ld)
            win = m.window(self)
            self.__dict__[name] = win
            win.open()

        self.window_color.add_watcher(self.OnColorChanged)   
        
        self.set_active_brush(self.brushes[0]) 
        self.set_color(0, 0, 0)

    def init_brushes(self):
        self._brush = Brush()
        
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

        self.brushes = []
        paths = (self.paths['user_brushes'], self.paths['builtins_brushes'])
        for name in self.brushes_names:
            b = Brush()
            b.load(paths, name)
            b.notify(mui.MUIA_Selected, mui.MUIV_EveryTime, self.OnSelectBrush, b)
            self.brushes.append(b)

    def set_color(self, *rgb):
        self.window_color.color = rgb # Coloradjust object will call OnColor method

    def OnColorChanged(self, color): # Called by the ColorChooser window
        self.brush.color = color

    def OnSelectBrush(self, brush):
        mui.nnset(self.brush.mui, mui.MUIA_Selected, False) 
        self.brush = brush

    def set_active_brush(self, brush):
        self._brush.copy(brush)
        mui.nnset(brush.mui, mui.MUIA_Selected, True)
        _core.set_active_brush(brush.path)

    brush = property(fget=lambda self: self._brush, fset=set_active_brush)

