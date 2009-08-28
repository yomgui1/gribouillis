#include "common.h"

//+
static inline void fill_ellipse(void *mem, int sx, int sy, int ex, int ey, int cx, int cy, float radx2, float rady2)
{
    int x, y;

    /* For all points (x,y) in the rectangle [S(sx,sy), E(ex,ey)] */
    for (y=sy; y <= ey; y++) {
        for (x=sx; x <= ex; x++) {
            float rx, ry;

            rx = (x - cx); rx *= rx;
            ry = (y - ry); ry *= ry;
            
            if ((rx < radx2) && (rady2))
        }
    }
}
//-

//+ _BrushMethods
static PyMethodDef _BrushMethods[] = {
    {0}
};
//-

//+ init_brushmodule
void init_brushmodule(void)
{
    Py_InitModule("_brush", _BrushMethods);
}
//-
