import os, _core, mui

class Brush(mui.MUIObject):
    def __init__(self):
        super(Brush, self).__init__() # MUI object given at 'load 'method
        self._color = (0, 0, 0)

    def load(self, search_paths, name):
        fullname = name + '_prev.png'
        
        for path in search_paths:
            filename = os.path.join(path, fullname)
            if not os.path.isfile(filename): continue

            self.name = name
            self.path = filename
            self.mui = _core.do_brush(filename)
            return
        
        raise RuntimeError('brush "' + name + '" not found')

    def set_color(self, color):
        pass

    color = property(fget=lambda self: self._color, fset=set_color)

    def copy(self, brush):
        self.mui = brush.mui
        self.name = brush.name
        self.path = brush.path
        self.color = brush.color
