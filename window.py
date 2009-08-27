import _mui

MUIA_Window_Open = 0x80428aa0

class Window:
    def __init__(self):
        pass

    def open(self, state=True):
        _mui.set(self.muio, MUIA_Window_Open, state)
