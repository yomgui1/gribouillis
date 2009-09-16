#include "common.h"

#include <math.h>

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
static APTR
obtain_pixbuf(PyObject *surface, LONG x, LONG y, LONG *bsx, LONG *bsy)
{
    /* TODO */
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
//+ brush_draw_ellipse
static PyObject *
brush_ellipse(PyBrush *self, PyObject *args)
{
    LONG sx, sy; /* Center position (surface units) */
    FLOAT dx, dy; /* Speed vector, range = [0.0, 0.1]*/
    FLOAT p; /* Pressure, range =  [0.0, 0.1] */
    FLOAT y_ratio; /* Ellipse Y/X radius ratio */
    FLOAT radius; /* Ellipse X radius */
    LONG minx, miny, maxx, maxy, x, y;

    if (!PyArg_ParseTuple(args, "kkfffff", &sx, &sy,  &dx, &dy, &p, &radius, &y_ratio))
        return NULL;

    minx = floorf(sx - radius);
    maxx = ceilf(sx + radius);
    miny = floorf(sy - radius * y_ratio);
    maxy = ceilf(sy + radius * y_ratio);

    Printf("BDraw: %ld, %ld, %ld, %ld\n", minx, miny, maxx, maxy);

    /* Loop on all pixels inside the bbox supposed to be changed */
    for (y=miny; y <= maxy;) {
        for (x=minx; x <= maxx;) {
            USHORT *buf;
            LONG bsx, bsy; /* Position of the top/left corner of the buffer on surface */
            LONG bx, by;

            /* Try to obtain the surface pixels buffer for the point (x, y).
             * Search in internal cache for it, then ask directly to the surface object.
             */

            buf = obtain_pixbuf(self->b_Surface, x, y, &bsx, &bsy);
            
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

            for (by=y-bsy; by <= MIN(maxy-bsy, self->b_PixBufHeight-1); by++) {
                for (bx=x-bsx; bx <= MIN(maxx-bsx, self->b_PixBufWidth-1); bx++) {
                    /* XXX: Replace me by the real function */
                    buf[bx+0] = 1 << 15; /* A */
                    buf[bx+1] = 1 << 15; /* R */
                    buf[bx+2] = 1 << 15; /* G */
                    buf[bx+3] = 0;       /* B */

                    if (SetSignal(SIGBREAKF_CTRL_C, SIGBREAKF_CTRL_C) & SIGBREAKF_CTRL_C)
                        Py_RETURN_NONE;

                    Delay(5);
                }

                /* Go to the next row to fill */
                buf += self->b_PixBufBPR / sizeof(USHORT);
            }

            /* Update x */
            x = bx + bsx;

            /* Update the y only if x > maxx */
            if (x > maxx)
                y = by + bsy;
        }
    }

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

//+ init_brushmodule
void init_brushmodule(void)
{
     PyObject *m;

     if (PyType_Ready(&PyBrush_Type) < 0) return;

     m = Py_InitModule("_brush", _BrushMethods);
     if (NULL == m)
         return;

     ADD_TYPE(m, "Brush", &PyBrush_Type);
}
//-
