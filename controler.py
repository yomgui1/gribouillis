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

__all__ = ('DrawControler', )

from pymui import TABLETA_Pressure, MUI_EventHandlerRC_Eat
import os

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

    def AddData(self, **data):
        self.evtlist.append(data)


class DrawControler(object):
    MODE_IDLE = 0
    MODE_DRAW = 1
    MODE_DRAG = 2
    SCALE_VALUES = [0.2, 0.25, 0.3, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 8.0]
    
    def __init__(self, view, model):
        self.view = view
        self.model = model
        self.scale_idx = self.SCALE_VALUES.index(1.0)
        self.view.ConnectToModel(model)

        # Inputs comes from the view
        self.view.add_watcher('mouse-button', self.OnMouseButton)
        self.view.add_watcher('mouse-motion', self.OnMouseMotion)
        self.view.add_watcher('rawkey', self.OnKey)

        self._mode = DrawControler.MODE_IDLE
        self._rec = Recorder() # XXX: to use, one day ;-)

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
        self.secs = evt.Seconds
        self.mics = evt.Micros
        
    def OnKey(self, evt):
        if evt.Up:
            cb = self.KEYMAPS_UP.get(evt.Key)
        else:
            cb = self.KEYMAPS_DOWN.get(evt.Key)

        if cb:
            return cb(self, evt)

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
        self.secs = evt.Seconds
        self.mics = evt.Micros

        # Tablet position available only during move
        self.tbx = None
        
        if mode == DrawControler.MODE_DRAW:
            pos = self.view.GetSurfacePos(self.mx, self.my)
            self.model.InitializeDrawAction(pos)
        elif mode == DrawControler.MODE_DRAG:
            self.view.StartMove()

        self.mode = mode 
        
    def CancelAction(self, mode, evt):
        if self._mode == DrawControler.MODE_DRAG:
            self.view.CancelMove()
        elif self._mode == DrawControler.MODE_DRAW:
            self.model.FinalizeDrawAction(False)
        self.mode = mode

    def ConfirmAction(self, mode, evt):
        if self._mode == DrawControler.MODE_DRAW:
            self.model.FinalizeDrawAction(True)
        self.mode = mode

    def DragOnMotion(self, evt):
        # Raster moves never use tablet data, only mouse (pixel unit)
        self.view.Scroll(self.mx - evt.MouseX, self.my - evt.MouseY)
        self.view.RedrawDamaged()

    def DrawOnMotion(self, evt):
        # create the stroke data
        if evt.ValidTD:
            #if self.tbx is not None:
            #    speed = (evt.td_NormTabletX - self.tbx,
            #             evt.td_NormTabletY - self.tby)
            #    self.tbx = evt.td_NormTabletX
            #    self.tby = evt.td_NormTabletY
            p = float(evt.td_Tags.get(TABLETA_Pressure, PRESSURE_MAX/2)) / PRESSURE_MAX
        else:
            p = 0.5

        pos = self.view.GetSurfacePos(evt.MouseX, evt.MouseY)
        
        # record and render the stroke
        # TODO: for now, a stroke is just a dict object.
        # we need to use a custom object later for optimizations.
        time = (evt.Seconds+evt.Micros*1e-6) - (self.secs+self.mics*1e-6)
        stroke = dict(pos=pos, pressure=p, time=time)
        self.model.RecordStroke(stroke)
        self.view.AddDamagedBuffer(self.model.RenderStroke(stroke))
        self.view.RedrawDamaged()

    def OnMouseWheelUp(self, evt):
        if self.scale_idx+1 < len(self.SCALE_VALUES):
            x, y = self.view.GetSurfacePos(evt.MouseX, evt.MouseY) 
            self.scale_idx += 1        
            self.view.scale = self.SCALE_VALUES[self.scale_idx]
            x, y = self.view.GetRasterPos(x, y)
            self.view.osx += evt.MouseX-x
            self.view.osy += evt.MouseY-y
            self.view.RedrawFull()

    def OnMouseWheelDown(self, evt):
        if self.scale_idx-1 >= 0:
            x, y = self.view.GetSurfacePos(evt.MouseX, evt.MouseY)
            self.scale_idx -= 1 
            self.view.scale = self.SCALE_VALUES[self.scale_idx]
            x, y = self.view.GetRasterPos(x, y)
            self.view.osx += evt.MouseX-x
            self.view.osy += evt.MouseY-y
            self.view.RedrawFull()
    
    def Clear(self):
        self.model.Clear()
        self.view.RedrawFull()

    KEYMAPS_UP = { }

    KEYMAPS_DOWN = { NM_WHEEL_UP:     OnMouseWheelUp,
                     NM_WHEEL_DOWN:   OnMouseWheelDown,
                   }

    def LoadImage(self, filename):
        assert "METHOD" is "NOT IMPLEMENTED"
    
    def SaveImage(self, filename):
        im = self.model.AsPILImage('RGBA')
        ext = os.path.splitext(filename)[1].lower()
        dpi = (self.model.info['ResolutionX'],
               self.model.info['ResolutionY'])

        if ext == '.png':
            im.save(filename, 'PNG', optimize=True, dpi=dpi, compression=9)
        elif ext in ('.jpg', '.jpeg'):
            im.save(filename, 'JPEG', optimize=True, dpi=dpi, quality=90)
        elif ext == '.ora':
            self.model.SaveAsOpenRaster(filename)
        else:
            im.save(filename)

    def LoadBackground(self, filename):
        self.model.LoadBackground(filename)
        self.view.RedrawFull()

    def Undo(self):
        self.model.Undo()
        self.view.RedrawFull()
        
    def Redo(self):
        self.model.Redo()
        self.view.RedrawFull()

    def ResetZoom(self):
        self.view.scale = 1.0
        self.view.osx = self.view.osy = 0
        self.view.RedrawFull()

    def Center(self):
        x, y, w, h = self.model.bbox
        self.view.CenterOnSurfacePoint(x+w/2, y+h/2)
