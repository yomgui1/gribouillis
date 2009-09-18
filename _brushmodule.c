#include "common.h"

#include <math.h>

#ifndef INITFUNC
#define INITFUNC init_brush
#endif

#define DPRINT(x, ...)

#define PyBrush_Check(op) PyObject_TypeCheck(op, &PyBrush_Type)
#define PyBrush_CheckExact(op) ((op)->ob_type == &PyBrush_Type)

#define PA_CACHE_SIZE 10

typedef struct PyBrush_STRUCT {
    PyObject_HEAD

    PyObject *  b_Surface;
    ULONG       b_PixBufWidth;
    ULONG       b_PixBufHeight;
    Py_ssize_t  b_PixBufBPR;
    APTR        b_PACache[PA_CACHE_SIZE];
} PyBrush;

static PyTypeObject PyBrush_Type;


/*******************************************************************************************
** Private routines
*/

//+ obtain_pixbuf
/* This function could be used in quite unsafe way, because the length
 * of the returned buffer is not given. An evil code may overflow it.
 */
static APTR
obtain_pixbuf(PyObject *surface, PyObject *buflist, LONG x, LONG y, LONG *bsx, LONG *bsy)
{
    PyObject *o_pixbuf;

    o_pixbuf = PyObject_CallMethod(surface, "GetBuffer", "iii", x, y, FALSE); /* NR */
    if (NULL != o_pixbuf) {
        PyObject *o_bsx = PyObject_GetAttrString(o_pixbuf, "x"); /* NR */
        PyObject *o_bsy = PyObject_GetAttrString(o_pixbuf, "y"); /* NR */

        if ((NULL != o_bsx) && (NULL != o_bsy)) {
            APTR pixbuf;
            Py_ssize_t len;
            int res;

            res = PyObject_AsWriteBuffer(o_pixbuf, &pixbuf, &len);
            *bsx = PyLong_AsLong(o_bsx); Py_CLEAR(o_bsx);
            *bsy = PyLong_AsLong(o_bsy); Py_CLEAR(o_bsy);

            /* We suppose that the associated python object remains valid during the draw call */
            if (!res && !PyErr_Occurred()) {
                DPRINT("obtain_pixbuf: pb=%p, len=%lu, bsx=%ld, bsy=%ld, x=%ld, y=%ld\n",
                    (ULONG)pixbuf, *len, *bsx, *bsy, x, y);
                if (!PyList_Append(buflist, o_pixbuf))
                    return pixbuf;
            }
        }

        Py_XDECREF(o_bsx);
        Py_XDECREF(o_bsy);
        Py_DECREF(o_pixbuf);
    }

    return NULL;
}
//-


/*******************************************************************************************
** PyBrush_Type
*/

//+ brush_new
static PyObject *
brush_new(PyTypeObject *type, PyObject *args)
{
    PyBrush *self;

    self = (PyBrush *)type->tp_alloc(type, 0); /* NR */
    return (PyObject *)self;
}
//-
//+ brush_traverse
static int
brush_traverse(PyBrush *self, visitproc visit, void *arg)
{
    Py_VISIT(self->b_Surface);
    return 0;
}
//-
//+ brush_clear
static int
brush_clear(PyBrush *self)
{
    Py_CLEAR(self->b_Surface);
    return 0;
}
//-
//+ brush_dealloc
static void
brush_dealloc(PyBrush *self)
{
    brush_clear(self);
    self->ob_type->tp_free((PyObject *)self);
}
//-
//+ brush_draw
static PyObject *
brush_draw(PyBrush *self, PyObject *args)
{
    LONG sx, sy; /* Center position (surface units) */
    FLOAT dx, dy; /* Speed vector, range = [0.0, 0.1]*/
    FLOAT p; /* Pressure, range =  [0.0, 0.1] */
    FLOAT y_ratio; /* Ellipse Y/X radius ratio */
    FLOAT radius; /* Ellipse X radius */
    LONG minx, miny, maxx, maxy, x, y;
    FLOAT rr;
    PyObject *buflist;

    if (NULL == self->b_Surface)
        return PyErr_Format(PyExc_RuntimeError, "No surface set.");

    if (!PyArg_ParseTuple(args, "O!kkfffff", &PyList_Type, &buflist, &sx, &sy,  &dx, &dy, &p, &radius, &y_ratio)) /* BR */
        return NULL;

    Py_INCREF(buflist);

    minx = floorf(sx - radius);
    maxx = ceilf(sx + radius);
    miny = floorf(sy - radius * y_ratio);
    maxy = ceilf(sy + radius * y_ratio);

    DPRINT("BDraw: bbox = (%ld, %ld, %ld, %ld)\n", minx, miny, maxx, maxy);
    rr = radius*radius; 

    /* Loop on all pixels inside the bbox supposed to be changed */
    for (y=miny; y <= maxy;) {
        for (x=minx; x <= maxx;) {
            UBYTE *buf;
            LONG bsx, bsy; /* Position of the top/left corner of the buffer on surface */
            LONG bx, by;

            /* Try to obtain the surface pixels buffer for the point (x, y).
             * Search in internal cache for it, then ask directly to the surface object.
             */

            buf = obtain_pixbuf(self->b_Surface, buflist, x, y, &bsx, &bsy);
            if (NULL == buf) {
                Py_DECREF(buflist);
                return NULL;
            }


            /* 'buf' pointer is supposed to be an ARGB15X pixels buffer.
             * This pointer is directly positionned on pixel (bsx, bsy).
             * Buffer is self->b_PixBufWidth pixels of width
             * and self->b_PixBufHeight pixels of height.
             * self->b_PixBufBPR gives the number of bytes to add to pass directly
             * to the pixel just below the current position.
             */
            
            /* BBox inside the given buffer (surface units):
             * XMin = x;  XMax = min(maxx, bsx + self->b_PixBufWidth)
             * YMin = y;  YMax = min(maxy, bsy + self->b_PixBufHeight)
             * When this area is filled, we keep the x (=XMax+1),
             * but set y to the value before this inner loop.
             */

            bx = x-bsx; /* To remove a compiler warning */
            buf += (y-bsy) * self->b_PixBufBPR / sizeof(*buf);

            DPRINT("BDraw: area = (%ld, %ld, %ld, %ld)\n", x-bsx, y-bsy, MIN(maxx-bsx, self->b_PixBufWidth-1), MIN(maxy-bsy, self->b_PixBufHeight-1));

            for (by=y-bsy; by <= MIN(maxy-bsy, self->b_PixBufHeight-1); by++) {
                for (bx=x-bsx; bx <= MIN(maxx-bsx, self->b_PixBufWidth-1); bx++) {
                    FLOAT drx, dry, r;
                    
                    drx = bx+bsx - sx;
                    dry = (by+bsy - sy) / y_ratio;
                    r = (drx * drx + dry*dry);
                    if (r <= rr) {
                        int i = bx*4/sizeof(*buf);
                        ULONG alpha = p*255;
                        ULONG one_minus_alpha = (1.0f - p) * 255;

                        /* XXX: Replace me by the real function */
                        buf[i+0] = (alpha * alpha + (ULONG)buf[i+0] * one_minus_alpha) / 255; /* A */
                        buf[i+1] = (255ul * alpha + (ULONG)buf[i+1] * one_minus_alpha) / 255; /* R */
                        buf[i+2] = (255ul * alpha + (ULONG)buf[i+2] * one_minus_alpha) / 255; /* G */
                        buf[i+3] = (  0ul * alpha + (ULONG)buf[i+3] * one_minus_alpha) / 255; /* B */
                    }
                }

                /* Go to the next row to fill */
                buf += self->b_PixBufBPR / sizeof(*buf);
            }

            if (SetSignal(0, SIGBREAKF_CTRL_C) & SIGBREAKF_CTRL_C)
                goto end;

            /* Update x */
            x = bx + bsx;

            /* Update the y only if x > maxx */
            if (x > maxx)
                y = by + bsy;
        }
    }

end:
    Py_DECREF(buflist);
    Py_RETURN_NONE;
}
//-

//+ brush_get_surface
static PyObject *
brush_get_surface(PyBrush *self, void *closure)
{
    PyObject *value;

    if (NULL != self->b_Surface)
        value = self->b_Surface;
    else
        value = Py_None;

    Py_INCREF(value);
    return value;
}
//-
//+ brush_set_surface
static int
brush_set_surface(PyBrush *self, PyObject *value, void *closure)
{
    PyObject *o;

    if (NULL == value) {
        Py_CLEAR(self->b_Surface);
        return 0;
    }
    
    o = PyObject_GetAttrString(value, "info"); /* NR */
    if (NULL != o) {
        int res = PyArg_ParseTuple(o, "III", &self->b_PixBufWidth, &self->b_PixBufHeight, &self->b_PixBufBPR);

        Py_DECREF(o);
        if (!res)
            return -1;
    }

    self->b_Surface = value; 
    Py_INCREF(value);

    return 0;
}
//-

static PyGetSetDef brush_getseters[] = {
    {"surface", (getter)brush_get_surface, (setter)brush_set_surface, "Surface to use", NULL},
    {NULL} /* sentinel */
};

static struct PyMethodDef brush_methods[] = {
    {"draw", (PyCFunction)brush_draw, METH_VARARGS, NULL},
    {NULL} /* sentinel */
};

static PyTypeObject PyBrush_Type = {
    PyObject_HEAD_INIT(NULL)

    tp_name         : "_brush.Brush",
    tp_basicsize    : sizeof(PyBrush),
    tp_flags        : Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,
    tp_doc          : "Brush Objects",

    tp_new          : (newfunc)brush_new,
    tp_traverse     : (traverseproc)brush_traverse,
    tp_clear        : (inquiry)brush_clear,
    tp_dealloc      : (destructor)brush_dealloc,
    tp_methods      : brush_methods,
    tp_getset       : brush_getseters,
};


/*******************************************************************************************
** Module
*/

//+ _BrushMethods
static PyMethodDef _BrushMethods[] = {
    {0}
};
//-

//+ INITFUNC()
PyMODINIT_FUNC
INITFUNC(void)
{
     PyObject *m;

     if (PyType_Ready(&PyBrush_Type) < 0) return;

     m = Py_InitModule("_brush", _BrushMethods);
     if (NULL == m)
         return;

     ADD_TYPE(m, "Brush", &PyBrush_Type);
}
//-
