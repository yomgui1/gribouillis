import _core, mui

class BrushEditorWindow(mui.Window):
    def __init__(self, app):
        super(BrushEditorWindow, self).__init__(app, _core.do_win_brusheditor())

window = BrushEditorWindow
