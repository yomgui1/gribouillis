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

IECODE_UP_PREFIX = 0x80
IECODE_LBUTTON   = 0x68
IECODE_RBUTTON   = 0x69
IECODE_MBUTTON   = 0x6A

NM_WHEEL_UP      = 0x7a
NM_WHEEL_DOWN    = 0x7b

class DrawControler(object):
    MODE_IDLE = 0
    MODE_DRAW = 1
    MODE_DRAG = 2
    
    def __init__(self, view, model):
        self.view = view
        self.model = model

        self.view.model = model

        self._mode = DrawControler.MODE_IDLE

        # Inputs comes from the view
        self.view.add_watcher('mouse-button', self.OnMouseButton)
        self.view.add_watcher('mouse-motion', self.OnMouseMotion)
        self.view.add_watcher('rawkey', self.OnKey)

    def OnMouseButton(self, evt):
        if self._mode == DrawControler.MODE_IDLE:
            if not evt.InObject: return
            if evt.Code == IECODE_LBUTTON:
                if not evt.Up:
                    self.StartAction(DrawControler.MODE_DRAW, evt)
                    return MUI_EventHandlerRC_Eat
            elif evt.Code == IECODE_MBUTTON:
                if not evt.Up:
                    self.StartAction(DrawControler.MODE_DRAG, evt)
                    return MUI_EventHandlerRC_Eat
        elif self._mode == DrawControler.MODE_DRAW:
            if evt.Code == IECODE_LBUTTON:
                if evt.Up:
                    self.ConfirmAction(DrawControler.MODE_IDLE, evt)
                    return MUI_EventHandlerRC_Eat
        elif self._mode == DrawControler.MODE_DRAG:
            if evt.Code == IECODE_LBUTTON:
                if not evt.Up and evt.InObject:
                    self.ConfirmAction(DrawControler.MODE_DRAW, evt)
                    return MUI_EventHandlerRC_Eat
            elif evt.Code == IECODE_MBUTTON:
                if evt.Up:
                    self.ConfirmAction(DrawControler.MODE_IDLE, evt)
                    return MUI_EventHandlerRC_Eat
            elif evt.Code == IECODE_RBUTTON:
                if not evt.Up:
                    self.CancelMode(DrawControler.MODE_IDLE, evt)
                    return MUI_EventHandlerRC_Eat

    def OnMouseMotion(self, evt):
        if self._mode == DrawControler.MODE_DRAG:
            # Raster moves never use tablet data, only mouse (pixel unit)
            self.view.Scroll(self.mx-evt.MouseX, self.my-evt.MouseY)

        elif self._mode == DrawControler.MODE_DRAW:
            if evt.ValidTD and self.tbx is not None:
                dx = evt.td_NormTabletX - self.tbx
                dy = evt.td_NormTabletY - self.tby
            else:
                dx = evt.MouseX - self.mx
                dy = evt.MouseY - self.my
                
            # draw inside the model
            x, y = self.view.GetSurfacePos(evt.MouseX, evt.MouseY)
            damagedrects = self.model.BrushDraw(x, y, dx / self.view.scale, dy / self.view.scale)

            # converting damaged rectangles from model to view coordinates and add them to view
            for a,b,c,d in damagedrects:
                self.view.AddDamagedRect(*(self.view.GetRasterPos(a,b)+self.view.GetRasterPos(c,d)))

            # redraw using this damaged list
            self.view.Redraw(MADF_DRAWUPDATE)
        
        self.mx = evt.MouseX
        self.my = evt.MouseY
        if evt.ValidTD: 
            self.tbx = evt.td_NormTabletX
            self.tby = evt.td_NormTabletY
    
    def OnKey(self, evt):
        pass

    def SetMode(self, mode):
        if mode != self._mode:
            self.view.EnableMouseMoveEvents(mode != DrawControler.MODE_IDLE)
            self._mode = mode
        
    mode = property(fget=lambda self: self._mode, fset=SetMode)

    def StartAction(self, mode, evt):
        # /!\ event MouseX/Y origin is the left/top origin of the window
        self.mx = evt.MouseX
        self.my = evt.MouseY

        # Tablet position available only during move
        self.tbx = None
        
        if mode == DrawControler.MODE_DRAW:
            pos = self.view.GetSurfacePos(self.mx, self.my)
            self.model.BrushMove(*pos)
            self.view.Redraw(MADF_DRAWOBJECT)
        elif mode == DrawControler.MODE_DRAG:
            self.view.StartMove()

        self.mode = mode 
        
    def CancelAction(self, mode, evt):
        if self._mode == DrawControler.MODE_DRAG:
            self.view.CancelMove()
        self.mode = mode

    def ConfirmAction(self, mode, evt):
        self.mode = mode     


class DrawWindow(Window):
    def __init__(self, title, fullscreen=True):
        kwds = {}
        if fullscreen:
            kwds['WidthScreen'] = 100
            kwds['HeightScreen'] = 100
            kwds['Borderless'] = True
            kwds['Backdrop'] = True
        else:
            kwds['Width'] = 800
            kwds['Height'] = 600
            kwds['LeftEdge'] = 64
            kwds['TopEdge'] = 64

        super(DrawWindow, self).__init__(title, ID="DRAW",
                                         TabletMessages=True, # enable tablet events support
                                         **kwds
                                         )

        self.raster = Raster()
        self.RootObject = self.raster

    def _isfile(self, path):
        if not os.path.isfile(path):
            raise IOError("given path doesn't exist or not a file: '%s'" % path)

