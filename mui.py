from _mui import *

MUIA_Selected = 0x8042654b
MUIA_Window_Open = 0x80428aa0
MUIA_Coloradjust_RGB = 0x8042f899
MUIV_EveryTime = 0x49893131

class MUIObject(object):
    def __init__(self, obj=None):
        self._notify = dict()
        self._muio = obj

    def _notify_cb(self, attr, v):
        tv, cb, a = self._notify[attr]
        if tv == MUIV_EveryTime or tv == v:
            cb(*a)

    def notify(self, trigAttr, trigValue, callback, *args):
        self._notify[trigAttr] = (trigValue, callback, args)
        notify(self, self._muio, trigAttr, trigValue)

    def set_mui(self, obj):
        self._muio = obj

    mui = property(fget=lambda self: self._muio, fset=set_mui, doc="Get associated MUI object (Python CObject)")

class Application(MUIObject):
    def __init__(self, obj):
        super(Application, self).__init__(obj)

    def mainloop(self):
        mainloop(self.mui)
    
class Window(MUIObject):
    def __init__(self, app, obj):
        super(Window, self).__init__(obj)
        add_member(app.mui, self.mui)

    def open(self, state=True):
        set(self.mui, MUIA_Window_Open, state)
