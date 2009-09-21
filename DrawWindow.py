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
import os.path

IECODE_UP_PREFIX = 0x80
IECODE_LBUTTON   = 0x68
IECODE_RBUTTON   = 0x69
IECODE_MBUTTON   = 0x6A

NM_WHEEL_UP      = 0x7a
NM_WHEEL_DOWN    = 0x7b

PRESSURE_MAX     = 0x7ffff800

class Recorder:
    def __init__(self):
        self.evtlist = []

    def Start(self, init=False):
        if init:
            self.evtlist = []

    def Stop(self):
        pass

    def AddEvent(self, secs, micros, pos, pressure, **extra):
        if extra:
            self.evtlist.append((secs, micros, pos, pressure, extra))
        else:
            self.evtlist.append((secs, micros, pos, pressure))


class DrawControler(object):
    MODE_IDLE = 0
    MODE_DRAW = 1
    MODE_DRAG = 2
    
    def __init__(self, view, model):
        self.view = view
        self.model = model
        self.view.ConnectToModel(model)

        # Inputs comes from the view
        self.view.add_watcher('mouse-button', self.OnMouseButton)
        self.view.add_watcher('mouse-motion', self.OnMouseMotion)
        self.view.add_watcher('rawkey', self.OnKey)

        self._mode = DrawControler.MODE_IDLE
        self._rec = Recorder()

    def OnMouseButton(self, evt):
        if self._mode == DrawControler.MODE_IDLE:
            if not evt.InObject: return
            if evt.Key == IECODE_LBUTTON:
                if not evt.Up:
                    self.StartAction(DrawControler.MODE_DRAW, evt)
                    return MUI_EventHandlerRC_Eat
            elif evt.Key == IECODE_MBUTTON:
                if not evt.Up:
                    self.StartAction(DrawControler.MODE_DRAG, evt)
                    return MUI_EventHandlerRC_Eat
        elif self._mode == DrawControler.MODE_DRAW:
            if evt.Key == IECODE_LBUTTON:
                if evt.Up:
                    self.ConfirmAction(DrawControler.MODE_IDLE, evt)
                    return MUI_EventHandlerRC_Eat
        elif self._mode == DrawControler.MODE_DRAG:
            if evt.Key == IECODE_MBUTTON:
                if evt.Up:
                    self.ConfirmAction(DrawControler.MODE_IDLE, evt)
                    return MUI_EventHandlerRC_Eat
            elif evt.Key == IECODE_RBUTTON:
                if not evt.Up:
                    self.CancelMode(DrawControler.MODE_IDLE, evt)
                    return MUI_EventHandlerRC_Eat

    def OnMouseMotion(self, evt):
        self._on_motion(evt)
        self.mx = evt.MouseX
        self.my = evt.MouseY
        
    def OnKey(self, evt):
        if evt.Up:
            cb = self.KEYMAPS.get(evt.Key)
            if cb:
                cb(self, evt)

    def SetMode(self, mode):
        if mode != self._mode:
            if mode == DrawControler.MODE_DRAG:
                self._on_motion = self.DragOnMotion
            elif mode == DrawControler.MODE_DRAW:
                self._on_motion = self.DrawOnMotion
            else:
                self._on_motion = None # Guard

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
            self._rec.Start(True)
            pos = self.view.GetSurfacePos(self.mx, self.my)
            self.model.MoveBrush(*pos)
        elif mode == DrawControler.MODE_DRAG:
            self._rec.Start(True) 
            self.view.StartMove()

        self.mode = mode 
        
    def CancelAction(self, mode, evt):
        if self._mode == DrawControler.MODE_DRAG:
            self.view.CancelMove()
        self.mode = mode
        self._rec.Stop()

    def ConfirmAction(self, mode, evt):
        self.mode = mode
        self._rec.Stop()

    def DragOnMotion(self, evt):
        # Raster moves never use tablet data, only mouse (pixel unit)
        self.view.Scroll(self.mx - evt.MouseX, self.my - evt.MouseY)
        self.view.RedrawDamaged()

    def DrawOnMotion(self, evt):
        if evt.ValidTD:
            if self.tbx is not None:
                speed = (evt.td_NormTabletX - self.tbx,
                         evt.td_NormTabletY - self.tby)
                self.tbx = evt.td_NormTabletX
                self.tby = evt.td_NormTabletY
            else:
                speed = None
            p = float(evt.td_Tags.get(TABLETA_Pressure, PRESSURE_MAX/2)) / PRESSURE_MAX
            #tilt = (float(evt.td_Tags.get(TABLETA_AngleX, 2147483648))/0x7ffffff8-1, float(evt.td_Tags.get(TABLETA_AngleY, 2147483648))/0x7ffffff8-1)
        else:
            speed = None
            p = 0.5

        if not speed:
            speed = ((evt.MouseX - self.mx)/self.view.SRangeX, (evt.MouseY - self.my)/self.view.SRangeY)
        
        # draw inside the model
        pos = self.view.GetSurfacePos(evt.MouseX, evt.MouseY)
        self._rec.AddEvent(evt.Seconds, evt.Micros, pos, p)
        _ = tuple(self.model.Draw(pos, speed=speed, pressure=p))
        self.view.AddDamagedBuffer(*_)
        self.view.RedrawDamaged()

    def OnMouseWheelUp(self, evt):
        pass

    def OnMouseWheelDown(self, evt):
        pass

    def Clear(self):
        self.model.Clear()
        self.view.RedrawFull()

    KEYMAPS = { NM_WHEEL_UP:     OnMouseWheelUp,
                NM_WHEEL_DOWN:   OnMouseWheelDown,
                }
        

class DrawWindow(Window):
    def __init__(self, title, raster, fullscreen=False):
        self.fullscreen = fullscreen
        kwds = {}
        if fullscreen:
            kwds['WidthScreen'] = 100
            kwds['HeightScreen'] = 100
            kwds['Borderless'] = True
            kwds['Backdrop'] = True
            kwds['ID'] = 'DRWF'
            # Note: if I use the same ID for each FS mode, the FS window will take data
            # of the non FS window... that's render very bad ;-)
        else:
            kwds['Width'] = 800
            kwds['Height'] = 600
            kwds['LeftEdge'] = 64
            kwds['TopEdge'] = 64
            kwds['ID'] = 'DRW0'

        super(DrawWindow, self).__init__(title,
                                         RootObject=raster,
                                         TabletMessages=True, # enable tablet events support
                                         **kwds)

    def _isfile(self, path):
        if not os.path.isfile(path):
            raise IOError("given path doesn't exist or not a file: '%s'" % path)

