#include "common.h"

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
