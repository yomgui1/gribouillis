#include "common.h"
#include "_pixbufmodule.h"

#include <math.h>

#ifndef INITFUNC
#define INITFUNC init_brush
#endif

#define NDEBUG

#ifdef NDEBUG
#define DPRINT(x, ...)
#else
#define DPRINT dprintf
#endif

#define PyBrush_Check(op) PyObject_TypeCheck(op, &PyBrush_Type)
#define PyBrush_CheckExact(op) ((op)->ob_type == &PyBrush_Type)

#define PA_CACHE_SIZE 10

typedef struct PyBrush_STRUCT {
    PyObject_HEAD

    PyObject *  b_Surface;
    LONG        b_X;
    LONG        b_Y;
    FLOAT       b_BaseRadius;
    FLOAT       b_BaseYRatio;
    UBYTE       b_Alpha;
    UBYTE       b_Red;
    UBYTE       b_Green;
    UBYTE       b_Blue;
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
obtain_pixbuf(PyObject *surface, LONG x, LONG y, LONG *bsx, LONG *bsy, PyObject **o_pixbuf)
{
    *o_pixbuf = PyObject_CallMethod(surface, "GetBuffer", "iii", x, y, FALSE); /* NR */
    if (NULL != *o_pixbuf) {
        PyObject *o_bsx = PyObject_GetAttrString(*o_pixbuf, "x"); /* NR */
        PyObject *o_bsy = PyObject_GetAttrString(*o_pixbuf, "y"); /* NR */

        if ((NULL != o_bsx) && (NULL != o_bsy)) {
            APTR pixbuf;
            Py_ssize_t len;
            int res;

            res = PyObject_AsWriteBuffer(*o_pixbuf, &pixbuf, &len);
            *bsx = PyLong_AsLong(o_bsx); Py_CLEAR(o_bsx);
            *bsy = PyLong_AsLong(o_bsy); Py_CLEAR(o_bsy);

            /* We suppose that the associated python object remains valid during the draw call */
            if (!res && !PyErr_Occurred()) {
                DPRINT("obtain_pixbuf: pb=%p, len=%lu, bsx=%ld, bsy=%ld, x=%ld, y=%ld\n",
                       pixbuf, *len, *bsx, *bsy, x, y);
                return pixbuf;
            }
        }

        Py_XDECREF(o_bsx);
        Py_XDECREF(o_bsy);
        Py_DECREF(*o_pixbuf);
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
    FLOAT p; /* Pressure, range =  [0.0, 0.1] */
    LONG minx, miny, maxx, maxy, x, y;
    FLOAT radius_radius, hardness=1.0;
    PyObject *buflist;

    if (NULL == self->b_Surface)
        return PyErr_Format(PyExc_RuntimeError, "No surface set.");

    buflist = PyList_New(0); /* NR */
    if (NULL == buflist)
        return NULL;

    if (!PyArg_ParseTuple(args, "(kk)p", &sx, &sy,  &p))
        goto error;

    minx = floorf(sx - self->b_BaseRadius);
    maxx = ceilf(sx + self->b_BaseRadius);
    miny = floorf(sy - self->b_BaseRadius * self->b_BaseYRatio);
    maxy = ceilf(sy + self->b_BaseRadius * self->b_BaseYRatio);

    DPRINT("BDraw: bbox = (%ld, %ld, %ld, %ld)\n", minx, miny, maxx, maxy);
    radius_radius = self->b_BaseRadius * self->b_BaseRadius;

    /* Loop on all pixels inside a bbox centered on (sx, sy) */
    for (y=miny; y <= maxy;) {
        for (x=minx; x <= maxx;) {
            PyPixelArray *o_buf;
            USHORT *buf;
            LONG bsx, bsy; /* Position of the top/left corner of the buffer on surface */
            LONG bx, by;
            int i = -1; /* >=0 when some pixels have been written */

            /* Try to obtain the surface pixels buffer for the point (x, y).
             * Search in internal cache for it, then ask directly to the surface object.
             */

            buf = obtain_pixbuf(self->b_Surface, x, y, &bsx, &bsy, (APTR)&o_buf /* NR */);
            if (NULL == buf)
                goto error;

            /* 'buf' pointer is supposed to be an ARGB15X pixels buffer.
             * This pointer is directly positionned on pixel (bsx, bsy).
             * Buffer is o_buf->width pixels of width and o_buf->height pixels of height.
             * o_buf->bpr gives the number of bytes to add to pass directly
             * to the pixel just below the current position.
             */
            
            /* BBox inside the given buffer (surface units):
             * XMin = x;  XMax = min(maxx, bsx + o_buf->width)
             * YMin = y;  YMax = min(maxy, bsy + o_buf->height)
             * When this area is filled, we keep the x (=XMax+1),
             * but set y to the value before this inner loop.
             */

            bx = x-bsx; /* To remove a compiler warning */
            buf += (y-bsy) * o_buf->bpr / sizeof(*buf);

            DPRINT("BDraw: area = (%ld, %ld, %ld, %ld)\n",
                   x - bsx, y - bsy,
                   MIN(maxx-bsx, o_buf->width-1), MIN(maxy-bsy, o_buf->height-1));

            /* Filling one PixelBuffer (inner loop)
            ** Note: optimization? using a bresenham algo and remove all float computations ?
            */
            for (by=y-bsy; by <= MIN(maxy-bsy, o_buf->width-1); by++) {
                for (bx=x-bsx; bx <= MIN(maxx-bsx, o_buf->height-1); bx++) {
                    FLOAT drx, dry;
                    FLOAT rr, rr_dx;

                    /* Compute the square of ellipse radius
                     * Note: Why +0.5 for each coordinate? because we put the center of
                     * ellipse in the center of the pixel (pixel positions are integers).
                     */
                    drx = bx+bsx - sx + 0.5;
                    dry = (by+bsy - sy + 0.5) / self->b_BaseYRatio;
                    rr = (drx*drx + dry*dry) / radius_radius;

                    /* rr range: [0.0, sqrt(2)] */

                    /* P=(x, y) in the Ellipse ? */
                    if (rr <= 1.0) {
                        FLOAT density = p;
                        ULONG alpha, one_minus_alpha;

                        /* density = p * f(r), where:
                         *   - f is a falloff function
                         *   - r the radius (we using the square radius (rr) in fact)
                         *   - p the pressure
                         *
                         * hardness is the first zero of f (f(hardness)=0.0).
                         * hardness can't be zero (or density = -infinity, clamped to zero)
                         */
                        if (hardness < 1.0) {
                            if (rr < hardness)
                                density *= rr + 1-(rr/hardness);
                            else
                                density *= hardness/(hardness-1)*(rr-1);
                        }

                        i = bx * (4 / sizeof(*buf)); /* Pixel index from the left of buffer */
                        alpha = density * (1<<15); /* density as 15bits fixed point value */
                        one_minus_alpha = (1<<15) - alpha;

                        /* 'Simple' over-alpha compositing (in 15bits fixed point arithmetics)
                         * Supposing that color values are alpha pre-multiplied.
                         */

                        /* A */ buf[i+0] = alpha + one_minus_alpha * buf[i+0] / (1<<15);
                        /* R */ buf[i+1] = (alpha*self->b_Red*(1<<15)   + one_minus_alpha*buf[i+1]) / (1<<15);
                        /* G */ buf[i+2] = (alpha*self->b_Green*(1<<15) + one_minus_alpha*buf[i+2]) / (1<<15);
                        /* B */ buf[i+3] = (alpha*self->b_Blue*(1<<15)  + one_minus_alpha*buf[i+3]) / (1<<15);
                    }
                }

                /* Go to the next row to fill */
                buf += o_buf->bpr / sizeof(*buf);
            }

            /* Written buffer ? */
            if (i >= 0) {
                int failed = PyList_Append(buflist, (PyObject *)o_buf); /* shall incref */

                Py_DECREF((PyObject *)o_buf);
                if (failed)
                    goto error;
            } else
                Py_DECREF((PyObject *)o_buf);

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
    return buflist; /* list of damaged buffers */

error:
    Py_DECREF(buflist);
    return NULL;
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
    if (NULL == value) {
        Py_CLEAR(self->b_Surface);
        return 0;
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

static PyMemberDef brush_members[] = {
    {"x",           T_LONG,  offsetof(PyBrush, b_X), 0, NULL},
    {"y",           T_LONG,  offsetof(PyBrush, b_Y), 0, NULL},
    {"base_radius", T_FLOAT, offsetof(PyBrush, b_BaseRadius), 0, NULL},
    {"base_yratio", T_FLOAT, offsetof(PyBrush, b_BaseYRatio), 0, NULL},
    {"red",         T_UBYTE, offsetof(PyBrush, b_Red), 0, NULL},
    {"green",       T_UBYTE, offsetof(PyBrush, b_Green), 0, NULL},
    {"blue",        T_UBYTE, offsetof(PyBrush, b_Blue), 0, NULL},
    {NULL}
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
    tp_members      : brush_members,
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
