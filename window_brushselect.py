import _core, mui

class BrushSelectWindow(mui.Window):
    def __init__(self, app):
        super(BrushSelectWindow, self).__init__(app, _core.do_win_brushselect(app))

window = BrushSelectWindow
