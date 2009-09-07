from pymui import Rectangle
from array import array

T_SIZE = 16
DEBUG = True

class Tile:
    def __init__(self):
        # RGBA buffer, 15bits per conmposants
        self.rgba15 = array('H', '\0' * 4*T_SIZE**2)

    def get_rgba8(self):
        # TODO!
        return None

if DEBUG:
    red_rgba8 = array('B', '\xFF\x00\x00\x00' * T_SIZE**2)
    green_rgba8 = array('B', '\x00\xFF\x00\x00' * T_SIZE**2)
    blue_rgba8 = array('B', '\x00\x00\xFF\x00' * T_SIZE**2)

class Surface(Rectangle):
    def __init__(self):
        super(Surface, self).__init__()
        self.scale = 1.0
        self.sx = 0.0
        self.sy = 0.0

class TiledSurface(Surface):
    def __init__(self):
        super(TiledSurface, self).__init__()
        self.tiles = {}

    def GetTileBuffer(self, create=False, *p):
        """GetTileBuffer(x, y, create=False) -> Tile buffer

        Returns the tile buffer containing the point p=(x, y).
        If no tile exist yet, return None if create is False,
        otherwhise create a new tile and returns it.
        """

        assert len(p) == 2

        tile = self.tiles.get(p)
        if tile:
            return tile
        elif create:
            tile = Tile()
            self.tiles[p] = tile
            return tile.buffer

    def Render(self, sx, sy, rx, rh, rw, rh):
        # point (sx, sy) gives the position in the surface of the raster origin
        # (rx, ry) => Blit start position in the raster (pixels)
        # (rw, rh) => Blit size in the raster (pixels)

        raster = self._get_raster()
        ts = T_SIZE*self.scale

        # Loop on all tiles visible through the raster
        for j in xrange(0, (rh + self.scale) / self.scale, T_SIZE):
            ty = int(j*self.scale)
            for i in xrange(0, (rw + self.scale) / self.scale, T_SIZE):
                tx = int(i*self.scale)
                if DEBUG:
                    if i+j == 0:
                        buf = red_rgba8
                    elif (i+j) % (T_SIZE * 2) == 0:
                        buf = green_rgba8
                    else:
                        buf = blue_rgba8
                    raster.ScaledBlit8(buf, T_SIZE, T_SIZE, rx + tx, ry + ty, ts, ts)
                else:
                    buf = self.GetTileBuffer(sx + i, sy + j)
                    if buf:
                        raster.ScaledBlit15(buf, T_SIZE, T_SIZE, rx + tx, ry + ty, ts, ts)
