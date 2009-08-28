import os, _core

class Brush(object):
    def __init__(self, app):
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
        self.muio = _core.mui_image(path)

    def set_color(self, color):
        print "brush color:", color

    color = property(fget=lambda self: self._color, fset=set_color)

    def copy(self, brush):
        pass
