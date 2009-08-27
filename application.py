from __future__ import with_statement
import os, _core
from brush import Brush

class Application:
    def __init__(self, datapath, userpath=None):
        if userpath is None:
            userpath = datapath

        self.paths = dict(data=datapath, user=userpath)
        
        self.muio = _core.create_app()

        gd = globals()
        ld = locals()

        # GUI creation
        for name in ['window_color']:
            m = __import__(name, gd, ld)
            win = m.window()
            _core.add_member(self.muio, win.muio)
            self.__dict__[name] = win
            win.open()
        
        self.init_brushes()
        self.set_color(0,0,0)

    def init_brushes(self):
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
        for name in self.brushes_names:
            b = Brush(self)
            b.load(name)
            self.brushes.append(b)

        self.set_active_brush(self.brushes[0])

    def set_active_brush(self, brush):
        self.selected_brush = brush
        _core.set_active_brush(brush.path)

    def set_color(self, *rgb):
        self.window_color.set_color(*rgb)

    def OnSelectedBrush(self, path):
        for b in self.brushes:
            if b.path == path:
                self.set_active_brush(b)

    def OnColor(self, *rgb):
        assert len(rgb) == 3, 'Bad call'
        self.active_color = rgb
