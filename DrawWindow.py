from pymui import *
from surface import TiledSurface

MUIA_Bitmap_PNGData = 0x8042f4ba # V20 isg (UBYTE *)
MUIA_Bitmap_PNGSize = 0x8042a0ea # V20 isg LONG

class DrawWindow(Window):
    def __init__(self, title):
        super(DrawWindow, self).__init__(title, ID="DRAW",
                                         Width=800, Height=600,
                                         LeftEdge=64, TopEdge=64)

        self.surface = TiledSurface()
        self.surface.Background = MUII_SHINE

        self.RootObject = self.surface

