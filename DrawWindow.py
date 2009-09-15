###############################################################################
# Copyright (c) 2009 Guillaume Roguez
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
###############################################################################

from pymui import *
from raster import Raster
import os.path

class DrawControler(object):
    MODE_IDLE = 0
    MODE_DRAW = 1
    MODE_DRAG = 2
    
    def __init__(self, view, model):
        self.view = view
        self.model = model
        self._mode = MODE_IDLE

        # Inputs comes from the view
        self.view.add_watcher('mouse-button', self.OnMouseButton)
        self.view.add_watcher('mouse-motion', self.OnMouseMotion)
        self.view.add_watcher('rawkey', self.OnKey)

    def OnMouseButton(self, evt):
        if self._mode == MODE_IDLE:
            if not evt.InObject: return
            if evt.Code == IECODE_LBUTTON:
                if not evt.Up:
                    self.StartAction(Raster.MODE_DRAW, evt)
                    return MUI_EventHandlerRC_Eat
            elif evt.Code == IECODE_MBUTTON:
                if not evt.Up:
                    self.StartAction(Raster.MODE_DRAG, evt)
                    return MUI_EventHandlerRC_Eat
        elif self._mode == MODE_DRAW:
            if evt.Code == IECODE_LBUTTON:
                if evt.Up:
                    self.ConfirmAction(Raster.MODE_IDLE, evt)
                    return MUI_EventHandlerRC_Eat
        elif self._mode == MODE_DRAG:
            if evt.Code == IECODE_LBUTTON:
                if not evt.Up and evt.InObject:
                    self.ConfirmAction(Raster.MODE_DRAW, evt)
                    return MUI_EventHandlerRC_Eat
            elif evt.Code == IECODE_MBUTTON:
                if evt.Up:
                    self.ConfirmAction(Raster.MODE_IDLE, evt)
                    return MUI_EventHandlerRC_Eat
            elif evt.Code == IECODE_RBUTTON:
                if not evt.Up:
                    self.CancelMode(Raster.MODE_IDLE, evt)
                    return MUI_EventHandlerRC_Eat

    def OnMouseMotion(self, evt):
        if self._mode == Raster.MODE_DRAG:
            # Raster moves never use tablet data, only mouse (pixel unit)
            self.view.Move(self.mx-evt.MouseX, self.my-evt.MouseY)
        elif self._mode == Raster.MODE_DRAW:
            if evt.ValidTD:
                dx = (evt.td_NormTabletX - self.tbx) * self.view.SRangeX
                dy = (evt.td_NormTabletY - self.tby) * self.view.SRangeX
            else:
                dx = double(evt.MouseX - self.mx)
                dy = double(evt.MouseY - self.my)
            self.model.BrushDraw(dx, dy)
    
    def OnKey(self, evt):
        pass

    def SetMode(self, mode):
        if mode != self._mode:
            self.view.EnableMouseMoveEvents(mode != Raster.MODE_IDLE)
            self._mode = mode
        
    mode = property(fget=lambda self: self._mode, fset=SetMode)

    def StartAction(self, mode, evt):
        self.mx = evt.MouseX
        self.my = evt.MouseY

        self.tbx = evt.td_NormTabletX
        self.tby = evt.td_NormTabletY
        
        self.mode = mode
        
        if mode == Raster.MODE_DRAW:
            pos = self.view.GetSurfacePos(self.mx, self.my)
            self.model.BrushMove(*pos)
        elif mode == Raster.MODE_DRAG:
            self.view.StartMove()
        
    def CancelAction(self, mode, evt):
        if self._mode == Raster.MODE_DRAG:
            self.view.CancelMove()
        self.mode = mode

    def ConfirmAction(self):
        pass


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

