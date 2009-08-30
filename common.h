#ifndef COMMON_H
#define COMMON_H

#include <Python.h>
#include <structmember.h>

#include <private/mui2intuition/mui.h>
#include <libraries/mui.h>
#include <libraries/gadtools.h>
#include <utility/hooks.h>

#undef USE_INLINE_STDARG
#include <clib/alib_protos.h>
#include <proto/muimaster.h>
#include <proto/intuition.h>
#define USE_INLINE_STDARG

#ifndef MAKE_ID
#define MAKE_ID(a,b,c,d) ((ULONG) (a)<<24 | (ULONG) (b)<<16 | (ULONG) (c)<<8 | (ULONG) (d))
#endif

#ifndef DISPATCHER
#define DISPATCHER(Name) \
static ULONG Name##_Dispatcher(void); \
static struct EmulLibEntry GATE ##Name##_Dispatcher = { TRAP_LIB, 0, (void (*)(void)) Name##_Dispatcher }; \
static ULONG Name##_Dispatcher(void) { struct IClass *cl=(struct IClass*)REG_A0; Msg msg=(Msg)REG_A1; Object *obj=(Object*)REG_A2;
#define DISPATCHER_REF(Name) &GATE##Name##_Dispatcher
#define DISPATCHER_END }
#endif

#define INIT_HOOK(h, f) { struct Hook *_h = (struct Hook *)(h); \
    _h->h_Entry = (APTR) HookEntry; \
    _h->h_SubEntry = (APTR) (f); }

#define PYOBJECT2OBJECT(pyo) ({ \
    PyObject *_pyo = (PyObject *)(pyo); \
    Object *_mo = PyCObject_AsVoidPtr(_pyo); \
    if ((NULL == _mo) && !PyErr_Occurred()) \
        PyErr_SetString(PyExc_ValueError, "python C object not associated to a MUI object"); \
    _mo; })

#define MYTAGBASE (TAG_USER | 0x95fe0000)

#define INSI(m, s, v) if (PyModule_AddIntConstant(m, s, v)) return -1
#define INSL(m, s, v) if (PyModule_AddObject(m, s, PyLong_FromUnsignedLong(v))) return -1
#define INSS(m, s, v) if (PyModule_AddStringConstant(m, s, v)) return -1

extern struct Library *PythonBase;
extern void dprintf(char*fmt, ...);
extern Object *gApp;

#endif /* COMMON_H */
