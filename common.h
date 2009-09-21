#ifndef COMMON_H
#define COMMON_H

#include <Python.h>
#include <structmember.h>

#include <private/mui2intuition/mui.h>
#include <libraries/mui.h>
#include <libraries/gadtools.h>
#include <utility/hooks.h>
#include <clib/macros.h>

#undef USE_INLINE_STDARG
#include <clib/alib_protos.h>
#include <proto/muimaster.h>
#include <proto/intuition.h>
#define USE_INLINE_STDARG

#ifndef MAKE_ID
#define MAKE_ID(a,b,c,d) ((ULONG) (a)<<24 | (ULONG) (b)<<16 | (ULONG) (c)<<8 | (ULONG) (d))
#endif

#ifdef NDEBUG
#define D(x)
#else
#define D(x) x
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

#define MYTAGBASE (TAG_USER | 0x95fe0000)

#define OBJ_TNAME(o) (((PyObject *)(o))->ob_type->tp_name)
#define OBJ_TNAME_SAFE(o) ({                                            \
            PyObject *_o = (PyObject *)(o);                             \
            NULL != _o ? _o->ob_type->tp_name : "nil"; })

#define INSI(m, s, v) if (PyModule_AddIntConstant(m, s, v)) return -1
#define INSL(m, s, v) if (PyModule_AddObject(m, s, PyLong_FromUnsignedLong(v))) return -1
#define INSS(m, s, v) if (PyModule_AddStringConstant(m, s, v)) return -1

#define ADD_TYPE(m, s, t) {Py_INCREF(t); PyModule_AddObject(m, s, (PyObject *)(t));}

#define ADDVAFUNC(name, func, doc...) {name, (PyCFunction) func, METH_VARARGS ,## doc}
#define ADD0FUNC(name, func, doc...) {name, (PyCFunction) func, METH_NOARGS ,## doc}

#define SIMPLE0FUNC(fname, func) static PyObject * fname(PyObject *self){ func(); Py_RETURN_NONE; }
#define SIMPLE0FUNC_bx(fname, func, x) static PyObject * fname(PyObject *self){ return Py_BuildValue(x, func()); }
#define SIMPLE0FUNC_fx(fname, func, x) static PyObject * fname(PyObject *self){ return x(func()); }

#define CLAMP(v, min, max) ({                                   \
            typeof(v) _v = (v);                                 \
            typeof(min) _min = (min);                           \
            typeof(max) _max = (max);                           \
            (_v < _min) ? _min : ((_v > _max) ? _max : _v); })

extern struct Library *PythonBase;
extern void dprintf(char*fmt, ...);

#endif /* COMMON_H */
