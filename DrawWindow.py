from pymui import *
from raster import Raster
import os.path

class DrawControler(object):
    def __init__(self, view, model):
        self.view = view
        self.model = model

        self.view.add_watcher('mouse-button', self.OnMouseButton)
        self.view.add_watcher('mouse-motion', self.OnMouseMotion)
        self.view.add_watcher('key-released', self.OnKey)

class DrawWindow(Window):
    def __init__(self, title):
        super(DrawWindow, self).__init__(title, ID="DRAW",
                                         Width=800, Height=600,
                                         LeftEdge=64, TopEdge=64,
                                         TabletMessages=True, # enable tablet events support
                                         )

        self.raster = Raster()
        self.RootObject = self.raster

    def _isfile(self, path):
        if not os.path.isfile(path):
            raise IOError("given path doesn't exist or not a file: '%s'" % path)

    def AddZoom(self, n):
        #self.raster.scale += n
        self.raster.Redraw(MADF_DRAWOBJECT)

    def ResetZoom(self):
        #del self.raster.scale
        #self.raster.sx = self.surface.sy = 0.0
        self.raster.Redraw(MADF_DRAWOBJECT)

    def SetBackground(self, path):
        self._isfile(path)
        #self.surface.Background = "5:"+path

    def LoadImage(self, path):
        self._isfile(path)
        #self.surface.SetBackgroundImage(path)
