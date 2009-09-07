from pymui import Rectangle
from array import array

T_SIZE = 16

class Tile:
    def __init__(self):
        self.buffer = array('H', '\0' * 4*T_SIZE**2)

class Surface(Rectangle):
    def __init__(self):
        super(Surface, self).__init__()
        self.scale = 1.0
        self.rot   = 0.0

class TiledSurface(Surface):
    def __init__(self):
        super(TiledSurface, self).__init__()
        self.tiles = {}

    def GetTileBuffer(self, *p):
        "Returns the tiles containing the point p=(x, y)"

        assert len(p) == 2

        tile = self.tiles.get(p)
        if tile:
            return tile
        else:
            tile = Tile()
            self.tiles[p] = tile
            return tile.buffer

    def RenderRegion(self, x, y, width, height):
        self.SetRegion(x, y, width, height)
        for j in xrange(y, y+width, T_SIZE):
            for i in xrange(x, x+width, T_SIZE):
                buf = self.GetTileBuffer(i, j)
                self.DrawBuffer(buf, i, j)
