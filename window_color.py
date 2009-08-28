from window import Window
import _core, mui

MUIA_Coloradjust_RGB = 0x8042f899
MUIV_EveryTime = 0x49893131

class ColorChooser(Window):
    def __init__(self):
        self._color_adjust = mui.MUIObject(_core.do_color_adjust())
        Window.__init__(self, _core.do_win_color(self._color_adjust.mui))

        self.watchers = []

        # register callback when the MUI Coloradjust object get its color changed
        self._color_adjust.notify(MUIA_Coloradjust_RGB, MUIV_EveryTime, self.OnColorChanged)

    def set_color(self, *rgb):
        _core.set_color(self._color_adjust.mui, *rgb)

    def get_color(self):
        return _core.get_color(self._color_adjust.mui)

    def add_watcher(self, cb):
        if cb not in self.watchers:
            self.watchers.append(cb)

    def rem_watcher(self, cb):
        self.watchers.remove(cb)

    def OnColorChanged(self):
        color = self.get_color()
        for cb in self.watchers:
            cb(color)

window = ColorChooser
