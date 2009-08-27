#include <Python.h>

#include <private/mui2intuition/mui.h>
#include <libraries/mui.h>

#undef USE_INLINE_STDARG
#include <clib/alib_protos.h>
#include <proto/muimaster.h>
#include <proto/intuition.h>
#define USE_INLINE_STDARG

//+ mui_add_member
static PyObject *mui_add_member(PyObject *self, PyObject *args)
{
    PyObject *pyo1, *pyo2;

    if (!PyArg_ParseTuple(args, "O!O!:add_member", &PyCObject_Type, &pyo1, &PyCObject_Type, &pyo2)) /* BR */
        return NULL;

    DoMethod(PyCObject_AsVoidPtr(pyo1), OM_ADDMEMBER, PyCObject_AsVoidPtr(pyo2));

    Py_RETURN_NONE;
}
//-
//+ mui_mainloop
static PyObject *mui_mainloop(PyObject *pyo)
{
    BOOL run = TRUE;
    LONG sigs;
    Object *app;

    if (!PyCObject_Check(pyo)) {
        PyErr_SetString(PyExc_TypeError, "mainloop needs a Application MUI CObject as argument");
        return NULL;
    }

    app = PyCObject_AsVoidPtr(pyo);

    while (run) {
        ULONG id = DoMethod(app, MUIM_Application_Input, &sigs);

        switch (id) {
            case MUIV_Application_ReturnID_Quit:
                run = FALSE;
                break;
        }

        if (PyErr_Occurred())
            break;

        if (run && sigs) Wait(sigs);
    }

    Py_RETURN_NONE;
}
//-
//+ mui_set
static PyObject *mui_set(PyObject *self, PyObject *args)
{
    PyObject *pyo;
    ULONG method, value;
    LONG res;

    if (!PyArg_ParseTuple(args, "O!kk:set", &PyCObject_Type, &pyo, &method, &value)) /* BR */
        return NULL;

    res = set(PyCObject_AsVoidPtr(pyo), method, value);
    return PyInt_FromLong(res);
}
//-
//+ mui_get
static PyObject *mui_get(PyObject *self, PyObject *args)
{
    PyObject *pyo;
    ULONG method, value;
    STRPTR fmt;
    LONG res;

    if (!PyArg_ParseTuple(args, "O!ks:get", &PyCObject_Type, &pyo, &method, &fmt)) /* BR */
        return NULL;

    res = get(PyCObject_AsVoidPtr(pyo), method, &value);
    if (!res)
        return PyErr_Format(PyExc_SystemError, "MUI get(%p) failed", method);
        
    return Py_BuildValue(fmt, value);
}
//-

//+ MuiMethods
static PyMethodDef _MUIMethods[] = {
    {"add_member", mui_add_member, METH_VARARGS, NULL},
    {"mainloop", (PyCFunction)mui_mainloop, METH_NOARGS, NULL},
    {"set", mui_set, METH_VARARGS, NULL},
    {"get", mui_get, METH_VARARGS, NULL},

    {0}
};
//-

//+ init_muimodule
void init_muimodule(void)
{
    Py_InitModule("_mui", _MUIMethods);
}
//-
