#include "common.h"

//+ draw_ellipse
static void fill_ellipse(void *mem, int sx, int sy, int ex, int ey, int cx, int cy, float radx2, float rady2)
{
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
