#include "common.h"
#include "surface_mcc.h"

//+ add_constants
static int add_constants(PyObject *m)
{
    INSL(m, "MA_Surface_MotionEvent", MA_Surface_MotionEvent);
    INSL(m, "MA_Surface_LeftButtonPressed", MA_Surface_LeftButtonPressed);
    INSL(m, "PRESSURE_MAX", PRESSURE_MAX);
    
    return 0;
}
//-

//+ PyMotionEvent_Type
typedef struct PyMotionEvent_STRUCT {
    PyObject_HEAD

    struct SurfaceST_MotionEvent mevt;
} PyMotionEvent;

static PyMemberDef event_members[] = {
    {"X", T_LONG, offsetof(PyMotionEvent, mevt.X), RO, NULL},
    {"Y", T_LONG, offsetof(PyMotionEvent, mevt.Y), RO, NULL},
    {"AngleX", T_LONG, offsetof(PyMotionEvent, mevt.AngleX), RO, NULL},
    {"AngleY", T_LONG, offsetof(PyMotionEvent, mevt.AngleY), RO, NULL},
    {"RangeX", T_LONG, offsetof(PyMotionEvent, mevt.RangeX), RO, NULL},
    {"RangeY", T_LONG, offsetof(PyMotionEvent, mevt.RangeY), RO, NULL},
    {"Pressure", T_LONG, offsetof(PyMotionEvent, mevt.Pressure), RO, NULL},
    {"InProximity", T_BYTE, offsetof(PyMotionEvent, mevt.InProximity), RO, NULL},
    {"IsTablet", T_BYTE, offsetof(PyMotionEvent, mevt.IsTablet), RO, NULL},
    {NULL}  /* Sentinel */
};

PyTypeObject PyMotionEvent_Type = {
    PyObject_HEAD_INIT(NULL)

    tp_name         : "_surface.Event",
    tp_basicsize    : sizeof(PyMotionEvent),
    tp_flags        : Py_TPFLAGS_DEFAULT,
    tp_new          : PyType_GenericNew,

    tp_members      : event_members,
};
//-

//+ mod_geteventmotion
static PyObject *mod_geteventmotion(PyObject *self, PyObject *pyo)
{
    PyMotionEvent *obj;
    struct SurfaceST_MotionEvent *mevt;

    mevt = (APTR) PyLong_AsUnsignedLong(pyo);
    if (NULL == mevt) {
        PyErr_SetString(PyExc_ValueError, "Non zero long value waited");
        return NULL;
    }

    obj = PyObject_New(PyMotionEvent, &PyMotionEvent_Type); /* NR */
    if (NULL == obj) {
        if (!PyErr_Occurred())
            PyErr_SetString(PyExc_RuntimeError, "Unable to create new MotionEvent object");
        return NULL;
    }

    obj->mevt = *mevt;

    return (PyObject *)obj;
}
//-
//+ mod_draw
static PyObject *mod_draw(PyObject *self, PyObject *args)
{
    PyObject *pyo;
    Object *mo;
    LONG x, y, pressure;

    if (!PyArg_ParseTuple(args, "O!III:draw", &PyCObject_Type, &pyo, &x, &y, &pressure)) /* BR */
        return NULL;

    mo = PYOBJECT2OBJECT(pyo);
    if (NULL == mo)
        return NULL;

    DoMethod(mo, MM_Surface_Draw, x, y, pressure);

    Py_RETURN_NONE;
}
//-

//+ methods
static PyMethodDef methods[] = {
    {"get_eventmotion", (PyCFunction)mod_geteventmotion, METH_O, NULL},
    {"draw", (PyCFunction)mod_draw, METH_VARARGS, NULL},
    {0}
};
//-

//+ init_surfacemodule
void init_surfacemodule(void)
{
    PyObject *m;

    if (PyType_Ready(&PyMotionEvent_Type) < 0)
        return;

    m = Py_InitModule("_surface", methods);
    add_constants(m);

    Py_INCREF(&PyMotionEvent_Type);
    PyModule_AddObject(m, "MotionEvent", (PyObject *)&PyMotionEvent_Type);
}
//-
