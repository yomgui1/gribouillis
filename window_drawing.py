import _core, mui, _surface

class DrawingWindow(mui.Window):
    def __init__(self, app):
        super(DrawingWindow, self).__init__(app, _core.do_win_drawing())

        self.draw = False

        self.surface = mui.MUIObject(_core.get_surface())
        self.surface.notify(_surface.MA_Surface_MotionEvent, mui.MUIV_EveryTime, self.motion_event_cb, mui.MUIV_TriggerValue)
        self.surface.notify(_surface.MA_Surface_LeftButtonPressed, mui.MUIV_EveryTime, self.lbutton_event_cb, mui.MUIV_TriggerValue)

    def lbutton_event_cb(self, down):
        self.draw = bool(down)

    def motion_event_cb(self, evt_p):
        evt = _surface.get_eventmotion(evt_p)
        if self.draw:
            _surface.draw(self.surface.mui, evt.X, evt.Y, evt.Pressure)

window = DrawingWindow
