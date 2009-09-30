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

import pymui, _pixarray, lcms

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
        self._damaged = []
        self._damagedbuflist = []
        self._watchers = {}
        self._ev = pymui.EventHandler()
        self._tmpbuf = None
        self.Reset()
        self.model = None
        self.debug = False
        self.EnableCMS(False)

    def Reset(self):
        self.osx = 0 # X position of the surface origin, in raster origin
        self.osy = 0 # Y position of the surface origin, in raster origin
        self._scale = 1.0 # zoom factor

    def SetScale(self, v):
        self._scale = max(0.1, min(10, v))

    scale = property(fget=lambda self: self._scale, fset=SetScale)

    def ConnectToModel(self, model):
        self.model = model

    def add_watcher(self, name, cb, *args):
        wl = self._watchers.get(name)
        if wl is None:
            self._watchers[name] = wl = []
        wl.append((cb, args))

    def RedrawFull(self):
        self.Redraw(pymui.MADF_DRAWOBJECT)

    def RedrawDamaged(self):
        self.Redraw(pymui.MADF_DRAWUPDATE)

    def MCC_AskMinMax(self, minw, defw, maxw, minh, defh, maxh):
        return minw, defw+320, maxw+10000, minh, defh+320, maxh+10000

    def MCC_Setup(self):
        self._ev.install(self, pymui.IDCMP_RAWKEY | pymui.IDCMP_MOUSEBUTTONS)
        return True

    def MCC_Cleanup(self):
        self._ev.uninstall()

    def MCC_HandleEvent(self, evt):
        wl = self._watchers.get(Raster.EVENTMAP.get(evt.Class), [])
        for cb, args in wl:
            return cb(evt, *args)

    def MCC_Draw(self, flags):
        # Draw full raster
        if flags & pymui.MADF_DRAWOBJECT:
            self._draw_area(self.MLeft, self.MTop, self.MRight, self.MBottom)

        # Draw only damaged area
        elif flags & pymui.MADF_DRAWUPDATE:
            # Redraw damaged rectangles
            for rect in self._damaged:
                self._draw_area(*rect)
            self._damaged = []

            # Redraw damaged buffers
            self._draw_buffers(self._damagedbuflist)
            self._damagedbuflist = []

    def _draw_area(self, *bbox):
        a, b = self.GetSurfacePos(*bbox[:2])
        c, d = self.GetSurfacePos(*bbox[2:])
        self._draw_buffers(self.model.GetRenderBuffers(a, b, c, d))

    def _draw_buffers(self, buflist):
        for buf in buflist:
            pos = (buf.x, buf.y) # saved because CMS return a new buffer object
            buf = self.CMS_ApplyTransform(buf) # do color management (for Christoph ;-))
            rx, ry = self.GetRasterPos(*pos)

            # Dumb scale math (like int(buf.Width * self._scale)) causes bad tile size
            # so some lines are not filled => bad result
            #
            # To be sure of the raster size to draw we start from the tile (x, y)
            # and we use the start of the tile at (+1, +1) to compute the size
            #
            rx2, ry2 = self.GetRasterPos(pos[0]+buf.Width, pos[1]+buf.Height)
            
            self._rp.ScaledBlit8(buf, buf.Width, buf.Height, rx, ry, rx2-rx, ry2-ry)

            if self.debug:
                self._rp.Rect(3, rx, ry, rx2, ry2)
                if not buf.ro:
                    self._rp.Rect(4, rx+1, ry+1, rx2-1, ry2-1)

    def AddDamagedBuffer(self, buffer):
        if hasattr(buffer, '__iter__'):
            self._damagedbuflist += buffer
        else:
            self._damagedbuflist.append(buffer)

    def ClearDamaged(self):
        self._damaged = []
        self._damagedbuflist = []

    def AddDamagedRect(self, *bbox):
        self._damaged.append(bbox)

    damaged = property(fget=lambda self: iter(self._damaged), fdel=ClearDamaged)

    def EnableMouseMoveEvents(self, state=True):
        self._ev.uninstall()
        if state:
            idcmp = self._ev.idcmp | pymui.IDCMP_MOUSEMOVE
        else:
            idcmp = self._ev.idcmp & ~pymui.IDCMP_MOUSEMOVE
        self._ev.install(self, idcmp)

    def GetSurfacePos(self, x, y):
        return int((x - self.MLeft - self.osx) / self._scale), int((y - self.MTop - self.osy) / self._scale)

    def GetRasterPos(self, x, y):
        return int(x * self._scale) + self.MLeft + self.osx, int(y * self._scale) + self.MTop + self.osy

    def StartMove(self):
        "Save view state"
        self._saved_osx = self.osx
        self._saved_osy = self.osy
        self._saved_scale = self._scale

    def CancelMove(self):
        "Restore previously saved view state"
        self.osx = self._saved_osx 
        self.osy = self._saved_osy
        self._scale = self._saved_scale
        self.RedrawFull()
        
    def Scroll(self, dx, dy):
        """Scroll(dx, dy)

        Scroll current displayed surface using pixel vector (dx, dy).
        ATTENTION: doesn't do any display refresh.
        """

        self.osx -= dx
        self.osy -= dy

        a, b, c, d = self.MLeft, self.MTop, self.MRight, self.MBottom
        self._rp.Scroll(dx, dy, a, b, c, d)

        ## Compute the damaged rectangles list...
        # 4 damaged rectangles, but only two for one (dx, dy):
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

        if dx < 0:
            if dy <= 0:
                self.AddDamagedRect(a, b-dy, a-dx, d) #1
            else:
                self.AddDamagedRect(a, b, a-dx, d-dy) #1
        elif dx > 0:
            if dy <= 0:
                self.AddDamagedRect(c-dx, b, c, d-dy) #2
            else:
                self.AddDamagedRect(c-dx, b-dy, c, d) #2
                
        if dy < 0:
            self.AddDamagedRect(a, b, c, b-dy) #3
        elif dy > 0:
            self.AddDamagedRect(a, d-dy, c, d) #4

    def CenterOnSurfacePoint(self, *pos):
        x, y = self.GetRasterPos(*pos)
        self.osx += self.MLeft + self.MWidth/2 - x
        self.osy += self.MTop +self.MHeight/2 - y

    ##############################
    ## Color Management Methods ##

    def EnableCMS(self, enabled=True):
        self.cms_transform = self._cms_th if enabled else self._DummyCMSTransform

    def _DummyCMSTransform(self, buf, *a):
        return buf

    def CMS_SetInputProfile(self, profile):
        self.cms_ip = profile

    def CMS_SetOutputProfile(self, profile):
        self.cms_op = profile

    def CMS_InitTransform(self):
        self._cms_th = lcms.TransformHandler(self.cms_ip, lcms.TYPE_RGB_8,
                                             self.cms_op, lcms.TYPE_RGB_8,
                                             lcms.INTENT_PERCEPTUAL)

    def CMS_ApplyTransform(self, buf):
        if self._tmpbuf is None:
            self._tmpbuf = buf.copy()
        return self.cms_transform(buf, self._tmpbuf, buf.Width * buf.Height)
