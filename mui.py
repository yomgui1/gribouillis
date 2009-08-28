from _mui import *

MUIA_Window_Open = 0x80428aa0

class MUIObject(object):
    def __init__(self, obj):
        self._notify_cb = []
        self._muio = obj

    def notify(self, *args):
        self._notify_cb.append(notify(self._muio, *args))

    mui = property(fget=lambda self: self._muio, doc="Get associated MUI object (Python CObject)")
