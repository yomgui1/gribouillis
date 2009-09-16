/******************************************************************************
Copyright (c) 2009 Guillaume Roguez

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

#include "common.h"

#include <cybergraphx/cybergraphics.h>

#include <proto/graphics.h>
#include <proto/cybergraphics.h>

#define PyPixelArray_Check(op) PyObject_TypeCheck(op, &PyPixelArray_Type)
#define PyPixelArray_CheckExact(op) ((op)->ob_type == &PyPixelArray_Type)

#define CACHE_SIZE 16

typedef struct PyPixelArray_STRUCT {
    PyObject_HEAD

    UWORD width, height; /* Pixels array size */
    UBYTE nc;            /* Number of components per pixels */
    UBYTE bpc;           /* Number of bits for each components */
    ULONG bpr;           /* Number of bytes per row */
    APTR  data;          /* Pixels data */
} PyPixelArray;

static struct Library *CyberGfxBase;
static PyTypeObject PyPixelArray_Type;


/*******************************************************************************************
** Private routines
*/

/* About color format in buffers.
 *
 * Pixels colors are stored as 4 components (ARGB) using fixed point encoding.
 * So the floating point range [0.0, 1.0] is converted into integer range [0, 2**15].
 * Using 2**15 than a more natural 2**16 value gives the way to store the 1.0 value
 * into a short integer (16bits) and permit to use a logical shift operation of 15 bits,
 * when we need to multiply/divide values in fixed-point arithmetic computations.
 *
 * In all the application I'll note argb15x a ARGB pixel buffer using this convention.
 */

//+ argb15x_to_argb8
static void
argb15x_to_argb8(USHORT *src, UBYTE *dst, UWORD w, UWORD h)
{
    ULONG i, n = w * h;

    for (i=0; i < n; i++) {
        dst[0] = (ULONG)src[0] * 255 >> 15;
        dst[1] = (ULONG)src[1] * 255 >> 15;
        dst[2] = (ULONG)src[2] * 255 >> 15;
        dst[3] = (ULONG)src[3] * 255 >> 15;
        
        src += 4;
        dst += 4;
    }
}
//-
//+ argb15x_to_rgb8
static void
argb15x_to_rgb8(USHORT *src, UBYTE *dst, UWORD w, UWORD h)
{
    ULONG i, n = w * h;

    for (i=0; i < n; i++) {
        ULONG alpha = src[0];

        dst[1] = (ULONG)src[0] * 255 / alpha;
        dst[2] = (ULONG)src[1] * 255 / alpha;
        dst[3] = (ULONG)src[2] * 255 / alpha;
        
        dst += 3;
        src += 4;
    }
}
//-
//+ argb8_to_argb15x
static void
argb8_to_argb15x(UBYTE *src, USHORT *dst, UWORD w, UWORD h)
{
    ULONG i, n = w * h;

    for (i=0; i < n; i++) {
        USHORT alpha = ((ULONG)src[0] << 15) / 255;
        
        dst[0] = alpha;
        dst[1] = (ULONG)src[1] * alpha / 255;
        dst[2] = (ULONG)src[2] * alpha / 255;
        dst[3] = (ULONG)src[3] * alpha / 255;

        src += 4;
        dst += 4;
    }
}
//-
//+ rgb8_to_argb15x
static void
rgb8_to_argb15x(UBYTE *src, USHORT *dst, UWORD w, UWORD h)
{
    ULONG i, n = w * h;

    for (i=0; i < n; i++) {
        dst[0] = 1 << 15;
        dst[1] = ((ULONG)src[0] << 15) / 255;
        dst[2] = ((ULONG)src[1] << 15) / 255;
        dst[3] = ((ULONG)src[2] << 15) / 255;

        src += 3;
        dst += 4;
    }
}
//-
//+ rgb8_to_argb8
static void
rgb8_to_argb8(UBYTE *src, UBYTE *dst, UWORD w, UWORD h)
{
    ULONG i, n = w * h;

    for (i=0; i < n; i++) {
        dst[0] = 255;
        dst[1] = src[0];
        dst[2] = src[1];
        dst[3] = src[2];

        src += 3;
        dst += 4;
    }
}
//-
//+ blit_overalpha_argb15x_to_rgb8
static void
blit_overalpha_argb15x_to_rgb8(USHORT *src, UBYTE *dst, UWORD w, UWORD h)
{
    ULONG i, n = w * h;

    // src is a argb15x with alpha pre-multiplied rgb values.
    // dst is not alpha premul.

    for (i=0; i < n; i++) {
        // DestAlpha = 1.0 (full opaque surface)
        // Dest[x] = Src[x] + (1.0 - SrcAlpha) * Dst[x]
        ULONG alpha = src[0];
        ULONG one_minus_alpha = (1 << 15) - alpha;

        dst[1] = (ULONG)src[1] * 255 / alpha + (one_minus_alpha * dst[1] >> 15);
        dst[2] = (ULONG)src[2] * 255 / alpha + (one_minus_alpha * dst[2] >> 15);
        dst[3] = (ULONG)src[3] * 255 / alpha + (one_minus_alpha * dst[3] >> 15);

        src += 4;
        dst += 3;
    }
}
//-


/*******************************************************************************************
** PyPixelArray_Type
*/

//+ pixarray_new
static PyObject *
pixarray_new(PyTypeObject *type, PyObject *args)
{
    PyPixelArray *self;
    UWORD w, h;
    UBYTE nc, bpc;

    if (!PyArg_ParseTuple(args, "HHBB:__new__", &w, &h, &nc, &bpc)) /* BR */
        return NULL;

    if (nc > 4)
        return PyErr_Format(PyExc_ValueError, "PixelArray support 4 composants at maximum, not %u", nc);

    if (bpc > 32)
        return PyErr_Format(PyExc_ValueError, "PixelArray support 32 bits per composant at maximum, not %u", bpc);

    if ((nc * bpc) % 8)
        return PyErr_Format(PyExc_ValueError, "PixelArray needs the number of components by the number of bit per component aligned on byte size");
 

    self = (PyPixelArray *)type->tp_alloc(type, 0); /* NR */
    if (NULL != self) {
        self->bpr = w * ((bpc * nc) >> 3); 
        self->data = PyMem_Malloc(self->bpr * h);
        if (NULL != self->data) {
            self->width = w;
            self->height = h;
            self->nc  = nc;
            self->bpc = bpc;
            return (PyObject *)self;
        }

        Py_DECREF((PyObject *)self);
    }

    return NULL;
}
//-
//+ pixarray_dealloc
static void
pixarray_dealloc(PyPixelArray *self)
{
    PyMem_Free(self->data);
    self->ob_type->tp_free((PyObject *)self);
}
//-
//+ pixarray_getsegcount
static Py_ssize_t
pixarray_getsegcount(PyPixelArray *self, Py_ssize_t *lenp)
{
    if (NULL != lenp)
        *lenp = self->bpr * self->height;
    return 1;
}
//-
//+ pixarray_getbuffer
static Py_ssize_t
pixarray_getbuffer(PyPixelArray *self, Py_ssize_t segment, void **ptrptr)
{
    if (segment != 0) {
        PyErr_SetString(PyExc_TypeError, "Only segment 0 is allowed");
        return -1;
    }

    *ptrptr = self->data;
    return self->bpr * self->height;
}
//-
//+ pixarray_zero
static PyObject *
pixarray_zero(PyPixelArray *self)
{
    memset(self->data, 0, self->bpr * self->height);
    Py_RETURN_NONE;
}
//-
//+ pixarray_one
static PyObject *
pixarray_one(PyPixelArray *self)
{
    memset(self->data, 0xff, self->bpr * self->height);
    Py_RETURN_NONE;
}
//-
//+ pixarray_from_string
static PyObject *
pixarray_from_string(PyPixelArray *self, PyObject *arg)
{
    Py_ssize_t len;

    if (PyString_CheckExact(arg)) {
        len = MIN(PyString_GET_SIZE(arg), self->bpr * self->height);
        CopyMem(PyString_AS_STRING(arg), self->data, len);
    
    } else if (PyObject_CheckReadBuffer(arg)) {
        APTR buf;
        
        PyObject_AsReadBuffer(arg, (const void **)&buf, &len);
        
        len = MIN(len, self->bpr * self->height);
        CopyMem(buf, self->data, len);
    } else
        return PyErr_Format(PyExc_TypeError, "str or buffer object needed as first argument, not %s", OBJ_TNAME(arg));
    
    Py_RETURN_NONE;
}
//-
//+ pixarray_from_pixarray
static PyObject *
pixarray_from_pixarray(PyPixelArray *self, PyObject *arg)
{
    PyPixelArray *src;
    Py_ssize_t len;

    if (!PyPixelArray_Check(arg))
        return PyErr_Format(PyExc_TypeError, "instance of PixelArray waited as first argument, not %s", OBJ_TNAME(arg));
    
    src = (APTR)arg;
    len = MIN(self->bpr * self->height, src->bpr * src->height);
    CopyMem(src->data, self->data, len);

    Py_RETURN_NONE;
}
//-

static struct PyMethodDef pixarray_methods[] = {
    {"zero", (PyCFunction)pixarray_zero, METH_VARARGS, NULL},
    {"one", (PyCFunction)pixarray_one, METH_VARARGS, NULL},
    {"from_string", (PyCFunction)pixarray_from_string, METH_O, NULL},
    {"from_pixarray", (PyCFunction)pixarray_from_pixarray, METH_O, NULL},
    {NULL} /* sentinel */
};

static PyMemberDef pixarray_members[] = {
    {"Width", T_USHORT, offsetof(PyPixelArray, width), RO, NULL},
    {"Height", T_USHORT, offsetof(PyPixelArray, height), RO, NULL},
    {"BytesPerRow", T_ULONG, offsetof(PyPixelArray, bpr), RO, NULL},
    {"ComponentNumber", T_UBYTE, offsetof(PyPixelArray, nc), RO, NULL},
    {"BitsPerComponent", T_UBYTE, offsetof(PyPixelArray, bpc), RO, NULL},
    {"DataAddress", T_ULONG, offsetof(PyPixelArray, data), RO, NULL},
    {NULL}
};

static PyBufferProcs pixarray_as_buffer = {
    bf_getreadbuffer  : (getreadbufferproc)pixarray_getbuffer,
    bf_getwritebuffer : (getwritebufferproc)pixarray_getbuffer,
    bf_getsegcount    : (getsegcountproc)pixarray_getsegcount,
};

static PyTypeObject PyPixelArray_Type = {
    PyObject_HEAD_INIT(NULL)

    tp_name         : "_surface.PixelArray",
    tp_basicsize    : sizeof(PyPixelArray),
    tp_flags        : Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    tp_doc          : "PixelArray Objects",

    tp_new          : (newfunc)pixarray_new,
    tp_dealloc      : (destructor)pixarray_dealloc,
    tp_methods      : pixarray_methods,
    tp_members      : pixarray_members,
    tp_as_buffer    : &pixarray_as_buffer,
};


/*******************************************************************************************
** Module
*/

//+ mod_rgb8_to_argb8
static PyObject *
mod_rgb8_to_argb8(PyObject *self, PyObject *args)
{
    PyPixelArray *src, *dst;

    if (!PyArg_ParseTuple(args, "O!O!", &src, &PyPixelArray_Type, &dst, &PyPixelArray_Type))
        return NULL;

    if ((src->nc != 3) || (src->bpc != 8))
        return PyErr_Format(PyExc_TypeError, "Incompatible source PixelArray object");

    if ((dst->nc != 4) || (dst->bpc != 8))
        return PyErr_Format(PyExc_TypeError, "Incompatible destination PixelArray object");

    if ((src->width != dst->width) || (src->height != dst->height))
        return PyErr_Format(PyExc_TypeError, "Incompatible dimensions between given PixelArray objects");

    rgb8_to_argb8(src->data, dst->data, dst->width, dst->height);

    Py_RETURN_NONE;
}
//-
//+ mod_rgb8_to_argb15x
static PyObject *
mod_rgb8_to_argb15x(PyObject *self, PyObject *args)
{
    PyPixelArray *src, *dst;

    if (!PyArg_ParseTuple(args, "O!O!", &src, &PyPixelArray_Type, &dst, &PyPixelArray_Type))
        return NULL;

    if ((src->nc != 3) || (src->bpc != 8))
        return PyErr_Format(PyExc_TypeError, "Incompatible source PixelArray object");

    if ((dst->nc != 4) || (dst->bpc != 16))
        return PyErr_Format(PyExc_TypeError, "Incompatible destination PixelArray object");

    if ((src->width != dst->width) || (src->height != dst->height))
        return PyErr_Format(PyExc_TypeError, "Incompatible dimensions between given PixelArray objects");

    rgb8_to_argb15x(src->data, dst->data, dst->width, dst->height);

    Py_RETURN_NONE;
}
//-
//+ mod_argb8_to_argb15x
static PyObject *
mod_argb8_to_argb15x(PyObject *self, PyObject *args)
{
    PyPixelArray *src, *dst;

    if (!PyArg_ParseTuple(args, "O!O!", &src, &PyPixelArray_Type, &dst, &PyPixelArray_Type))
        return NULL;

    if ((src->nc != 4) || (src->bpc != 8))
        return PyErr_Format(PyExc_TypeError, "Incompatible source PixelArray object");

    if ((dst->nc != 4) || (dst->bpc != 16))
        return PyErr_Format(PyExc_TypeError, "Incompatible destination PixelArray object");

    if ((src->width != dst->width) || (src->height != dst->height))
        return PyErr_Format(PyExc_TypeError, "Incompatible dimensions between given PixelArray objects");

    argb8_to_argb15x(src->data, dst->data, dst->width, dst->height);

    Py_RETURN_NONE;
}
//-
//+ mod_bltalpha_argb15x_to_rgb8
static PyObject *
mod_bltalpha_argb15x_to_rgb8(PyObject *self, PyObject *args)
{
    PyPixelArray *src, *dst;

    if (!PyArg_ParseTuple(args, "O!O!", &src, &PyPixelArray_Type, &dst, &PyPixelArray_Type))
        return NULL;

    if ((src->nc != 4) || (src->bpc != 16))
        return PyErr_Format(PyExc_TypeError, "Incompatible source PixelArray object");

    if ((dst->nc != 3) || (dst->bpc != 8))
        return PyErr_Format(PyExc_TypeError, "Incompatible destination PixelArray object");

    if ((src->width != dst->width) || (src->height != dst->height))
        return PyErr_Format(PyExc_TypeError, "Incompatible dimensions between given PixelArray objects");

    blit_overalpha_argb15x_to_rgb8(src->data, dst->data, dst->width, dst->height);

    Py_RETURN_NONE;
}
//-

//+ methods
static PyMethodDef methods[] = {
    {"rgb8_to_argb8", (PyCFunction)mod_rgb8_to_argb8, METH_VARARGS, NULL},
    {"rgb8_to_argb15x", (PyCFunction)mod_rgb8_to_argb15x, METH_VARARGS, NULL},
    {"argb8_to_argb15x", (PyCFunction)mod_argb8_to_argb15x, METH_VARARGS, NULL},
    {"bltalpha_argb15x_to_rgb8", (PyCFunction)mod_bltalpha_argb15x_to_rgb8, METH_VARARGS, NULL},
    {0}
};
//-

//+ add_constants
static int add_constants(PyObject *m)
{
    return 0;
}
//-
//+ PyMorphOS_CloseModule
void
PyMorphOS_CloseModule(void) {

    if (NULL != CyberGfxBase) {
        CloseLibrary(CyberGfxBase);
        CyberGfxBase = NULL;
    }
}
//- PyMorphOS_CloseModule
//+ init_pixbuf
void init_pixbuf(void)
{
    PyObject *m;

    CyberGfxBase = OpenLibrary("cybergraphics.library", 50);
    if (NULL == CyberGfxBase)
        return;

    if (PyType_Ready(&PyPixelArray_Type) < 0) return;

    m = Py_InitModule("_pixbuf", methods);
    if (NULL == m)
        return;

    add_constants(m);

    ADD_TYPE(m, "PixelArray", &PyPixelArray_Type);
}
//-
