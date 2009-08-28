#include <Python.h>

#include <private/mui2intuition/mui.h>
#include <libraries/mui.h>
#include <utility/hooks.h>

#undef USE_INLINE_STDARG
#include <clib/alib_protos.h>
#include <proto/muimaster.h>
#include <proto/intuition.h>
#define USE_INLINE_STDARG

#define INIT_HOOK(h, f) { struct Hook *_h = (struct Hook *)(h); \
    _h->h_Entry = (APTR) HookEntry; \
    _h->h_SubEntry = (APTR) (f); }

extern struct Library *PythonBase;
extern void dprintf(char*fmt, ...);

struct NotifySlot {
    PyObject *cb;
    PyObject *cb_args;
};

static struct Hook notify_hook;

//+ on_notify
static void on_notify(struct Hook *hook, Object *caller, ULONG *args)
{
    struct NotifySlot *slot = (APTR)args[0];
    PyObject *o;

    /* Because we never remove a notification, when the notification object is destroyed
     * this cause the cb and cb_args object to be Py_DECREF'ed. 
     * Only the slot variable is keeped in memory until the Py_Finalize().
     */
    if (NULL == slot->cb) return;

    //dprintf("call cb %p, args %p\n", slot->cb, slot->cb_args);
    o = PyObject_CallObject(slot->cb, slot->cb_args); /* NR */
    Py_XDECREF(o);

    /* in case of Python exception, the PyErr_Occurred() in the mainloop will catch it */
}
//-
//+
static void free_nslot(void *p)
{
    struct NotifySlot *slot = p;

    Py_CLEAR(slot->cb);
    Py_CLEAR(slot->cb_args);

    /* I don't call PyMem_Free() on slot because we want to keep it alive unil the end of the module
     * I hope that this doesn't cause memory waste.
     */
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
    PyObject *pyo, *cb, *cb_args;
    Object *mo;
    ULONG attr, trig;
    struct NotifySlot *slot;

    if (!PyArg_ParseTuple(args, "O!kkOO!:get", &PyCObject_Type, &pyo, &attr, &trig, &cb, &PyTuple_Type, &cb_args)) /* BR */
        return NULL;

    if (!PyCallable_Check(cb))
        return PyErr_Format(PyExc_TypeError, "object %s is not callable", cb->ob_type->tp_name);

    mo = PyCObject_AsVoidPtr(pyo);
    assert(NULL != mo);

    slot = PyMem_Malloc(sizeof(struct NotifySlot));
    if (NULL == slot)
        return PyErr_NoMemory();

    Py_INCREF(cb);
    Py_INCREF(cb_args);
    slot->cb = cb;
    slot->cb_args = cb_args;

    self = PyCObject_FromVoidPtr(slot, free_nslot);
    if (NULL == self) {
        Py_DECREF(cb);
        Py_DECREF(cb_args);
        PyMem_Free(slot);
        return NULL;
    }

    dprintf("New notify: obj=%p, attr=0x%08x, trig=0x%08x, cb=%p\n", mo, attr, trig, cb);
    DoMethod(mo, MUIM_Notify, attr, trig, MUIV_Notify_Self, 3, MUIM_CallHook, &notify_hook, slot);
    return self;
}
//-

//+ _MUIMethods
static PyMethodDef _MUIMethods[] = {
    {"add_member", mui_add_member, METH_VARARGS, NULL},
    {"mainloop", (PyCFunction)mui_mainloop, METH_O, NULL},
    {"set", mui_set, METH_VARARGS, NULL},
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
