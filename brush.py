import os, _core

class Brush:
    def __init__(self, app):
        self.app = app

    def load(self, name):
        fn = name + '_prev.png'
        path = os.path.join(self.app.paths['user_brushes'], fn)
        if not os.path.isfile(path):
            path = os.path.join(self.app.paths['builtins_brushes'], fn)
        assert os.path.isfile(path), 'brush "' + name + '" not found'
        self.name = name
        self.path = path
        self.muio = _core.mui_image(path)
