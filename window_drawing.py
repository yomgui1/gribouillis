from window import Window
import _core

class DrawingWindow(Window):
    def __init__(self):
        Window.__init__(self)
        self.muio = _core.do_win_drawing()

window = DrawingWindow
