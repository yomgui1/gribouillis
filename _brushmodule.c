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

/* TODO:
 *
 * - More dab filling engines: 1d-pattern, 2d-pattern, conical, linear, ...
 * - Optimize inner draw loop, especially for float usage.
 */

#include "common.h"
#include "_pixarraymodule.h"

#include <math.h>

#ifndef INITFUNC
#define INITFUNC init_brush
#endif

#ifndef MODNAME
#define MODNAME "_brush"
#endif

#define NDEBUG

#ifdef NDEBUG
#define DPRINT(x, ...)
#else
#define DPRINT dprintf
#endif

#define PyBrush_Check(op) PyObject_TypeCheck(op, &PyBrush_Type)
#define PyBrush_CheckExact(op) ((op)->ob_type == &PyBrush_Type)

#define PA_CACHE_SIZE 15 /* good value for the case of big brushes */

//#define STAT_TIMING

typedef struct PANode_STRUCT {
    struct MinNode pan_Node;
    PyObject *     pan_PixelArray;
    BOOL           pan_Valid;
} PANode;

typedef struct PyBrush_STRUCT {
    PyObject_HEAD

    /* Object Data */
    PyObject *      b_Surface;
    PANode          b_PACache[PA_CACHE_SIZE];
    struct MinList  b_PACacheList;
    PANode *        b_FirstInvalid;

    /* Brush Model */
    LONG            b_X;
    LONG            b_Y;
    FLOAT           b_Time;

    FLOAT           b_BaseRadius;
    FLOAT           b_BaseYRatio;
    FLOAT           b_Hardness;
    FLOAT           b_Opacity;
    FLOAT           b_TargetAlpha;

    USHORT          b_RGBColor[3];
    USHORT          b_CMYKColor[4];

#ifdef STAT_TIMING
    ULONG           b_CacheAccesses;
    ULONG           b_CacheMiss;
    UQUAD           b_Times[3];
    ULONG           b_TimesCount[3];
#endif

} PyBrush;

static PyTypeObject PyBrush_Type;


/*******************************************************************************************
** Private routines
*/

#ifdef STAT_TIMING
//+ ReadCPUClock
static void
ReadCPUClock(UQUAD *v)
{
    register unsigned long tbu, tb, tbu2;

loop:
    asm volatile ("mftbu %0" : "=r" (tbu) );
    asm volatile ("mftb  %0" : "=r" (tb)  );
    asm volatile ("mftbu %0" : "=r" (tbu2));
    if (tbu != tbu2) goto loop;

    /* The slightly peculiar way of writing the next lines is
       compiled better by GCC than any other way I tried. */
    ((long*)(v))[0] = tbu;
    ((long*)(v))[1] = tb;
}
//-
#endif

//+ obtain_pixarray
static PyPixelArray *
obtain_pixarray(PyBrush *self, PyObject *surface, LONG x, LONG y)
{
    PyObject *cached = NULL, *o = NULL;
    PANode *node, *first_invalid = NULL;

    /* try in cache first */
#ifdef STAT_TIMING
    self->b_CacheAccesses++;
#endif
    ForeachNode(&self->b_PACacheList, node) {
        PyPixelArray *pa;

        if (!node->pan_Valid) {
            first_invalid = node;
            break;
        }

        pa = (APTR)node->pan_PixelArray;
        
        /* (x,y) inside pixel array ? */
        if ((x >= pa->x) && (x < (pa->x + pa->width))
            && (y >= pa->y) && (y < (pa->y + pa->height))) {
            o = cached = (APTR)pa;

            /* This node becomes the first one (next call could be faster) */
            ADDHEAD(&self->b_PACacheList, REMOVE(node));
            break;
        }
    }

    if (NULL != first_invalid)
        self->b_FirstInvalid = first_invalid;
    else
        self->b_FirstInvalid = (APTR)GetTail(&self->b_PACacheList);

    /* Not in cache, get it from the python side so */
    if (NULL == cached) {
#ifdef STAT_TIMING
        self->b_CacheMiss++;
#endif
        o = PyObject_CallMethod(surface, "GetBuffer", "iii", x, y, FALSE); /* NR */
        if (NULL == o)
            return NULL;

        Py_DECREF(o);

        if (!PyPixelArray_Check(o))
            return (APTR)PyErr_Format(PyExc_TypeError, "Surface GetBuffer() method shall returns PixelArray instance, not %s", OBJ_TNAME(o));

        /* Add it to the cache as first entry */
        self->b_FirstInvalid->pan_PixelArray = o; /* don't incref, because object is supposed to be valid
                                                   * until the end of stroke.
                                                   */
        self->b_FirstInvalid->pan_Valid = TRUE;
        ADDHEAD(&self->b_PACacheList, REMOVE(self->b_FirstInvalid));
    }

    return (APTR)o;
}
//-
//+ drawdab_solid
/* Solid spherical filling engine */
static PyObject *
drawdab_solid(PyBrush *self, /* In: */
              PyObject *buflist, /* Out: */
              PyObject *surface, /* In: Give information on color space also */
              LONG sx, LONG sy,
              FLOAT radius, FLOAT yratio,
              FLOAT hardness, /* Never set it to 0.0 ! */
              FLOAT target_alpha, /* 0.0=erase, 1.0=normal, between = translucent target color */
              FLOAT opacity /* 0.0=nothing drawn, 1.0=solid, between = translucent color */)
{
    LONG minx, miny, maxx, maxy, x, y;
    FLOAT radius_radius;
    USHORT *color = NULL;
#ifdef STAT_TIMING
    UQUAD t1, t2;
#endif

    minx = floorf(sx - radius);
    maxx = ceilf(sx + radius);
    miny = floorf(sy - radius * yratio);
    maxy = ceilf(sy + radius * yratio);

    DPRINT("BDraw: bbox = (%ld, %ld, %ld, %ld)\n", minx, miny, maxx, maxy);
    radius_radius = radius * radius;

    /* Loop on all pixels inside a bbox centered on (sx, sy) */
    for (y=miny; y <= maxy;) {
        for (x=minx; x <= maxx;) {
            PyPixelArray *pa;
            USHORT *buf;
            LONG box, boy; /* Position of the top/left corner of the buffer on surface */
            LONG bx, by;
            int i = -1; /* >=0 when some pixels have been written */

            /* Try to obtain the surface pixels buffer for the point (x, y).
             * Search in internal cache for it, then ask directly to the surface object.
             */

#ifdef STAT_TIMING
            ReadCPUClock(&t1);
#endif
            pa = obtain_pixarray(self, surface, x, y); /* NR */
#ifdef STAT_TIMING
            ReadCPUClock(&t2);
            self->b_Times[2] += t2 - t1;
            self->b_TimesCount[2]++;
#endif
            if (NULL == pa)
                goto error;

            /* XXX: I consider that all pixelarray have the same color space */
            if (NULL == color) {
                if (pa->pixfmt & PyPixelArray_FLAG_RGB)
                    color = self->b_RGBColor;
                else
                    color = self->b_CMYKColor;
            }

            box = pa->x;
            boy = pa->y;
            buf = pa->data;

            /* 'buf' pointer is supposed to be an ARGB15X pixels buffer.
             * This pointer is directly positionned on pixel (box, boy).
             * Buffer is buf_width pixels of width and buf_height pixels of height.
             * buf_bpr gives the number of bytes to add to pass directly
             * to the pixel just below the current position.
             */
            
            /* BBox inside the given buffer (surface units):
             * XMin = x;  XMax = min(maxx, box + buf_width)
             * YMin = y;  YMax = min(maxy, boy + buf_height)
             * When this area is filled, we keep the x (=XMax+1),
             * but set y to the value before this inner loop.
             */

            bx = x-box; /* To remove a compiler warning */
            buf += (y-boy) * pa->bpr / sizeof(*buf);

            DPRINT("BDraw: area = (%ld, %ld, %ld, %ld)\n",
                   x - box, y - boy,
                   MIN(maxx-box, pa->width-1), MIN(maxy-boy, pa->height-1));

            /* Filling one pixel buffer (inner loop)
            ** OPTIMIZATION: using a kind of bresenham algo and remove all float computations ?
            */
#ifdef STAT_TIMING
            ReadCPUClock(&t1);
#endif
            for (by=y-boy; by <= MIN(maxy-boy, pa->width-1); by++) {
                for (bx=x-box; bx <= MIN(maxx-box, pa->height-1); bx++) {
                    FLOAT drx, dry;
                    FLOAT rr, opa = opacity;

                    /* Compute the square of ellipse radius
                     * Note: Why +0.5 for each coordinate? because we put the center of
                     * ellipse in the center of the pixel (pixel positions are integers).
                     */
                    drx = bx+box - sx + 0.5;
                    dry = (by+boy - sy + 0.5) / yratio;
                    rr = (drx*drx + dry*dry) / radius_radius;

                    /* P=(x, y) in the Ellipse ? */
                    if (rr <= 1.0) {
                        /* opacity = p * f(r), where:
                         *   - f is a falloff function
                         *   - r the radius (we using the square radius (rr) in fact)
                         *   - p the pressure
                         *
                         * hardness is the first zero of f (f(hardness)=0.0).
                         * hardness can't be zero (or density = -infinity, clamped to zero)
                         */
                        if (hardness < 1.0) {
                            if (rr < hardness)
                                opa *= rr + 1-(rr/hardness);
                            else
                                opa *= hardness/(hardness-1)*(rr-1);
                        }

                        i = bx * 4; // BUG: change 4 to 5 for CMYK
                        pa->writepixel(&buf[i], opa * target_alpha, color);
                    }
                }

                /* Go to the next row to fill */
                buf += pa->bpr / sizeof(*buf);
            }
#ifdef STAT_TIMING
            ReadCPUClock(&t2);
            self->b_Times[1] += t2 - t1;
            self->b_TimesCount[1]++;
#endif

            /* Written buffer ? */
            if (i >= 0) {
                /* put in the damaged list if not damaged yet */
                if (!pa->damaged) {
                    int failed;
                    
                    failed = PyList_Append(buflist, (PyObject *)pa); /* incref 'pa' */
 
                    if (failed)
                        goto error;

                    pa->damaged = TRUE;
                }
            }

            if (SetSignal(0, SIGBREAKF_CTRL_C) & SIGBREAKF_CTRL_C)
                goto end;

            /* Update x */
            x = bx + box;

            /* Update the y only if x > maxx */
            if (x > maxx)
                y = by + boy;
        }
    }

end:
    return buflist; /* list of damaged buffers */

error:
    return NULL;
}
//-
//+ myrand1
double myrand1(void)
{
    static ULONG seed=0;

    seed = FastRand(seed);
    return ((double)seed) / (double)0xffffffff;
}
//-
//+ myrand2
double myrand2(void)
{
    static ULONG seed=0x1fa9b36;

    seed = FastRand(seed);
    return ((double)seed) / (double)0xffffffff;
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
    if (NULL != self) {
        int i;

        NEWLIST(&self->b_PACacheList);

        for (i=0; i < PA_CACHE_SIZE; i++) {
            ADDTAIL(&self->b_PACacheList, &self->b_PACache[i]);
        }

        self->b_FirstInvalid = &self->b_PACache[0];

        self->b_BaseRadius = 8.0;
        self->b_BaseYRatio = 1.0;
        self->b_Hardness = 0.5;
        self->b_Opacity = 1.0;
        self->b_TargetAlpha = 1.0;

        /* the rest to 0 */
    }

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
//+ brush_drawdab_solid
static PyObject *
brush_drawdab_solid(PyBrush *self, PyObject *args)
{
    LONG sx, sy; /* Center position (surface units) */
    FLOAT pressure; /* Pressure, range =  [0.0, 0.1] */
    FLOAT radius; /* Radius, range =  [0.0, 0.1] */
    FLOAT yratio; /* YRatio, range =  [0.0, inf] */
    FLOAT hardness; /* Hardness, range =  [0.0, inf] */
    PyObject *buflist, *ret;

    if (NULL == self->b_Surface)
        return PyErr_Format(PyExc_RuntimeError, "No surface set.");

    /* Set defaults for optional arguments */
    radius = self->b_BaseRadius;
    yratio = self->b_BaseYRatio;
    hardness = self->b_Hardness;
    pressure = 0.5;

    if (!PyArg_ParseTuple(args, "(kk)|ffff", &sx, &sy,  &pressure, &radius, &yratio, &hardness))
        return NULL;

    CLAMP(0.0, pressure, 1.0);
    CLAMP(0.0, radius, 1.0);

    buflist = PyList_New(0); /* NR */
    if (NULL == buflist)
        return NULL;

    /* Check if have something to draw or just return the empty damaged list */
    if ((0.0 <= hardness) || (yratio <= 0.0) || (0.0 == pressure) || (0.0 == radius))
        return buflist;

    ret = drawdab_solid(self, buflist, self->b_Surface,
                        sx, sy, radius, yratio,
                        hardness, self->b_TargetAlpha, self->b_Opacity);
    if (NULL == ret)
        Py_CLEAR(buflist);

    return buflist;
}
//-
//+ brush_drawstroke
static PyObject *
brush_drawstroke(PyBrush *self, PyObject *args)
{
    PyObject *stroke, *o, *buflist;
    LONG sx, sy;
    LONG dx, dy;
    FLOAT pressure, time, d;
    ULONG i, n;
    
    if (NULL == self->b_Surface)
        return PyErr_Format(PyExc_RuntimeError, "Uninitialized brush");

    /* TODO: yes, stroke is currently a dict object... */
    if (!PyArg_ParseTuple(args, "O!", &PyDict_Type, &stroke))
        return NULL;

    o = PyDict_GetItemString(stroke, "pos"); /* BR */
    if ((NULL == o) || !PyArg_ParseTuple(o, "kk", &sx, &sy))
        return NULL;

    o = PyDict_GetItemString(stroke, "pressure");
    if ((NULL == o) || ((pressure = PyFloat_AsDouble(o)), NULL != PyErr_Occurred()))
        return NULL;

    o = PyDict_GetItemString(stroke, "time");
    if ((NULL == o) || ((time = PyFloat_AsDouble(o)), NULL != PyErr_Occurred()))
        return NULL;

    buflist = PyList_New(0); /* NR */
    if (NULL == buflist)
        return NULL;

    /* TODO: CHANGE ME (Test routine) */
#define DABS_PER_RADIUS 10
#define DABS_PER_SECONDS 0

    dx = sx - self->b_X;
    dy = sy - self->b_Y;

    if ((0 == dx) && (0 == dy))
        return buflist;

    if (self->b_BaseYRatio >= 1.0)
        d = sqrt(dx*dx+dy*dy) * DABS_PER_RADIUS / self->b_BaseRadius;
    else
        d = sqrt(dx*dx+dy*dy) * DABS_PER_RADIUS / (self->b_BaseRadius*self->b_BaseYRatio);

    d += time * DABS_PER_SECONDS;

    n = (ULONG)d;
    //n = MAX(1, n);
    for (i=0; i < n; i++) {
        PyObject *ret;
        LONG x, y;
#ifdef STAT_TIMING
        UQUAD t1, t2;
#endif
        LONG v1 = 0;//(myrand1()*2-1)*1.7;
        LONG v2 = 0;//(myrand2()*2-1)*1.7;

        /* Simple linear interpolation */

        x = self->b_X + (LONG)((float)dx*i/n);
        y = self->b_Y + (LONG)((float)dy*i/n);

        DPRINT("BRUSH: (%ld, %ld), s: (%ld, %ld): c: (%ld, %ld)\n", self->b_X, self->b_Y, sx, sy, x, y);

#ifdef STAT_TIMING
        ReadCPUClock(&t1);
#endif
        ret = drawdab_solid(self, buflist, self->b_Surface,
                            x+v1, y+v2, self->b_BaseRadius, self->b_BaseYRatio,
                            self->b_Hardness, self->b_TargetAlpha, pressure * self->b_Opacity);
#ifdef STAT_TIMING
        ReadCPUClock(&t2);
        self->b_Times[0] += t2 - t1;
        self->b_TimesCount[0]++;   
#endif
        if (NULL == ret) {
            Py_CLEAR(buflist); /* BUG: let pa damaged ! */
            goto end;
        }
    }

    self->b_X = sx;
    self->b_Y = sy;

end:
    return buflist;
}
//-
//+ brush_invalid_cache
static PyObject *
brush_invalid_cache(PyBrush *self, PyObject *args)
{
    ULONG i;

#ifdef STAT_TIMING
    Printf("Cache states: cache accesses = %lu, cache miss = %lu (%lu%%)\n",
        self->b_CacheAccesses, self->b_CacheMiss, (ULONG)(((float)self->b_CacheMiss * 100 / self->b_CacheAccesses) + 0.5));
    
    for (i=0; i < sizeof(self->b_Times)/sizeof(*self->b_Times); i++) {
        float t = (float)self->b_Times[i] / self->b_TimesCount[i] / 33.333333;
        Printf("Time#%lu: %lu\n", i, (ULONG)t);
        self->b_Times[i] = 0;
        self->b_TimesCount[i] = 0;
    }

    self->b_CacheAccesses = 0;
    self->b_CacheMiss = 0;
#endif

    /* invalidate the whole cache */
    for (i=0; i < PA_CACHE_SIZE; i++)
        self->b_PACache[i].pan_Valid = FALSE;
    self->b_FirstInvalid = &self->b_PACache[0];

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
//+ brush_get_float
static PyObject *
brush_get_float(PyBrush *self, void *closure)
{
    FLOAT *ptr = (APTR)self + (ULONG)closure;

    return PyFloat_FromDouble((double)*ptr);
}
//-
//+ brush_set_float
static int
brush_set_float(PyBrush *self, PyObject *value, void *closure)
{
    FLOAT *ptr = (APTR)self + (ULONG)closure;
    DOUBLE v;

    if (NULL == value) {
        *ptr = 0;
        return 0;
    }

    v = PyFloat_AsDouble(value);
    if (PyErr_Occurred())
        return 1;

    *ptr = v;
    return 0;
}
//-
//+ brush_set_normalized_float
static int
brush_set_normalized_float(PyBrush *self, PyObject *value, void *closure)
{
    FLOAT *ptr = (APTR)self + (ULONG)closure;
    DOUBLE v;

    if (NULL == value) {
        *ptr = 0;
        return 0;
    }

    v = PyFloat_AsDouble(value);
    if (PyErr_Occurred())
        return 1;

    *ptr = CLAMP(v, 0.0, 1.0);
    return 0;
}
//-
//+ brush_get_color
static PyObject *
brush_get_color(PyBrush *self, void *closure)
{
    USHORT *ptr = (APTR)self + (ULONG)closure;

    return PyFloat_FromDouble(((DOUBLE)*ptr) / (1<<15));
}
//-
//+ brush_set_color
static int
brush_set_color(PyBrush *self, PyObject *value, void *closure)
{
    USHORT *ptr = (APTR)self + (ULONG)closure;
    DOUBLE v;

    if (NULL == value) {
        *ptr = 0;
        return 0;
    }

    v = PyFloat_AsDouble(value);
    if (PyErr_Occurred())
        return 1;
    
    *ptr = CLAMP(v * (1<<15), 0, 1<<15);
    return 0;
}
//-

static PyGetSetDef brush_getseters[] = {
    {"surface",  (getter)brush_get_surface, (setter)brush_set_surface,          "Surface to use",          NULL},
    {"radius",   (getter)brush_get_float,   (setter)brush_set_float,            "Base radius",             (APTR)offsetof(PyBrush, b_BaseRadius)},
    {"yratio",   (getter)brush_get_float,   (setter)brush_set_float,            "Base Y-ratio",            (APTR)offsetof(PyBrush, b_BaseYRatio)},
    {"hardness", (getter)brush_get_float,   (setter)brush_set_normalized_float, "Hardness",                (APTR)offsetof(PyBrush, b_Hardness)},
    {"opacity",  (getter)brush_get_float,   (setter)brush_set_normalized_float, "Opacity",                 (APTR)offsetof(PyBrush, b_Opacity)},
    {"red",      (getter)brush_get_color,   (setter)brush_set_color,            "Color (Red channel)",     (APTR)offsetof(PyBrush, b_RGBColor[0])},
    {"green",    (getter)brush_get_color,   (setter)brush_set_color,            "Color (Green channel)",   (APTR)offsetof(PyBrush, b_RGBColor[1])},
    {"blue",     (getter)brush_get_color,   (setter)brush_set_color,            "Color (Blue channel)",    (APTR)offsetof(PyBrush, b_RGBColor[2])},
    {"cyan",     (getter)brush_get_color,   (setter)brush_set_color,            "Color (Cyan channel)",    (APTR)offsetof(PyBrush, b_CMYKColor[0])},
    {"magenta",  (getter)brush_get_color,   (setter)brush_set_color,            "Color (Magenta channel)", (APTR)offsetof(PyBrush, b_CMYKColor[1])},
    {"yellow",   (getter)brush_get_color,   (setter)brush_set_color,            "Color (Yellow channel)",  (APTR)offsetof(PyBrush, b_CMYKColor[2])},
    {"key",      (getter)brush_get_color,   (setter)brush_set_color,            "Color (Key channel)",     (APTR)offsetof(PyBrush, b_CMYKColor[3])},

    {NULL} /* sentinel */
};

static struct PyMethodDef brush_methods[] = {
    {"drawdab_solid", (PyCFunction)brush_drawdab_solid, METH_VARARGS, NULL},
    {"draw_stroke",   (PyCFunction)brush_drawstroke, METH_VARARGS, NULL},
    {"invalid_cache", (PyCFunction)brush_invalid_cache, METH_NOARGS, NULL},
    {NULL} /* sentinel */
};

static PyMemberDef brush_members[] = {
    {"x",            T_LONG,   offsetof(PyBrush, b_X), 0, NULL},
    {"y",            T_LONG,   offsetof(PyBrush, b_Y), 0, NULL},
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
    PyObject *m, *_pixarray;

    if (PyType_Ready(&PyBrush_Type) < 0) return;

    m = Py_InitModule(MODNAME, _BrushMethods);
    if (NULL == m) return;

    ADD_TYPE(m, "Brush", &PyBrush_Type);

    /* Need the PyPixelArray_Type object from _pixarray */
    _pixarray = PyImport_ImportModule("_pixarray"); /* NR */
    if (NULL == _pixarray)
        return;

    PyPixelArray_Type = (PyTypeObject *)PyObject_GetAttrString(_pixarray, "PixelArray"); /* NR */
    if (NULL == PyPixelArray_Type) {
        Py_DECREF(_pixarray);
        return;
    }
}
//-
