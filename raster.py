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

import pymui

DEBUG = True

class Raster(pymui.Area):
    EVENTMAP = {
        pymui.IDCMP_MOUSEBUTTONS : 'mouse-button',
        pymui.IDCMP_MOUSEMOVE    : 'mouse-motion',
        pymui.IDCMP_RAWKEY       : 'rawkey',
        }

    def __init__(self):
        pymui.Area.__init__(self,
                            InnerSpacing=(0,)*4,
                            FillArea=False,
                            DoubleBuffer=True,
                            MCC=True)
        self._clip = True
        self._watchers = {}
        self._ev = pymui.EventHandler()
        self.osx = 0 # X position of the surface origin, in raster origin
        self.osy = 0 # Y position of the surface origin, in raster origin
        self.scale = 1.0 # zoom factor
        self.model = None

    def add_watcher(self, name, cb, *args):
        wl = self._watchers.get(name)
        if wl is None:
            self._watchers[name] = wl = []
        wl.append((cb, args))

    def MCC_AskMinMax(self):
        return 0, 320, 10000, 0, 320, 10000

    def MCC_Setup(self):
        self._ev.install(self, pymui.IDCMP_RAWKEY | pymui.IDCMP_MOUSEBUTTONS)
        return True

    def MCC_Cleanup(self):
        self._ev.uninstall()

    def MCC_HandleEvent(self, evt):
        wl = self._watchers.get(Raster.EVENTMAP.get(evt.Class), [])
        for cb, args in wl:
            cb(evt, *args)

    def MCC_Draw(self, flags):
        if flags & pymui.MADF_DRAWOBJECT:
            self._draw_area(self.MLeft, self.MTop, self.MRight, self.MBottom)
        elif flags & pymui.MADF_DRAWUPDATE:
            for rect in self._damaged:
                if rect is not None:
                    self._draw_area(*rect)
    
    def _draw_area(self, *bbox):
        a, b = self.GetSurfacePos(*bbox[:2])
        c, d = self.GetSurfacePos(*bbox[2:])
        for buf, rx, ry in self.model.GetBuffers(a, b, c, d):
            rx = int(rx * self.scale) + self.osx + self.MLeft
            ry = int(ry * self.scale) + self.osy + self.MTop
            if buf:
                self._rp.ScaledBlit8(buf, buf.Width, buf.Height, rx, ry, int(buf.Width * self.scale), int(buf.Height * self.scale))
            if DEBUG:
                self._rp.Rect(3, rx, ry, int(buf.Width * self.scale), int(buf.Height * self.scale))
 

    def EnableMouseMoveEvents(self, state=True):
        self._ev.uninstall()
        if state:
            idcmp = self._ev.idcmp | pymui.IDCMP_MOUSEMOVE
        else:
            idcmp = self._ev.idcmp & ~pymui.IDCMP_MOUSEMOVE
        self._ev.install(self, idcmp)

    def GetSurfacePos(self, x, y):
        return (x - self.MLeft - self.osx) / self.scale, (y - self.MTop - self.osy) / self.scale

    def StartMove(self):
        # save data of the current view
        self._saved_osx = self.osx
        self._saved_osy = self.osy
        self._saved_scale = self.scale

    def CancelMove(self):
        pass
        
    def Scroll(self, dx, dy):
        """Scroll(dx, dy)

        Scroll current displayed surface using pixel vector (dx, dy).
        """

        self.osx -= dx
        self.osy -= dy

        a, b, c, d = self.MLeft, self.MTop, self.MRight, self.MBottom
        self._rp.Scroll(dx, dy, a, b, c, d)

        ## Compute the damaged rectangles list...
        #
        # It exists 4 damaged rectangles at maximum:
        #
        # +==================+
        # |        #3        |      #1 exists if dx < 0
        # |----+========+----|      #2 exists if dx > 0
        # |    |        |    |      #3 exists if dy < 0
        # | #1 |   OK   | #2 |      #4 exists if dy > 0
        # |    |        |    |
        # |----+========+----|  
        # |        #4        |
        # +==================+              
        #

        self._damaged = [None]*4
        if dx < 0:
            if dy <= 0:
                self._damaged[0] = (a, b-dy, a-dx, d)
            else:
                self._damaged[0] = (a, b, a-dx, d-dy)
        elif dx > 0:
            if dy <= 0:
                self._damaged[1] = (c-dx, b, c, d-dy)
            else:
                self._damaged[1] = (c-dx, b-dy, c, d)

        if dy < 0:
            self._damaged[2] = (a, b, c, b-dy)
        elif dy > 0:
            self._damaged[3] = (a, d-dy, c, d)

        # We're going to redraw only damaged rectangles area
        self.Redraw(pymui.MADF_DRAWUPDATE)

