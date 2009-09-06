from pymui import *

class DrawWindow(Window):
    def __init__(self, title):
        super(DrawWindow, self).__init__(title, ID="DRAW",
                                         Width=800, Height=600,
                                         LeftEdge=64, TopEdge=64)

        surface = Rectangle.HVSpace()
        surface.Background = MUII_SHINE

        self.RootObject = surface
