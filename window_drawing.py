import _core, mui

class DrawingWindow(mui.Window):
    def __init__(self, app):
        super(DrawingWindow, self).__init__( _core.do_win_drawing())

window = DrawingWindow
