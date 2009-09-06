import os
from pymui import Dtpic, MUIV_InputMode_Toggle, MUIV_Frame_ImageButton

MUIA_Dtpic_Scale = 0x8042ca4c  # private

class Brush(Dtpic):
    BRUSH_SCALE = 48

    def __init__(self):
        super(Brush, self).__init__(InputMode=MUIV_InputMode_Toggle, Frame=MUIV_Frame_ImageButton)
        self._set(MUIA_Dtpic_Scale, self.BRUSH_SCALE)
        self._color = (0, 0, 0)

    def load(self, search_paths, name):
        fullname = name + '_prev.png'
        
        for path in search_paths:
            filename = os.path.join(path, fullname)
            if not os.path.isfile(filename): continue

            self.shortname = name
            self.Name = filename
            return
        
        raise RuntimeError('brush "' + name + '" not found')

    def set_color(self, color):
        pass

    color = property(fget=lambda self: self._color, fset=set_color)

    def copy(self, brush):
        self.Name = brush.Name
        self.shortname = brush.shortname
        self.color = brush.color
