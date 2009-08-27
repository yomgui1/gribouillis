from window import Window
import _core

class ColorChooser(Window):
    def __init__(self):
        Window.__init__(self)
        self._color_adjust = _core.do_color_adjust()
        self.muio = _core.do_win_color(self._color_adjust)

    def set_color(self, *rgb):
        assert len(rgb) == 3, 'Bad call'
        _core.set_color(self._color_adjust, *rgb)

    def get_color(self):
        return _core.get_color(self._color_adjust)

window = ColorChooser
