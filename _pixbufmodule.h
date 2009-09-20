#ifndef _PIXBUFMODULE_H

#define PyPixelArray_Check(op) PyObject_TypeCheck(op, &PyPixelArray_Type)
#define PyPixelArray_CheckExact(op) ((op)->ob_type == &PyPixelArray_Type)

typedef struct PyPixelArray_STRUCT {
    PyObject_HEAD

    LONG  x, y;          /* Buffers positions */
    UWORD width, height; /* Pixels array size */
    UBYTE nc;            /* Number of components per pixels */
    UBYTE bpc;           /* Number of bits for each components */
    ULONG bpr;           /* Number of bytes per row */
    APTR  data;          /* Pixels data */
} PyPixelArray;

#endif /* _PIXBUFMODULE_H */
