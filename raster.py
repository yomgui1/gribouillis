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

import pymui, weakref

MYTAGBASE = pymui.TAG_USER | 0x95fe0000
MM_Raster_Move = MYTAGBASE + 0x00

class Raster(pymui.Area):
    CLASSID = "Raster.mcc"

    EVENTMAP = {
        IDCMP_MOUSEBUTTONS : 'mouse-button',
        IDCMP_MOUSEMOVE    : 'mouse-motion',
        IDCMP_RAWKEY       : 'rawkey',
        }

    def __init__(self):
        pymui.Area.__init__(self, MCC=True)
        self._watchers = {}
        self._ev = pymui.EventHandler()
        self.osx = 0 # X position of the surface origin, in raster origin
        self.osy = 0 # Y position of the surface origin, in raster origin
        self.scale = 1.0 # zoom factor

    def add_watcher(self, name, cb, *args):
        wl = self._watchers.get(name)
        if wl is None:
            self._watchers[name] = wl = []
        wl.append((cb, args))

    def MCC_Setup(self):
        self._ev.install(self, pymui.IDCMP_RAWKEY | pymui.IDCMP_MOUSEBUTTONS)
        return TRUE

    def MCC_Cleanup(self):
        self._ev.unsinstall()

    def MCC_HandleEvent(self, ev):
        wl = self._watchers.get(Rater.EVENTMAP.get(evt.Class), [])
        for cb, args in wl:
            cb(evt, *args)

    def EnableMouseMoveEvents(self, state=True):
        self._ev.uninstall()
        self._ev.install(self, self._ev.idcmp | (pymui.IDCMP_MOUSEMOVE if state else 0))

    def GetSurfacePos(self, x, y):
        return (x - self.MLeft - self.osx) * self.scale, (y - self.MTop - self.osy) * self.scale

    def StartMove(self):
        # save data of the current view
        self._saved_osx = self.osx
        self._saved_osy = self.osy
        self._saved_scale = self.scale

    def CancelMove(self):
        pass
        
    def Move(self, dx, dy):
        """Move(dx, dy)

        Move current displayed surface using normalized vector (dx, dy).
        dx and dy are given in pixel integer unit.
        """

        self.osx += dx
        self.osy += dy

        #  This function should return a list of bbox corresponding to surfaces to refresh
        x = self._do(MM_Raster_Move, dx, dy)

        # Normally we shouldn't display the result until a complete refresh
        self.Redraw(pymui.MADF_DRAWOBJECT)
