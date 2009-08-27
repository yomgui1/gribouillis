import _core

class Window:
    def __init__(self):
        pass

    def open(self, state=True):
        _core.win_open(self.muio, state)

