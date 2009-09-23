#ifndef _PIXARRAYMODULE_H

#ifndef _PIXARRAY_CORE

PyTypeObject *PyPixelArray_Type;
#define PyPixelArray_Check(op) PyObject_TypeCheck(op, PyPixelArray_Type)
#define PyPixelArray_CheckExact(op) ((op)->ob_type == PyPixelArray_Type)

#else

static PyTypeObject PyPixelArray_Type;
#define PyPixelArray_Check(op) PyObject_TypeCheck(op, &PyPixelArray_Type)
#define PyPixelArray_CheckExact(op) ((op)->ob_type == &PyPixelArray_Type)

#endif

typedef struct PyPixelArray_STRUCT {
    PyObject_HEAD

    LONG  x, y;          /* Buffers positions */
    UWORD width, height; /* Pixels array size */
    UBYTE nc;            /* Number of components per pixels */
    UBYTE bpc;           /* Number of bits for each components */
    ULONG bpr;           /* Number of bytes per row */
    UBYTE damaged;       /* True if written but not displayed */
    APTR  data;          /* Pixels data */
} PyPixelArray;

#endif /* _PIXARRAYMODULE_H */
