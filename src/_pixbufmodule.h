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

#ifndef _PIXBUFMODULE_H

#ifndef _PIXBUF_CORE

static PyTypeObject *PyPixbuf_Type=NULL;
#define PyPixbuf_Check(op) PyObject_TypeCheck(op, PyPixbuf_Type)
#define PyPixbuf_CheckExact(op) ((op)->ob_type == PyPixbuf_Type)

static PyTypeObject *import_pixbuf(void) __attribute__((unused));

static PyTypeObject *
import_pixbuf(void)
{
    PyObject *_pixbuf = PyImport_ImportModule("model._pixbuf"); /* NR */

    if (NULL != _pixbuf)
    {
        PyPixbuf_Type = (PyTypeObject *)PyObject_GetAttrString(_pixbuf, "Pixbuf"); /* NR */
        Py_DECREF(_pixbuf);
    }
    return PyPixbuf_Type;
}

#else

static PyTypeObject PyPixbuf_Type;
#define PyPixbuf_Check(op) PyObject_TypeCheck(op, &PyPixbuf_Type)
#define PyPixbuf_CheckExact(op) ((op)->ob_type == &PyPixbuf_Type)

#endif /* _PIXBUF_CORE */

#define MAX_CHANNELS 5 /* CYMKA */

#define ROUND_ERROR_8BITS (255/2)
#define ROUND_ERROR_15BITS (32768/2)

#define PyPixbuf_FLAG_RGB         (1<<0)
#define PyPixbuf_FLAG_CMYK        (1<<1)
#define PyPixbuf_FLAG_15X         (1<<2)
#define PyPixbuf_FLAG_8           (1<<3)
#define PyPixbuf_FLAG_ALPHA_FIRST (1<<4)
#define PyPixbuf_FLAG_ALPHA_LAST  (1<<5)
#define PyPixbuf_FLAG_NO_ALPHA_PREMUL (1<<6)
#define PyPixbuf_FLAG_HAS_ALPHA   (PyPixbuf_FLAG_ALPHA_FIRST|PyPixbuf_FLAG_ALPHA_LAST)

/* Used for load/save */
#define PyPixbuf_PIXFMT_RGB_8 (PyPixbuf_FLAG_RGB | PyPixbuf_FLAG_8)
#define PyPixbuf_PIXFMT_RGBA_8 (PyPixbuf_PIXFMT_RGB_8 | PyPixbuf_FLAG_ALPHA_LAST)
#define PyPixbuf_PIXFMT_RGBA_8_NOA (PyPixbuf_PIXFMT_RGBA_8 | PyPixbuf_FLAG_NO_ALPHA_PREMUL)
#define PyPixbuf_PIXFMT_CMYK_8 (PyPixbuf_FLAG_CMYK | PyPixbuf_FLAG_8)

/* Used for display */
#define PyPixbuf_PIXFMT_ARGB_8 (PyPixbuf_PIXFMT_RGB_8 | PyPixbuf_FLAG_ALPHA_FIRST)
#define PyPixbuf_PIXFMT_ARGB_8_NOA (PyPixbuf_PIXFMT_ARGB_8 | PyPixbuf_FLAG_NO_ALPHA_PREMUL)

/* Used for drawing */
#define PyPixbuf_PIXFMT_RGBA_15X (PyPixbuf_FLAG_RGB | PyPixbuf_FLAG_15X | PyPixbuf_FLAG_ALPHA_LAST)
#define PyPixbuf_PIXFMT_ARGB_15X (PyPixbuf_FLAG_RGB | PyPixbuf_FLAG_15X | PyPixbuf_FLAG_ALPHA_FIRST)
#define PyPixbuf_PIXFMT_CMYKA_15X (PyPixbuf_FLAG_CMYK | PyPixbuf_FLAG_15X | PyPixbuf_FLAG_ALPHA_LAST)

typedef void (*writefunc)(void * pixel, float opacity, float erase, unsigned short * color);
typedef void (*write2func)(void * pixel, unsigned short * color);
typedef void (*readfunc)(void * pixel, unsigned short * color);
typedef void (*colfloat2natif)(float from, void *to);
typedef float (*colnatif2float)(void *from);

typedef struct PyPixbuf_STRUCT {
    PyObject_HEAD

    int            pixfmt;                      /* Pixel Format */
    int            x, y;                        /* Buffers positions */
    int            width, height;               /* Pixels array size */
    char           readonly;                    /* True if the buffer is protected against write */
    char           damaged;                     /* True if written but not displayed */
    unsigned char  nc;                          /* Number of components per pixels */
    unsigned char  bpc;                         /* Number of bits for each components */
    unsigned int   bpr;                         /* Number of bytes per row */
    colfloat2natif cfromfloat;                  /* Function to convert a color channel value given in float to natif value */
    colnatif2float ctofloat;                    /* Function to convert a color channel value given in natif to float value */
    writefunc      writepixel;                  /* Function to change one pixel for given opacity and color */
    writefunc      writepixel_alpha_locked;     /* Function to change one pixel for given opacity and color, Alpha not modified if exists */
    write2func     write2pixel;                 /* Function to change one pixel using all color information */
    readfunc       readpixel;                   /* Function to get color of specific pixel */
    uint8_t *      data_alloc;                  /* Pixels data (from malloc) */
    uint8_t *      data;                        /* Pixels data (aligned) */
} PyPixbuf;

#endif /* _PIXBUFMODULE_H */
