#include "common.h"

static struct Hook notify_hook;

//+ on_notify
static void on_notify(struct Hook *hook, Object *caller, ULONG *args)
{
    PyObject *obj;
    ULONG attr = args[0];
    ULONG value = args[1];

    obj = (APTR) muiUserData(caller);
    Py_XINCREF(obj);

    //printf("call notify on obj: %p, attr is 0x%08x\n", obj, attr);
    if (NULL != obj) {
        PyObject *res;

        res = PyObject_CallMethod(obj, "_notify_cb", "kk", attr, value); /* NR */
        Py_XDECREF(res);
    }

    Py_XDECREF(obj);

    /* in case of Python exception, the PyErr_Occurred() in the mainloop will catch it */
}
//-

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
static PyObject *mui_mainloop(PyObject *self, PyObject *pyo)
{
    BOOL run = TRUE;
    LONG sigs;
    Object *app;

    if (!PyCObject_Check(pyo)) {
        PyErr_SetString(PyExc_TypeError, "mainloop needs a Application MUI CObject as argument");
        return NULL;
    }

    app = PyCObject_AsVoidPtr(pyo);

    do {
        ULONG id = DoMethod(app, MUIM_Application_Input, &sigs);

        switch (id) {
            case MUIV_Application_ReturnID_Quit:
                run = FALSE;
                break;
        }

        if (PyErr_Occurred())
            break;

        if (run && sigs) {
            sigs = Wait(sigs|SIGBREAKF_CTRL_C);
            if (sigs & SIGBREAKF_CTRL_C)
                break;
        }
    } while (run);

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
//+ mui_nnset
static PyObject *mui_nnset(PyObject *self, PyObject *args)
{
    PyObject *pyo;
    ULONG method, value;
    LONG res;

    if (!PyArg_ParseTuple(args, "O!kk:nnset", &PyCObject_Type, &pyo, &method, &value)) /* BR */
        return NULL;

    res = nnset(PyCObject_AsVoidPtr(pyo), method, value);
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
//+ mui_notify
static PyObject *mui_notify(PyObject *self, PyObject *args)
{
    PyObject *obj, *pyo;
    Object *mo=NULL;
    ULONG attr, trig;

    if (!PyArg_ParseTuple(args, "OO!kk:mui_notify", &obj, &PyCObject_Type, &pyo, &attr, &trig)) /* BR */
        return NULL;

    mo = PYOBJECT2OBJECT(pyo);
    if (NULL == mo)
        return NULL;

    dprintf("New notify: obj=%p, attr=0x%08x, trig=0x%08x, obj=%p\n", mo, attr, trig, obj);  
    muiUserData(mo) = (ULONG) obj;
    
    DoMethod(mo, MUIM_Notify, attr, trig, MUIV_Notify_Self, 4, MUIM_CallHook, &notify_hook, attr, MUIV_TriggerValue);
    
    Py_RETURN_NONE;
}
//-

//+ _MUIMethods
static PyMethodDef _MUIMethods[] = {
    {"add_member", mui_add_member, METH_VARARGS, NULL},
    {"mainloop", (PyCFunction)mui_mainloop, METH_O, NULL},
    {"set", mui_set, METH_VARARGS, NULL},
    {"nnset", mui_nnset, METH_VARARGS, NULL},
    {"get", mui_get, METH_VARARGS, NULL},
    {"notify", mui_notify, METH_VARARGS, NULL},

    {0}
};
//-

//+ init_muimodule
void init_muimodule(void)
{
    INIT_HOOK(&notify_hook, on_notify);
    Py_InitModule("_mui", _MUIMethods);
}
//-
