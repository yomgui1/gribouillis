/******************************************************************************
Copyright (c) 2009-2011 Guillaume Roguez

Permission is hereby granted, free of charge, to any person
obtaining a copy of this software and associated documentation
files (the "Software"), to deal in the Software without
restriction, including without limitation the rights to use,
copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following
conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.
******************************************************************************/

#ifndef COMMON_H
#define COMMON_H

#include <Python.h>
#include <structmember.h>
#include <stdint.h>

#ifdef NDEBUG
#define D(x)
#else
#define D(x) x
#endif

#ifndef FALSE
#define FALSE 0
#endif

#ifndef TRUE
#define TRUE (!FALSE)
#endif

#ifndef MIN
#define MIN(a, b) ({typeof(a) _a=(a);typeof(b) _b=(b);_a<_b?_a:_b;})
#endif

#ifndef MAX
#define MAX(a, b) ({typeof(a) _a=(a);typeof(b) _b=(b);_a>_b?_a:_b;})
#endif

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

/* T_BOOL is present after >= 2.6 */
#ifndef T_BOOL
#define T_BOOL T_BYTE
#endif

#ifdef __MORPHOS__
#define PRINT_ERROR dprintf
#else
#define PRINT_ERROR printf
#define AllocVecTaskPooled malloc
#define FreeVecTaskPooled free
#endif

/* Implemented in platform dependent file */

typedef int RWLock; /* opaque structure */

extern RWLock *rwlock_create(void);
extern int rwlock_destroy(RWLock *);
extern int rwlock_lock_read(RWLock *, int);
extern int rwlock_lock_write(RWLock *, int);
extern void rwlock_unlock(RWLock *);


#endif /* COMMON_H */
