import _core, mui

class ColorChooser(mui.Window):
    default_color = (0, 0, 0)
    
    def __init__(self, app):
        self._color_adjust = mui.MUIObject(_core.do_color_adjust())
        super(ColorChooser, self).__init__(_core.do_win_color(self._color_adjust.mui))

        self.watchers = []

        # register callback when the MUI Coloradjust object get its color changed
        self._color_adjust.notify(mui.MUIA_Coloradjust_RGB, mui.MUIV_EveryTime, self.OnColorChanged)

    def set_color(self, rgb):
        _core.set_color(self._color_adjust.mui, *rgb)

    def get_color(self):
        return _core.get_color(self._color_adjust.mui)

    def del_color(self):
        _core.set_color(self._color_adjust.mui, *ColorChooser.default_color)

    color = property(fget=get_color, fset=set_color, del=del_color)

    def add_watcher(self, cb):
        if cb not in self.watchers:
            self.watchers.append(cb)

    def rem_watcher(self, cb):
        self.watchers.remove(cb)

    def OnColorChanged(self):
        c = self.color
        for cb in self.watchers:
            cb(c)

window = ColorChooser
