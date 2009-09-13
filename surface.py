from pymui import *
from array import array
import PIL.Image as image
import sys

sys.path.append('Libs/python2.5/site-packages')
import _surface

T_SIZE = 64
DEBUG = True

IECODE_UP_PREFIX = 0x80
IECODE_LBUTTON   = 0x68
IECODE_RBUTTON   = 0x69
IECODE_MBUTTON   = 0x6A

NM_WHEEL_UP      = 0x7a
NM_WHEEL_DOWN    = 0x7b

class Tile:
    def __init__(self):
        # RGBA buffer, 16-bits per conmposants but we'll using only 15 of them
        self.pixels = _surface.PixelArray(T_SIZE, T_SIZE, 4, 16)
        self.pixels.zero()

class Surface(Rectangle):
    def __init__(self):
        super(Surface, self).__init__(Background=MUII_SHINE,
                                      InnerTop=0,
                                      InnerLeft=0,
                                      InnerRight=0,
                                      InnerBottom=0,
                                      FillArea=False,
                                      MCC=True)
        self._clip = True # enable clipping during MCC_Draw
        self._scale = 1.0
        self.sx = 0.0
        self.sy = 0.0

        self.eh = EventHandler()
        self.move = 0

    def MCC_Draw(self, flags):
        if flags & MADF_DRAWOBJECT != MADF_DRAWOBJECT:
            return

        _surface.renderfull(self._mo, self.GetTileBuffer, T_SIZE, self.scale, self.sx, self.sy)

    def MCC_Setup(self):
        self.eh.install(self, IDCMP_MOUSEBUTTONS | IDCMP_RAWKEY)
        return True

    def MCC_Cleanup(self):
        self.eh.uninstall()

    def MCC_HandleEvent(self, evt):
        if evt.Class == IDCMP_MOUSEBUTTONS:
            self.OnMouseButton(evt.Code & IECODE_UP_PREFIX, evt.Code & ~IECODE_UP_PREFIX, evt)
        elif evt.Class == IDCMP_MOUSEMOVE:
            self.OnMouseMove(evt)
        elif evt.Class == IDCMP_RAWKEY:
            self.OnKeyEvent(evt.Code & IECODE_UP_PREFIX, evt.Code & ~IECODE_UP_PREFIX, evt)

    def SetScale(self, n):
        if n <= 0: return
        self._scale = n

    def ResetScale(self):
        self._scale = 1.0

    def OnMouseButton(self, up, bt, evt):
        if not up and bt in (IECODE_LBUTTON, IECODE_MBUTTON) and evt.InObject:
            self.omx = evt.MouseX
            self.omy = evt.MouseY
            if self.move == 0:
                idcmp = self.eh.idcmp | IDCMP_MOUSEMOVE  
                self.eh.uninstall()
                self.eh.install(self, idcmp)
            self.move = bt
        elif self.move and up and bt in (IECODE_LBUTTON, IECODE_MBUTTON):
            idcmp = self.eh.idcmp & ~IDCMP_MOUSEMOVE
            self.move = 0
            self.eh.uninstall()
            self.eh.install(self, idcmp)

    def OnMouseMove(self, evt):
        pass

    def OnKeyEvent(self, up, key, evt):
        redraw = False
        if evt.InObject and up:
            if key == NM_WHEEL_UP:
                self.scale += 0.05
                redraw = True
            elif key == NM_WHEEL_DOWN:
                self.scale -= 0.05
                redraw = True

        if redraw:
            self.Redraw(MADF_DRAWOBJECT)

    def ScreenToSurface(self, x, y):
        return ((x-self.MLeft) / self.scale) + self.sx, ((y-self.MTop) / self.scale) + self.sy

    scale = property(fget=lambda self: self._scale, fset=SetScale, fdel=ResetScale)

    def SetBackgroundImage(self, path):
        im = image.open(path)
        im.load()
        _, _, w, h = im.getbbox()
        self.ImportFromPILImage(im, w, h)
        self.Redraw(MADF_DRAWOBJECT)


class TiledSurface(Surface):
    def __init__(self):
        Surface.__init__(self)
        self.tiles = {}

    def GetTileBuffer(self, x, y, create=False):
        """GetTileBuffer(x, y, create=False) -> Tile buffer

        Returns the tile buffer containing the point p=(x, y).
        If no tile exist yet, return None if create is False,
        otherwhise create a new tile and returns it.
        """

        x = x // T_SIZE
        y = y // T_SIZE
        p = (x, y)

        tile = self.tiles.get(p)
        if tile:
            return tile.pixels
        elif create:
            tile = Tile()
            self.tiles[p] = tile
            return tile.pixels
    
    def ImportFromPILImage(self, im, w, h):
        im = im.convert('RGBA')
        src = _surface.PixelArray(T_SIZE, T_SIZE, 4, 8)
        for ty in xrange(0, h, T_SIZE):
            for tx in xrange(0, w, T_SIZE):
                buf = self.GetTileBuffer(tx, ty, create=True)
                buf.zero()
                sx = min(w, tx+T_SIZE)
                sy = min(h, ty+T_SIZE)
                src.from_string(im.crop((tx, ty, sx, sy)).tostring())
                buf.rgba8_to_rgba15x(src)

    def OnMouseMove(self, evt):
        if evt.ValidTD:
            mx = evt.td_NormTabletX * self.SRangeX
            my = evt.td_NormTabletY * self.SRangeY
        else:
            mx = evt.MouseX
            my = evt.MouseY
 
        if self.move == IECODE_LBUTTON:
            if evt.InObject:
                sx, sy = self.ScreenToSurface(mx, my)
                buf = self.GetTileBuffer(sx, sy, create=True)
        elif self.move == IECODE_MBUTTON:
            self.sx -= (mx - self.omx) / self.scale
            self.sy -= (my - self.omy) / self.scale
            self.Redraw(MADF_DRAWOBJECT)
            
        self.omx = mx
        self.omy = my
