#include "common.h"
#include "surface_mcc.h"

//+ add_constants
static int add_constants(PyObject *m)
{
    INSL(m, "MA_Surface_MotionEvent", MA_Surface_MotionEvent);
    
    return 0;
}
//-

typedef struct PyMotionEvent_STRUCT {
    PyObject_HEAD

    struct SurfaceST_MotionEvent mevt;
} PyMotionEvent;

static PyMemberDef event_members[] = {
    {"X", T_LONG, offsetof(PyMotionEvent, mevt.X), RO, NULL},
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

//+ methods
static PyMethodDef methods[] = {
    {"get_eventmotion", (PyCFunction)mod_geteventmotion, METH_O, NULL},
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
