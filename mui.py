from _mui import *

MUIA_Selected = 0x8042654b
MUIA_Window_Open = 0x80428aa0
MUIA_Coloradjust_RGB = 0x8042f899
MUIV_EveryTime = 0x49893131

class MUIObject(object):
    def __init__(self, obj=None):
        self._nslot_list = []
        self._muio = obj

    def notify(self, trigAttr, trigValue, callback, *args):
        self._nslot_list.append(notify(self._muio, trigAttr, trigValue, callback, *args))

    def set_mui(self, obj):
        self._muio = obj

    mui = property(fget=lambda self: self._muio, fset=set_mui, doc="Get associated MUI object (Python CObject)")

class Application(MUIObject):
    def __init__(self, obj):
        super(Application, self).__init__(obj)

    def mainloop(self):
        mainloop(self.mui)
    
class Window(MUIObject):
    def open(self, state=True):
        set(self.mui, MUIA_Window_Open, state)
