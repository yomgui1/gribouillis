import os, _core, mui

class Brush(mui.MUIObject):
    def __init__(self, app):
        mui.MUIObject.__init__(self)

        self.app = app
        self._color = (0, 0, 0)

    def load(self, name):
        fn = name + '_prev.png'
        path = os.path.join(self.app.paths['user_brushes'], fn)
        if not os.path.isfile(path):
            path = os.path.join(self.app.paths['builtins_brushes'], fn)
        assert os.path.isfile(path), 'brush "' + name + '" not found'
        self.name = name
        self.path = path
        self.mui = _core.mui_brush(path)

        self.notify(mui.MUIA_Selected, mui.MUIV_EveryTime, self.OnSelected)

    def set_color(self, color):
        pass

    color = property(fget=lambda self: self._color, fset=set_color)

    def copy(self, brush):
        self.mui = brush.mui
        self.name = brush.name
        self.path = brush.path
        self.color = brush.color

    def OnSelected(self):
        self.app.set_active_brush(self)
