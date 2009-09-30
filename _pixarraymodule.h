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

#define PyPixelArray_FLAG_RGB         (1<<0)
#define PyPixelArray_FLAG_CMYK        (1<<1)
#define PyPixelArray_FLAG_15X         (1<<2)
#define PyPixelArray_FLAG_8           (1<<3)
#define PyPixelArray_FLAG_ALPHA_FIRST (1<<31)
#define PyPixelArray_FLAG_ALPHA_LAST  (1<<30)

/* Used for load/save */
#define PyPixelArray_PIXFMT_RGB_8 (PyPixelArray_FLAG_RGB | PyPixelArray_FLAG_8)
#define PyPixelArray_PIXFMT_RGBA_8 (PyPixelArray_PIXFMT_RGB_8 | PyPixelArray_FLAG_ALPHA_LAST)
#define PyPixelArray_PIXFMT_CMYK_8 (PyPixelArray_FLAG_CMYK | PyPixelArray_FLAG_8)

/* Used for display */
#define PyPixelArray_PIXFMT_ARGB_8 (PyPixelArray_PIXFMT_RGB_8 | PyPixelArray_FLAG_ALPHA_FIRST)

/* Used for drawing */
#define PyPixelArray_PIXFMT_RGBA_15X (PyPixelArray_FLAG_RGB | PyPixelArray_FLAG_15X | PyPixelArray_FLAG_ALPHA_LAST)
#define PyPixelArray_PIXFMT_CMYKA_15X (PyPixelArray_FLAG_CMYK | PyPixelArray_FLAG_15X | PyPixelArray_FLAG_ALPHA_LAST)

typedef void (*writefunc)(APTR pixel, FLOAT opacity, APTR color);
typedef void (*colfloat2natif)(FLOAT from, APTR *to);
typedef FLOAT (*colnatif2float)(APTR from);

typedef struct PyPixelArray_STRUCT {
    PyObject_HEAD

    ULONG          pixfmt;        /* Pixel Format */
    LONG           x, y;          /* Buffers positions */
    UWORD          width, height; /* Pixels array size */
    UBYTE          damaged;       /* True if written but not displayed */
    UBYTE          nc;            /* Number of components per pixels */
    UBYTE          bpc;           /* Number of bits for each components */
    ULONG          bpr;           /* Number of bytes per row */
    colfloat2natif cfromfloat;    /* Function to convert a color channel value given in float to natif value */
    colnatif2float ctofloat;      /* Function to convert a color channel value given in natif to float value */
    writefunc      writepixel;    /* Function to change one pixel for given opacity and color */
    APTR           data;          /* Pixels data */
} PyPixelArray;

#endif /* _PIXARRAYMODULE_H */
