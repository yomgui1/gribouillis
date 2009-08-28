import mui

class Window(mui.MUIObject):
    def __init__(self, obj):
        mui.MUIObject.__init__(self, obj)

    def open(self, state=True):
        mui.set(self.mui, mui.MUIA_Window_Open, state)
