from window import Window
import _core

class ColorChooser(Window):
    def __init__(self):
        Window.__init__(self)
        self.muio = _core.create_color_gui()

    def set_color(self, *rgb):
        assert len(rgb) == 3, 'Bad call'
        _core.set_color(*rgb)

    def get_color(self):
        return _core.get_color()

window = ColorChooser
