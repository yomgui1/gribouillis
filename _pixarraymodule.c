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

#define _PIXARRAY_CORE

#include "common.h"
#include "_pixarraymodule.h"

#include <cybergraphx/cybergraphics.h>

#include <proto/graphics.h>
#include <proto/cybergraphics.h>

#ifndef INITFUNC
#define INITFUNC init_pixarray
#endif

#ifndef MODNAME
#define MODNAME "_pixarray"
#endif

static struct Library *CyberGfxBase;

typedef struct PA_InitValue
{
    UBYTE          nc;
    UBYTE          bpc;
    colfloat2natif cfromfloat;
    colnatif2float ctofloat;
    writefunc      writepixel;
} PA_InitValue;

static void rgb8_writepixel(APTR, FLOAT, FLOAT, USHORT *);
static void argb8_writepixel(APTR, FLOAT, FLOAT, USHORT *);
static void rgba8_writepixel(APTR, FLOAT, FLOAT, USHORT *);
static void rgba15x_writepixel(APTR, FLOAT, FLOAT, USHORT *);
static void cmyk8_writepixel(APTR, FLOAT, FLOAT, USHORT *);
static void cmyka15x_writepixel(APTR, FLOAT, FLOAT, USHORT *);

static void rgb8_fromfloat(FLOAT, APTR *);
static void rgba15x_fromfloat(FLOAT, APTR *);

static FLOAT rgb8_tofloat(APTR);
static FLOAT rgba15x_tofloat(APTR);

static const PA_InitValue gInitValues[] = {
    {/*PyPixelArray_PIXFMT_RGB_8,*/     3, 8,  rgb8_fromfloat,    rgb8_tofloat,    rgb8_writepixel},
    {/*PyPixelArray_PIXFMT_ARGB_8,*/    4, 8,  rgb8_fromfloat,    rgb8_tofloat,    argb8_writepixel},
    {/*PyPixelArray_PIXFMT_RGBA_8,*/    4, 8,  rgb8_fromfloat,    rgb8_tofloat,    rgba8_writepixel},
    {/*PyPixelArray_PIXFMT_CMYK_8,*/    4, 8,  rgb8_fromfloat,    rgb8_tofloat,    cmyk8_writepixel},
    {/*PyPixelArray_PIXFMT_RGBA_15X,*/  4, 16, rgba15x_fromfloat, rgba15x_tofloat, rgba15x_writepixel},
    {/*PyPixelArray_PIXFMT_CMYKA_15X,*/ 5, 16, rgba15x_fromfloat, rgba15x_tofloat, cmyka15x_writepixel},

    {NULL}
};


/*******************************************************************************************
** Private routines
*/

//+ get_init_values
const PA_InitValue *
get_init_values(ULONG pixfmt)
{
    switch (pixfmt) {
        case PyPixelArray_PIXFMT_RGB_8:     return &gInitValues[0];
        case PyPixelArray_PIXFMT_ARGB_8:    return &gInitValues[1];
        case PyPixelArray_PIXFMT_RGBA_8:    return &gInitValues[2];
        case PyPixelArray_PIXFMT_CMYK_8:    return &gInitValues[3];
        case PyPixelArray_PIXFMT_RGBA_15X:  return &gInitValues[4];
        case PyPixelArray_PIXFMT_CMYKA_15X: return &gInitValues[5];

        default: return NULL;
    }
}
//-

/*** Pixel write functions ***/

//+ rgb8_writepixel
static void
rgb8_writepixel(APTR data, FLOAT opacity, FLOAT erase, USHORT *color)
{
    UBYTE *pixel = data;
    ULONG alpha = (ULONG)(opacity * 255);
    ULONG one_minus_alpha = 255 - alpha;

    alpha *= erase;  

    /* R */ pixel[0] = (((alpha*color[0]*255)>>15) + one_minus_alpha*pixel[0]) / 255;
    /* G */ pixel[1] = (((alpha*color[1]*255)>>15) + one_minus_alpha*pixel[1]) / 255;
    /* B */ pixel[2] = (((alpha*color[2]*255)>>15) + one_minus_alpha*pixel[2]) / 255;
}
//-
//+ rgba8_writepixel
static void
rgba8_writepixel(APTR data, FLOAT opacity, FLOAT erase, USHORT *color)
{
    UBYTE *pixel = data;
    ULONG alpha = (ULONG)(opacity * 255);
    ULONG one_minus_alpha = 255 - alpha;

    alpha *= erase;

    /* R */ pixel[0] = (((alpha*color[0]*255)>>15) + one_minus_alpha*pixel[0]) / 255;
    /* G */ pixel[1] = (((alpha*color[1]*255)>>15) + one_minus_alpha*pixel[1]) / 255;
    /* B */ pixel[2] = (((alpha*color[2]*255)>>15) + one_minus_alpha*pixel[2]) / 255;
    /* A */ pixel[3] =    alpha                    + one_minus_alpha*pixel[3]  / 255;
}
//-
//+ argb8_writepixel
static void
argb8_writepixel(APTR data, FLOAT opacity, FLOAT erase, USHORT *color)
{
    UBYTE *pixel = data;
    ULONG alpha = (ULONG)(opacity * 255);
    ULONG one_minus_alpha = 255 - alpha;

    alpha *= erase; 

    /* A */ pixel[0] =    alpha                    + one_minus_alpha*pixel[0]  / 255;
    /* R */ pixel[1] = (((alpha*color[0]*255)>>15) + one_minus_alpha*pixel[1]) / 255;
    /* G */ pixel[2] = (((alpha*color[1]*255)>>15) + one_minus_alpha*pixel[2]) / 255;
    /* B */ pixel[3] = (((alpha*color[2]*255)>>15) + one_minus_alpha*pixel[3]) / 255;
}
//-
//+ cmyk8_writepixel
static void
cmyk8_writepixel(APTR data, FLOAT opacity, FLOAT erase, USHORT *color)
{
    UBYTE *pixel = data;
    ULONG alpha = (ULONG)(opacity * 255);
    ULONG one_minus_alpha = 255 - alpha;

    alpha *= erase; 

    /* C */ pixel[0] = (((alpha*color[0]*255)>>15) + one_minus_alpha*pixel[0]) / 255;
    /* M */ pixel[1] = (((alpha*color[1]*255)>>15) + one_minus_alpha*pixel[1]) / 255;
    /* Y */ pixel[2] = (((alpha*color[2]*255)>>15) + one_minus_alpha*pixel[2]) / 255;
    /* K */ pixel[3] = (((alpha*color[3]*255)>>15) + one_minus_alpha*pixel[3]) / 255;
}
//-
//+ rgba15x_writepixel
static void
rgba15x_writepixel(APTR data, FLOAT opacity, FLOAT erase, USHORT *color)
{
    USHORT *pixel = data;
    ULONG alpha = (ULONG)(opacity*erase * (1<<15));
    ULONG one_minus_alpha = (1<<15) - (ULONG)(opacity * (1<<15));

    /* R */ pixel[0] = (alpha*color[0] + one_minus_alpha*pixel[0]) / (1<<15);
    /* G */ pixel[1] = (alpha*color[1] + one_minus_alpha*pixel[1]) / (1<<15);
    /* B */ pixel[2] = (alpha*color[2] + one_minus_alpha*pixel[2]) / (1<<15);
    /* A */ pixel[3] =  alpha          + one_minus_alpha*pixel[3]  / (1<<15);
}
//-
//+ cmyka15x_writepixel
static void
cmyka15x_writepixel(APTR data, FLOAT opacity, FLOAT erase, USHORT *color)
{
    USHORT *pixel = data;
    ULONG alpha = (ULONG)(opacity * (1<<15));
    ULONG one_minus_alpha = (1<<15) - alpha;

    alpha *= erase; 

    /* C */ pixel[0] = (alpha*color[0] + one_minus_alpha*pixel[0]) / (1<<15);
    /* M */ pixel[1] = (alpha*color[1] + one_minus_alpha*pixel[1]) / (1<<15);
    /* Y */ pixel[2] = (alpha*color[2] + one_minus_alpha*pixel[2]) / (1<<15);
    /* K */ pixel[3] = (alpha*color[3] + one_minus_alpha*pixel[3]) / (1<<15);
    /* A */ pixel[4] =  alpha          + one_minus_alpha*pixel[4]  / (1<<15);
}
//-

/*** Color conversion functions ***/

/* /!\ no clamping applied ! */

//+ rgb8_fromfloat
static void
rgb8_fromfloat(FLOAT from, APTR *to)
{
    *((UBYTE *)to) = (UBYTE)(from * 255);
}
//-
//+ rgba15x_fromfloat
static void
rgba15x_fromfloat(FLOAT from, APTR *to)
{
    *((USHORT *)to) = (USHORT)(from * (1<<15));
}
//-

//+ rgb8_tofloat
static FLOAT
rgb8_tofloat(APTR from)
{
    return (FLOAT)(*(UBYTE *)from) / 255;
}
//-
//+ rgba15x_tofloat
static FLOAT
rgba15x_tofloat(APTR from)
{
    return (FLOAT)(*(USHORT *)from) / (1<<15);
}
//-


/* About color format in buffers.
 *
 * Pixels colors are stored as 4 components (RGBA/ARGB/CMYKA) using fixed point encoding.
 * So the floating point range [0.0, 1.0] is converted into integer range [0, 2**15].
 * Using 2**15 than a more natural 2**16 value gives the way to store the 1.0 value
 * into a short integer (16bits) and permit to use a logical shift operation of 15 bits,
 * when we need to multiply/divide values in fixed-point arithmetic computations.
 *
 * In all the application I'll note rgba15x a RGBA pixels buffer using this convention.
 */

//+ rgba15x_to_argb8
static void
rgba15x_to_argb8(USHORT *src, UBYTE *dst, ULONG w, ULONG h, Py_ssize_t bpr)
{
    ULONG x, y;

    bpr -= w*4;

    for (y=0; y < h; y++) {
        for (x=0; x < w; x++) {
            ULONG alpha = src[3];

            if (alpha > 0) {
                /* Convert alpha to range [0, 255] */
                dst[0] = (alpha * 255) >> 15;

                /* Un-multiply by alpha, rounding and convert to range [0, 255] */
                dst[1] = ((((ULONG)src[0]<<15) + alpha/2) / alpha * 255) >> 15;
                dst[2] = ((((ULONG)src[1]<<15) + alpha/2) / alpha * 255) >> 15;
                dst[3] = ((((ULONG)src[2]<<15) + alpha/2) / alpha * 255) >> 15;
            } else
                *(ULONG *)dst = 0;
            
            src += 4;
            dst += 4;
        }

        dst += bpr;
    }
}
//-
//+ rgba15x_to_rgba8
static void
rgba15x_to_rgba8(USHORT *src, UBYTE *dst, ULONG w, ULONG h, Py_ssize_t bpr)
{
    ULONG x, y;

    bpr -= w*4;

    for (y=0; y < h; y++) {
        for (x=0; x < w; x++) {
            ULONG alpha = src[3];

            if (alpha > 0) {
                /* Un-multiply by alpha, rounding and convert to range [0, 255] */
                dst[0] = ((((ULONG)src[0]<<15) + alpha/2) / alpha * 255) >> 15;
                dst[1] = ((((ULONG)src[1]<<15) + alpha/2) / alpha * 255) >> 15;
                dst[2] = ((((ULONG)src[2]<<15) + alpha/2) / alpha * 255) >> 15;

                /* Convert alpha to range [0, 255] */
                dst[3] = (alpha * 255) >> 15;
            } else
                *(ULONG *)dst = 0;
            
            src += 4;
            dst += 4;
        }

        dst += bpr;
    }
}
//-
//+ rgba15x_to_rgb8
static void
rgba15x_to_rgb8(USHORT *src, UBYTE *dst, UWORD w, UWORD h, Py_ssize_t bpr)
{
    ULONG x, y;

    bpr -= w*3;

    for (y=0; y < h; y++) {
        for (x=0; x < w; x++) {
            ULONG alpha = src[3];

            if (alpha > 0) {
                /* Un-multiply by alpha, rounding and convert to range [0, 255] */
                dst[0] = ((((ULONG)src[0]<<15) + alpha/2) / alpha * 255) >> 15;
                dst[1] = ((((ULONG)src[1]<<15) + alpha/2) / alpha * 255) >> 15;
                dst[2] = ((((ULONG)src[2]<<15) + alpha/2) / alpha * 255) >> 15;
            } else
                dst[0] = dst[1] = dst[2] = 0;

            src += 4;
            dst += 3;
        }

        dst += bpr;
    }
}
//-
//+ rgba8_to_rgba15x
static void
rgba8_to_rgba15x(UBYTE *src, USHORT *dst, UWORD w, UWORD h)
{
    ULONG i, n = w * h;

    for (i=0; i < n; i++) {
        ULONG alpha = ((ULONG)src[3] << 15) / 255;
        
        dst[0] = (ULONG)src[0] * alpha / 255;
        dst[1] = (ULONG)src[1] * alpha / 255;
        dst[2] = (ULONG)src[2] * alpha / 255;
        dst[3] = alpha;

        src += 4;
        dst += 4;
    }
}
//-
//+ argb8_to_rgba15x
static void
argb8_to_rgba15x(UBYTE *src, USHORT *dst, UWORD w, UWORD h)
{
    ULONG i, n = w * h;

    for (i=0; i < n; i++) {
        USHORT alpha = ((ULONG)src[0] << 15) / 255;
        
        dst[0] = (ULONG)src[1] * alpha / 255;
        dst[1] = (ULONG)src[2] * alpha / 255;
        dst[2] = (ULONG)src[3] * alpha / 255;
        dst[3] = alpha;

        src += 4;
        dst += 4;
    }
}
//-
//+ rgb8_to_rgba15x
static void
rgb8_to_rgba15x(UBYTE *src, USHORT *dst, UWORD w, UWORD h)
{
    ULONG i, n = w * h;

    for (i=0; i < n; i++) {
        dst[0] = ((ULONG)src[0] << 15) / 255;
        dst[1] = ((ULONG)src[1] << 15) / 255;
        dst[2] = ((ULONG)src[2] << 15) / 255;
        dst[3] = 1 << 15;

        src += 3;
        dst += 4;
    }
}
//-
//+ rgb8_to_rgba8
static void
rgb8_to_rgba8(UBYTE *src, UBYTE *dst, UWORD w, UWORD h)
{
    ULONG i, n = w * h;

    for (i=0; i < n; i++) {
        dst[0] = src[0];
        dst[1] = src[1];
        dst[2] = src[2];
        dst[3] = 255;

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
//+ compose_rgba15x_to_rgb8
static void
compose_rgba15x_to_rgb8(USHORT *src, UBYTE *dst, ULONG w, ULONG h)
{
    ULONG x, y;

    for (y=0; y < h; y++) {
        for (x=0; x < w; x++) {
            ULONG one_minus_alpha = (1<<15) - src[3];

            /* Destination Alpha = 1.0 (full opaque surface)
             * Dest{RGB} = Src{RGB} + (1.0 - SrcAlpha) * Dst{RGB}
             */

            dst[0] = ((ULONG)src[0] * 255 + one_minus_alpha * dst[0]) >> 15;
            dst[1] = ((ULONG)src[1] * 255 + one_minus_alpha * dst[1]) >> 15;
            dst[2] = ((ULONG)src[2] * 255 + one_minus_alpha * dst[2]) >> 15;

            src += 4;
            dst += 3;
        }
    }
}
//-

//+ cmyka15x_to_cmyk8
static void
cmyka15x_to_cmyk8(USHORT *src, UBYTE *dst, UWORD w, UWORD h, Py_ssize_t bpr)
{
    ULONG x, y;

    bpr -= w*4;

    for (y=0; y < h; y++) {
        for (x=0; x < w; x++) {
            ULONG alpha = src[4];

            if (alpha > 0) {
                /* Un-multiply by alpha, rounding and convert to range [0, 255] */
                dst[0] = ((((ULONG)src[0]<<15) + alpha/2) / alpha * 255) >> 15;
                dst[1] = ((((ULONG)src[1]<<15) + alpha/2) / alpha * 255) >> 15;
                dst[2] = ((((ULONG)src[2]<<15) + alpha/2) / alpha * 255) >> 15;
                dst[3] = ((((ULONG)src[3]<<15) + alpha/2) / alpha * 255) >> 15;
            } else
                *(ULONG *)dst = 0;

            src += 5;
            dst += 4;
        }

        dst += bpr;
    }
}
//-
//+ cmyk8_to_cmyka15x
static void
cmyk8_to_cmyka15x(UBYTE *src, USHORT *dst, UWORD w, UWORD h)
{
    ULONG i, n = w * h;

    for (i=0; i < n; i++) {
        dst[0] = ((ULONG)src[0] << 15) / 255;
        dst[1] = ((ULONG)src[1] << 15) / 255;
        dst[2] = ((ULONG)src[2] << 15) / 255;
        dst[3] = ((ULONG)src[3] << 15) / 255;
        dst[4] = 1 << 15;

        src += 4;
        dst += 5;
    }
}
//-


/*******************************************************************************************
** PyPixelArray_Type
*/

//+ new_pixarray
static BOOL
initialize_pixarray(PyPixelArray *self, UWORD width, UWORD height, ULONG pixfmt)
{
    const PA_InitValue *init_values = get_init_values(pixfmt);

    if (NULL == init_values) {
        PyErr_Format(PyExc_ValueError, "Invalid pixel format (%lx)", pixfmt);
        return FALSE;
    }

    self->bpc = init_values->bpc;
    self->nc = init_values->nc;
   self->bpr = width * ((self->bpc * self->nc) >> 3);

    self->data = PyMem_Malloc(self->bpr * height);
    if (NULL != self->data) {
        self->damaged = FALSE;
        self->x = self->y = 0;
        self->pixfmt = pixfmt;
        self->width = width;
        self->height = height;
        self->cfromfloat = init_values->cfromfloat;
        self->ctofloat = init_values->ctofloat;
        self->writepixel = init_values->writepixel;

        return TRUE;
    }

    return FALSE;
}
//-

//+ pixarray_new
static PyObject *
pixarray_new(PyTypeObject *type, PyObject *args)
{
    PyPixelArray *self;
    UWORD w, h;
    ULONG pixfmt;

    if (!PyArg_ParseTuple(args, "HHI:__new__", &w, &h, &pixfmt)) /* BR */
        return NULL;

    self = (PyPixelArray *)type->tp_alloc(type, 0); /* NR */
    if (NULL != self) {
        if (!initialize_pixarray(self, w, h, pixfmt))
            Py_CLEAR((PyObject *)self);
    }

    return (PyObject *)self;
}
//-
//+ pixarray_dealloc
static void
pixarray_dealloc(PyPixelArray *self)
{
    if (NULL != self->data) PyMem_Free(self->data);
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

    if ((src->bpr * src->height) < (self->bpr * self->height))
        return PyErr_Format(PyExc_TypeError, "Source array is too small, %lu bytes needed, get %lu", self->bpr * self->height, src->bpr * src->height);

    len = MIN(self->bpr * self->height, src->bpr * src->height);
    CopyMem(src->data, self->data, len);

    Py_RETURN_NONE;
}
//-
//+ pixarray_copy
static PyObject *
pixarray_copy(PyPixelArray *self)
{
    PyPixelArray *copy;

    copy = PyObject_New(PyPixelArray, self->ob_type);
    if (NULL != copy) {
        if (initialize_pixarray(copy, self->width, self->height, self->pixfmt)) {
            copy->x = self->x;
            copy->y = self->y;
            CopyMem(self->data, copy->data, copy->bpr*copy->height);
        } else
            Py_CLEAR(copy);
    }

    return (PyObject *)copy;
}
//-
//+ pixarray_nonzero
static int
pixarray_nonzero(PyPixelArray *self)
{
    Py_ssize_t i, n = self->height * self->bpr / sizeof(ULONG);
    ULONG *ptr = self->data;

    for (i=0; i < n; i++, ptr++) if (*ptr) return TRUE;
    return FALSE;
}
//-
//+ pixarray_pick_color
static PyObject *
pixarray_pick_color(PyPixelArray *self, PyObject *args)
{
    LONG x, y;
    APTR ptr;
    FLOAT r,g,b;

    if (!PyArg_ParseTuple(args, "kk", &x, &y))
        return NULL;

    ptr = &((UBYTE *)self->data)[y*self->bpr + x*((self->bpc*self->nc) >> 3)];
    if (self->pixfmt & PyPixelArray_FLAG_RGB) {
        if (self->pixfmt & PyPixelArray_FLAG_ALPHA_FIRST) {
            if (self->pixfmt & PyPixelArray_FLAG_8) {
                r = *(++(UBYTE *)ptr) / 255.;
                g = *(++(UBYTE *)ptr) / 255.;
                b = *(++(UBYTE *)ptr) / 255.;
            } else {
                r = *(++(USHORT *)ptr) / (float)(1<<15);
                g = *(++(USHORT *)ptr) / (float)(1<<15);
                b = *(++(USHORT *)ptr) / (float)(1<<15);
            }
        } else {
            if (self->pixfmt & PyPixelArray_FLAG_8) {
                r = *(((UBYTE *)ptr)++) / 255.;
                g = *(((UBYTE *)ptr)++) / 255.;
                b = *((UBYTE *)ptr)     / 255.;
            } else {
                r = *(((USHORT *)ptr)++) / (float)(1<<15);
                g = *(((USHORT *)ptr)++) / (float)(1<<15);
                b = *((USHORT *)ptr)     / (float)(1<<15);
            }
        }
    } else {
        /* TODO */
        /* need to return a converted color to RGB ? */
        r = g = b = 0.0;
    }

    return Py_BuildValue("fff", r, g, b);
}
//-


static struct PyMethodDef pixarray_methods[] = {
    {"zero", (PyCFunction)pixarray_zero, METH_VARARGS, NULL},
    {"one", (PyCFunction)pixarray_one, METH_VARARGS, NULL},
    {"from_string", (PyCFunction)pixarray_from_string, METH_O, NULL},
    {"from_pixarray", (PyCFunction)pixarray_from_pixarray, METH_O, NULL},
    {"copy", (PyCFunction)pixarray_copy, METH_NOARGS, NULL},
    {"pick_color", (PyCFunction)pixarray_pick_color, METH_VARARGS, NULL},
    {NULL} /* sentinel */
};

static PyMemberDef pixarray_members[] = {
    {"pixfmt", T_ULONG, offsetof(PyPixelArray, pixfmt), 0, NULL},
    {"x", T_LONG, offsetof(PyPixelArray, x), 0, NULL},
    {"y", T_LONG, offsetof(PyPixelArray, y), 0, NULL},
    {"Width", T_USHORT, offsetof(PyPixelArray, width), RO, NULL},
    {"Height", T_USHORT, offsetof(PyPixelArray, height), RO, NULL},
    {"BytesPerRow", T_ULONG, offsetof(PyPixelArray, bpr), RO, NULL},
    {"ComponentNumber", T_UBYTE, offsetof(PyPixelArray, nc), RO, NULL},
    {"BitsPerComponent", T_UBYTE, offsetof(PyPixelArray, bpc), RO, NULL},
    {"DataAddress", T_ULONG, offsetof(PyPixelArray, data), RO, NULL},
    {"Damaged", T_UBYTE, offsetof(PyPixelArray, damaged), 0, NULL},
    {NULL}
};

static PyBufferProcs pixarray_as_buffer = {
    bf_getreadbuffer  : (getreadbufferproc)pixarray_getbuffer,
    bf_getwritebuffer : (getwritebufferproc)pixarray_getbuffer,
    bf_getsegcount    : (getsegcountproc)pixarray_getsegcount,
};

static PyNumberMethods pixarray_as_number = {
    nb_nonzero : (inquiry)pixarray_nonzero,
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
    tp_as_number    : &pixarray_as_number,
};


/*******************************************************************************************
** Module
*/

#if 0
//+ mod_rgb8_to_argb8
static PyObject *
mod_rgb8_to_argb8(PyObject *self, PyObject *args)
{
    PyPixelArray *src, *dst;

    if (!PyArg_ParseTuple(args, "O!O!", &PyPixelArray_Type, &src, &PyPixelArray_Type, &dst))
        return NULL;

    

    if ((src->width != dst->width) || (src->height != dst->height))
        return PyErr_Format(PyExc_TypeError, "Incompatible dimensions between given PixelArray objects");

    /* todo */

    Py_RETURN_NONE;
}
//-
//+ mod_rgb8_to_argb15x
static PyObject *
mod_rgb8_to_argb15x(PyObject *self, PyObject *args)
{
    PyPixelArray *src, *dst;

    if (!PyArg_ParseTuple(args, "O!O!", &PyPixelArray_Type, &src, &PyPixelArray_Type, &dst))
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
//+ mod_argb15x_to_argb8
static PyObject *
mod_argb15x_to_argb8(PyObject *self, PyObject *args)
{
    PyPixelArray *src, *dst;
    ULONG dst_x=0, dst_y=0;

    if (!PyArg_ParseTuple(args, "O!O!|II", &PyPixelArray_Type, &src, &PyPixelArray_Type, &dst, &dst_x, &dst_y))
        return NULL;

    if ((src->nc != 4) || (src->bpc != 16))
        return PyErr_Format(PyExc_TypeError, "Incompatible source PixelArray object");

    if ((dst->nc != 4) || (dst->bpc != 8))
        return PyErr_Format(PyExc_TypeError, "Incompatible destination PixelArray object");

    /* No clipping */
    if ((src->width > dst->width) || (src->height > dst->height))
        return PyErr_Format(PyExc_TypeError, "Incompatible dimensions between given PixelArray objects");

    //argb15x_to_argb8(src->data, dst->data+(dst->bpr*dst_y)+dst_x*4, src->width, src->height, dst->bpr);

    Py_RETURN_NONE;
}
//-
#endif
//+ mod_rgba8_to_rgba15x
static PyObject *
mod_rgba8_to_rgba15x(PyObject *self, PyObject *args)
{
    PyPixelArray *src, *dst;

    if (!PyArg_ParseTuple(args, "O!O!", &PyPixelArray_Type, &src, &PyPixelArray_Type, &dst))
        return NULL;

    if (src->pixfmt != PyPixelArray_PIXFMT_RGBA_8)
        return PyErr_Format(PyExc_TypeError, "Incompatible source PixelArray format");

    if (dst->pixfmt != PyPixelArray_PIXFMT_RGBA_15X)
        return PyErr_Format(PyExc_TypeError, "Incompatible destination PixelArray format");

    if ((src->width != dst->width) || (src->height != dst->height))
        return PyErr_Format(PyExc_TypeError, "Incompatible dimensions between given PixelArray objects");

    rgba8_to_rgba15x(src->data, dst->data, dst->width, dst->height);

    Py_RETURN_NONE;
}
//-
//+ mod_rgba15x_to_rgb8
static PyObject *
mod_rgba15x_to_rgb8(PyObject *self, PyObject *args)
{
    PyPixelArray *src, *dst;
    ULONG dst_x=0, dst_y=0;
    APTR ptr;      
    
    if (!PyArg_ParseTuple(args, "O!O!|II", &PyPixelArray_Type, &src, &PyPixelArray_Type, &dst, &dst_x, &dst_y))
        return NULL;

    if (src->pixfmt != PyPixelArray_PIXFMT_RGBA_15X)
        return PyErr_Format(PyExc_TypeError, "Incompatible source PixelArray format");

    if (dst->pixfmt != PyPixelArray_PIXFMT_RGB_8)
        return PyErr_Format(PyExc_TypeError, "Incompatible destination PixelArray format");
 
    /* No clipping */
    if ((src->width > dst->width) || (src->height > dst->height))
        return PyErr_Format(PyExc_TypeError, "Incompatible dimensions between given PixelArray objects");

    ptr = dst->data+(dst->bpr*dst_y)+dst_x*3;
    rgba15x_to_rgb8(src->data, ptr, src->width, src->height, dst->bpr);

    Py_RETURN_NONE;
}
//-
//+ mod_rgba15x_to_argb8
static PyObject *
mod_rgba15x_to_argb8(PyObject *self, PyObject *args)
{
    PyPixelArray *src, *dst;
    ULONG dst_x=0, dst_y=0;
    APTR ptr;

    if (!PyArg_ParseTuple(args, "O!O!|II", &PyPixelArray_Type, &src, &PyPixelArray_Type, &dst, &dst_x, &dst_y))
        return NULL;

    if (src->pixfmt != PyPixelArray_PIXFMT_RGBA_15X)
        return PyErr_Format(PyExc_TypeError, "Incompatible source PixelArray format");

    if (dst->pixfmt != PyPixelArray_PIXFMT_ARGB_8)
        return PyErr_Format(PyExc_TypeError, "Incompatible destination PixelArray format");

    /* No clipping */
    if ((src->width > dst->width) || (src->height > dst->height))
        return PyErr_Format(PyExc_TypeError, "Incompatible dimensions between given PixelArray objects");

    ptr = dst->data+(dst->bpr*dst_y)+dst_x*4;
    rgba15x_to_argb8(src->data, ptr, src->width, src->height, dst->bpr);

    Py_RETURN_NONE;
}
//-
//+ mod_rgba15x_to_rgba8
static PyObject *
mod_rgba15x_to_rgba8(PyObject *self, PyObject *args)
{
    PyPixelArray *src, *dst;
    ULONG dst_x=0, dst_y=0;
    APTR ptr;

    if (!PyArg_ParseTuple(args, "O!O!|II", &PyPixelArray_Type, &src, &PyPixelArray_Type, &dst, &dst_x, &dst_y))
        return NULL;

    if (src->pixfmt != PyPixelArray_PIXFMT_RGBA_15X)
        return PyErr_Format(PyExc_TypeError, "Incompatible source PixelArray format");

    if (dst->pixfmt != PyPixelArray_PIXFMT_RGBA_8)
        return PyErr_Format(PyExc_TypeError, "Incompatible destination PixelArray format");

    /* No clipping */
    if ((src->width > dst->width) || (src->height > dst->height))
        return PyErr_Format(PyExc_TypeError, "Incompatible dimensions between given PixelArray objects");

    ptr = dst->data+(dst->bpr*dst_y)+dst_x*4;
    rgba15x_to_rgba8(src->data, ptr, src->width, src->height, dst->bpr);

    Py_RETURN_NONE;
}
//-
//+ mod_compose_rgba15x_to_rgb8
static PyObject *
mod_compose_rgba15x_to_rgb8(PyObject *self, PyObject *args)
{
    PyPixelArray *src, *dst;

    if (!PyArg_ParseTuple(args, "O!O!", &PyPixelArray_Type, &src, &PyPixelArray_Type, &dst))
        return NULL;

    if (src->pixfmt != PyPixelArray_PIXFMT_RGBA_15X)
        return PyErr_Format(PyExc_TypeError, "Incompatible source PixelArray format");

    if (dst->pixfmt != PyPixelArray_PIXFMT_RGB_8)
        return PyErr_Format(PyExc_TypeError, "Incompatible destination PixelArray format");

    if ((src->width != dst->width) || (src->height != dst->height))
        return PyErr_Format(PyExc_TypeError, "Incompatible dimensions between given PixelArray objects");

    compose_rgba15x_to_rgb8(src->data, dst->data, dst->width, dst->height);

    Py_RETURN_NONE;
}
//-

static PyMethodDef methods[] = {
    //{"rgb8_to_argb8",            (PyCFunction)mod_rgb8_to_argb8,            METH_VARARGS, NULL},
    //{"rgb8_to_argb15x",          (PyCFunction)mod_rgb8_to_argb15x,          METH_VARARGS, NULL},
    {"rgba8_to_rgba15x",        (PyCFunction)mod_rgba8_to_rgba15x,        METH_VARARGS, NULL},
    {"rgba15x_to_argb8",        (PyCFunction)mod_rgba15x_to_argb8,        METH_VARARGS, NULL},
    {"rgba15x_to_rgba8",        (PyCFunction)mod_rgba15x_to_rgba8,        METH_VARARGS, NULL},
    {"rgba15x_to_rgb8",         (PyCFunction)mod_rgba15x_to_rgb8,         METH_VARARGS, NULL},
    {"compose_rgba15x_to_rgb8", (PyCFunction)mod_compose_rgba15x_to_rgb8, METH_VARARGS, NULL},
    {0}
};

//+ add_constants
static int add_constants(PyObject *m)
{
    INSI(m, "PIXFMT_RGB_8", PyPixelArray_PIXFMT_RGB_8);
    INSI(m, "PIXFMT_RGBA_8", PyPixelArray_PIXFMT_RGBA_8);
    INSI(m, "PIXFMT_CMYK_8", PyPixelArray_PIXFMT_CMYK_8);
    INSI(m, "PIXFMT_ARGB_8", PyPixelArray_PIXFMT_ARGB_8);
    INSI(m, "PIXFMT_RGBA_15X", PyPixelArray_PIXFMT_RGBA_15X);
    INSI(m, "PIXFMT_CMYKA_15X", PyPixelArray_PIXFMT_CMYKA_15X);
    INSI(m, "FLAG_RGB", PyPixelArray_FLAG_RGB);
    INSI(m, "FLAG_CMYK", PyPixelArray_FLAG_CMYK);
    INSI(m, "FLAG_15X", PyPixelArray_FLAG_15X);
    INSI(m, "FLAG_8", PyPixelArray_FLAG_8);
    INSI(m, "FLAG_ALPHA_FIRST", PyPixelArray_FLAG_ALPHA_FIRST);
    INSI(m, "FLAG_ALPHA_LAST", PyPixelArray_FLAG_ALPHA_LAST);

    return 0;
}
//-
//+ PyMorphOS_CloseModule
void
PyMorphOS_CloseModule(void)
{
    if (NULL != CyberGfxBase) {
        CloseLibrary(CyberGfxBase);
        CyberGfxBase = NULL;
    }
}
//- PyMorphOS_CloseModule
//+ INITFUNC()
PyMODINIT_FUNC
INITFUNC(void)
{
    PyObject *m;

    CyberGfxBase = OpenLibrary("cybergraphics.library", 50);
    if (NULL == CyberGfxBase)
        return;

    if (PyType_Ready(&PyPixelArray_Type) < 0) return;

    m = Py_InitModule(MODNAME, methods);
    if (NULL == m)
        return;

    add_constants(m);

    ADD_TYPE(m, "PixelArray", &PyPixelArray_Type);
}
//-
