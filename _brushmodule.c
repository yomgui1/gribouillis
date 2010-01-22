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

#ifdef NDEBUG
#define DPRINT(x, ...)
#else
#define DPRINT dprintf
#endif

#define PyBrush_Check(op) PyObject_TypeCheck(op, &PyBrush_Type)
#define PyBrush_CheckExact(op) ((op)->ob_type == &PyBrush_Type)

#define PA_CACHE_SIZE 15 /* good value for the case of big brushes */
#define DABS_PER_SECONDS 0

//#define STAT_TIMING

#ifdef STAT_TIMING
#include <exec/system.h>
#endif

enum {
    BV_RADIUS=0,
    BV_YRATIO,
    BV_HARDNESS,
    BV_OPACITY,
    BV_ERASE,
    BV_RADIUS_RANDOM,
    BV_DABS_PER_RADIUS,
    BV_GRAIN_FAC,
    BASIC_VALUES_MAX
};

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
    FLOAT           b_Time;
    FLOAT           b_Pressure;
    FLOAT           b_cs, b_sn;

    /* Model for Hermite interpolation */
    FLOAT           b_T1x, b_T1y;
    LONG            b_P1x, b_P1y;
    LONG            b_P2x, b_P2y;
    LONG            b_Start;
    
    FLOAT           b_BasicValues[BASIC_VALUES_MAX];

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

//+ myrand1
FLOAT myrand1(void)
{
    static ULONG seed=0;

    seed = FastRand(seed);
    return (FLOAT)seed / 0xffffffff;
}
//-
//+ myrand2
FLOAT myrand2(void)
{
    static ULONG seed=0x1fa9b36;

    seed = FastRand(seed);
    return (FLOAT)seed / 0xffffffff;
}
//-
//+ myrand3
FLOAT myrand3(void)
{
    static ULONG seed=0x78fb69a1;

    seed = FastRand(seed);
    return (FLOAT)seed / 0xffffffff;
}
//-
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
              FLOAT erase, /* 0.0=erase, 1.0=normal, between = translucent target color */
              FLOAT opacity, /* 0.0=nothing drawn, 1.0=solid, between = translucent color */
              FLOAT cs,
              FLOAT sn)
{
    LONG minx, miny, maxx, maxy, x, y;
    FLOAT radius_radius, grain;
    USHORT *color = NULL;
#ifdef STAT_TIMING
    UQUAD t1, t2;
#endif

    cs = 1.0;
    sn = 0.0;

    DPRINT("BDraw: pos = (%ld, %ld)\n", sx, sy);

    minx = floorf((FLOAT)sx - radius);
    maxx = ceilf((FLOAT)sx + radius);
    miny = floorf((FLOAT)sy - radius);
    maxy = ceilf((FLOAT)sy + radius);
    DPRINT("BDraw: bbox = (%ld, %ld, %ld, %ld) (radius=%f)\n", minx, miny, maxx, maxy, radius);

    /* check if there is really something to draw */
    if ((minx == maxx) || (miny == maxy))
        return buflist;
    
    radius_radius = radius * radius;
    grain = self->b_BasicValues[BV_GRAIN_FAC];

    /* Loop on all pixels inside a bbox centered on (sx, sy) */
    for (y=miny; y <= maxy;) {
        for (x=minx; x <= maxx;) {
            PyPixelArray *pa;
            UBYTE *buf;
            ULONG bx_left, bx_right, by_top, by_bottom;
            ULONG bx, by; /* x, y in buffer space */
            LONG n, i = -1; /* >=0 when some pixels have been written */
            ULONG cx, cy;

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

            n = (pa->bpc * pa->nc) >> 3;

            /* XXX: I consider that all pixelarray have the same color space */
            if (NULL == color) {
                if (pa->pixfmt & PyPixelArray_FLAG_RGB)
                    color = self->b_RGBColor;
                else
                    color = self->b_CMYKColor;
            }

            buf = pa->data;

            /* 'buf' pointer is supposed to be an ARGB15X pixels buffer.
             * This pointer is directly positionned on pixel (box, boy).
             * Buffer is buf_width pixels of width and buf_height pixels of height.
             * buf_bpr gives the number of bytes to add to pass directly
             * to the pixel just below the current position.
             */
            
            /* Computing bbox inside the given buffer (surface units)
             * OPTIMIZE: modulo can be avoided if pa (x,y) are correctly set.
             */
            bx_left = x - pa->x;
            bx_left %= pa->width; /* /!\ modulo of neg is neg... */
            bx_right = MIN(bx_left+(maxx-x), pa->width-1);
            by_top = y - pa->y;
            by_top %= pa->height;
            by_bottom = MIN(by_top+(maxy-y), pa->height-1);

            buf += by_top * pa->bpr;
            
            DPRINT("BDraw: area = (%ld, %ld, %ld, %ld) size=(%lu, %lu)\n",
                bx_left, by_top, bx_right, by_bottom, bx_right-bx_left, by_bottom-by_top);

            /* Filling one pixel buffer (inner loop) */
#ifdef STAT_TIMING
            ReadCPUClock(&t1);
#endif

            /* Ellipse center in buffer coordinates */
            cx = sx - pa->x;
            cy = sy - pa->y;

            for (by=by_top; by <= by_bottom; by++) {
                FLOAT yy = ((LONG)by - (LONG)cy);
                FLOAT yycs = yy*cs;
                FLOAT yysn = yy*sn;

                for (bx=bx_left; bx <= bx_right; bx++) {
                    FLOAT xx, rx, ry, rr, opa, g;

                    xx = (LONG)bx - (LONG)cx;

                    /* Rotation */
                    rx = yysn + xx*cs;
                    ry = (yycs - xx*sn) * yratio;

                    /* Compute the square of pixel radius: rr^2 = rx^2 + ry^2
                     * Divide by the square of the ellipse radius to have
                     * a number relative to this radius.
                     */
                    rr = (rx*rx + ry*ry) / radius_radius;

                    /* (x, y) in the Ellipse ? */
                    if (rr <= 1.) {
                        /* opacity = opacity_base * f(r), where:
                         *   - f is a falloff function
                         *   - r the radius (we using the square radius (rr) in fact)
                         *
                         * hardness is the first zero of f (f(hardness)=0.0).
                         * hardness can't be zero (or density = -infinity, clamped to zero)
                         */
                        opa = opacity;
                        if (hardness < 1.) {
                            if (rr < hardness)
                                opa *= (rr + 1.-(rr/hardness));
                            else
                                opa *= (hardness/(hardness-1.)*(rr-1.));
                        }

                        g = myrand3();
                        if (g <= grain) {
                            FLOAT opa2 = opa*(2.*g/grain-1.);
                            if (opa2 > 1.)
                                opa2 = 1.;
                            else if (opa2 < 0.)
                                opa2 = 0.;
                            opa *= opa2;
                        }
                        i = bx * n;
                        pa->writepixel(&buf[i], opa, erase, color);
                    }
                }

                /* Go to the next row to fill */
                buf += pa->bpr;
            }
#ifdef STAT_TIMING
            ReadCPUClock(&t2);
            self->b_Times[1] += t2 - t1;
            self->b_TimesCount[1]++;
#endif

            /* Pixel(s) written ? */
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

            //if (SetSignal(0, SIGBREAKF_CTRL_C) & SIGBREAKF_CTRL_C)
            //    goto end;
            
            /* Update x */
            x += bx_right - bx_left + 1;

            /* Update the y only if x > maxx */
            if (x > maxx)
                y += by_bottom - by_top + 1;
        }
    }

end:
    return buflist; /* list of damaged buffers */

error:
    return NULL;
}
//-
//+ decay
/* Inspired from http://en.wikipedia.org/wiki/Exponential_decay */
FLOAT decay(FLOAT t, FLOAT tau)
{
    t = -t / tau;
    if (t >= -87.) /* limits says, FLOAT_MIN = 1.17549435E-38 => ~= exp(-87) */
        return expf(-t/tau);
    else
        return 0.0;
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

        self->b_BasicValues[BV_RADIUS] = 2.0;
        self->b_BasicValues[BV_YRATIO] = 1.0;
        self->b_BasicValues[BV_HARDNESS] = 0.5;
        self->b_BasicValues[BV_OPACITY] = 1.0;
        self->b_BasicValues[BV_ERASE] = 1.0;

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
    radius = self->b_BasicValues[BV_RADIUS];
    yratio = self->b_BasicValues[BV_YRATIO];
    hardness = self->b_BasicValues[BV_HARDNESS];
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
                        hardness, self->b_BasicValues[BV_ERASE], self->b_BasicValues[BV_OPACITY], 0.707106, 0.707106);
    if (NULL == ret)
        Py_CLEAR(buflist);

    return buflist;
}
//-
#if 0
//+ brush_drawstroke
static PyObject *
brush_drawstroke(PyBrush *self, PyObject *args)
{
    PyObject *stroke, *o, *buflist;
    LONG sx, sy;
    LONG dx, dy;
    FLOAT radius, yratio, pressure, time, tiltx, tilty, d;
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

    pressure = CLAMP(pressure, 0.0, 1.0); 

    o = PyDict_GetItemString(stroke, "time");
    if ((NULL == o) || ((time = PyFloat_AsDouble(o)), NULL != PyErr_Occurred()))
        return NULL;

    o = PyDict_GetItemString(stroke, "tiltx");
    if (NULL == o) {
        PyErr_Clear();
        tiltx = 0.5;
    } else {
        tiltx = PyFloat_AsDouble(o);
        if (PyErr_Occurred())
            return NULL;
    }

    o = PyDict_GetItemString(stroke, "tilty");
    if (NULL == o) {
        PyErr_Clear();
        tilty = -0.5;
    } else {
        tilty = PyFloat_AsDouble(o);
        if (PyErr_Occurred())
            return NULL;
    }

    buflist = PyList_New(0); /* NR */
    if (NULL == buflist)
        return NULL;

    radius = self->b_BasicValues[BV_RADIUS];
    yratio = CLAMP(self->b_BasicValues[BV_YRATIO], 1.0, 100.0);

    /* Compute movement vector */
    dx = sx - self->b_X;
    dy = sy - self->b_Y;

    /* Apply a discret low-pass filter on it */
    //d = self->b_BasicValues[BV_MOVE_SMOOTH_FAC];
    //dx = d*dx + (1.-d)*self->b_dX;
    //dy = d*dy + (1.-d)*self->b_dY;

    if ((dx != 0) || (dy != 0)) {
        /* Use the final movement vector to compute the brush direction (cos/sin rotation) */
        d = sqrtf(dx*dx + dy*dy);
        self->b_cs = -dy/d;
        self->b_sn = dx/d;
    } else {
        d = 0.0;
    }
   
    /* TODO: how to use tilt? */

    /* Compute final radius */
    radius = CLAMP(radius, 0.01, 128.0);

    /* Number of dabs to draw */
    d *= self->b_BasicValues[BV_DABS_PER_RADIUS] / radius;
    d += time * DABS_PER_SECONDS;

    n = (ULONG)d;
    n = MIN(n, 100);
    for (i=0; i < n; i++) {
        FLOAT r;
        PyObject *ret;
        LONG x, y;
#ifdef STAT_TIMING
        UQUAD t1, t2;
#endif
        LONG v1;
        LONG v2;

        d = (float)i/n;

        /* Radius per dabs */
        r = radius*(self->b_Pressure*(1. - d) + pressure*d);

        v1 = (myrand1()*2-1)*self->b_BasicValues[BV_RADIUS_RANDOM]*r;
        v2 = (myrand2()*2-1)*self->b_BasicValues[BV_RADIUS_RANDOM]*r;

        /* Simple linear interpolation */
        x = self->b_X + (LONG)((float)dx*d) + v1;
        y = self->b_Y + (LONG)((float)dy*d) + v2;

        DPRINT("BRUSH: old: (%ld, %ld), new: (%ld, %ld), int: (%ld, %ld)\n", self->b_X, self->b_Y, sx, sy, x, y);

#ifdef STAT_TIMING
        ReadCPUClock(&t1);
#endif
        ret = drawdab_solid(self, buflist, self->b_Surface,
                            x, y, r, yratio,
                            self->b_BasicValues[BV_HARDNESS],
                            self->b_BasicValues[BV_ERASE],
                            pressure * self->b_BasicValues[BV_OPACITY],
                            self->b_cs, self->b_sn);
#ifdef STAT_TIMING
        ReadCPUClock(&t2);
        self->b_Times[0] += t2 - t1;
        self->b_TimesCount[0]++;
#endif
        
        if (NULL == ret) {
            Py_CLEAR(buflist); /* BUG: let pa damaged ! */
            break;
        }
    }

    self->b_X = sx;
    self->b_Y = sy;
    self->b_dX = dx;
    self->b_dY = dy;
    self->b_Time = time; /* TODO: use it somewhere... */
    self->b_Pressure = pressure;
    
    return buflist;
}
//-
#endif
//+ brush_drawstroke
static PyObject *
brush_drawstroke(PyBrush *self, PyObject *args)
{
    PyObject *stroke, *o, *buflist, *ret;
    LONG sx, sy;
    FLOAT radius, t2x, t2y, d, pressure, time, dx, dy, tiltx, tilty, yratio;
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

    o = PyDict_GetItemString(stroke, "tiltx");
    if (NULL == o) {
        PyErr_Clear();
        tiltx = 0.5;
    } else {
        tiltx = PyFloat_AsDouble(o);
        if (PyErr_Occurred())
            return NULL;
    }

    o = PyDict_GetItemString(stroke, "tilty");
    if (NULL == o) {
        PyErr_Clear();
        tilty = -0.5;
    } else {
        tilty = PyFloat_AsDouble(o);
        if (PyErr_Occurred())
            return NULL;
    }

    buflist = PyList_New(0); /* NR */
    if (NULL == buflist)
        return NULL;

    /* computing dynamic brush parameters */
    radius = self->b_BasicValues[BV_RADIUS];

    /* Compute movement vector */
    dx = self->b_P2x - self->b_P1x;
    dy = self->b_P2y - self->b_P1y;

    /* Brush direction (cos/sin) */
    if ((dx != 0) || (dy != 0)) {
        d = sqrtf(dx*dx + dy*dy);
        self->b_cs = -dy/d;
        self->b_sn = dx/d;
    } else
        d = 0.0;

    /* clamping values */
    radius = CLAMP(radius, 0.01, 128.0);
    pressure = CLAMP(pressure, 0.0, 1.0);
    yratio = CLAMP(self->b_BasicValues[BV_YRATIO], 1.0, 100.0);

    /* Number of dabs to draw */
    d *= self->b_BasicValues[BV_DABS_PER_RADIUS] / radius;
    d += time * DABS_PER_SECONDS;

    n = (ULONG)d;
    n = MAX(self->b_Start+1, MIN(n, 500));

    /* About interpolation:
     * Events points from the user device (tablet/mouse/...)
     * are given by exact positions (well... at the device resolution),
     * but it's discretes positions, no continuity in positions inputs.
     * To make a draw between them I need to interpolate.
     *
     * So it exists two type of interpolation.
     *  1) by interpolating the curve
     *  2) by approximating the curve
     *
     * I don't want to use the second one, as it gives a curve that doesn't
     * pass exactly on control points (ones given by the device).
     * So I'm using here the first method.
     *
     * And specially use Hermite Interpolation: this type is able to
     * do the job with only 2 points, if you give derivatives for each ones.
     *
     * Really handy, because points are coming in real time: we don't have
     * all points when computation start, but one by one.
     * As I need to draw something before that the user stop to move the device,
     * it's not possible to wait this moment before to reach the minimal
     * number of points to compute the spline.
     *
     * With Hermite interpolation, I just need 2 points and derivatives for
     * each one (derivative = tangent at the point).
     *
     * So the problem is now to compute these tangents...
     * I'm using Kochanek-Bartels tangents fomulations!
     * (see http://en.wikipedia.org/wiki/Kochanek-Bartels_spline)
     *
     * My implementation compute a spline between 2 points: P1, P2.
     * But need in fact 3 points (add P3) and suppose that T1 tangent is known.
     * I take notation in the previous URL, I've got T1=d(1) and I try to compute T2=d(2).
     *
     * d(2) = ([(1-t)*(1+b)*(1-c)]*(P2-P1) + [(1-t)*(1-b)*(1+c)]*(P3-P2)) * 0.5
     *
     * That cause in the rendering to wait 3 points before starting to draw the spline
     * between the first two points. So a special process shall be done to finish the curve
     * when user raise up the pen (or release the mouse button, etc).
     *
     * After some tests, I choose to fix tension (t, )bias (b) and continuity (c)
     * to (1.0, 0.0, 0.0) giving Catmull splines.
     */

    /* Computing T2 */
    t2x = ((self->b_P2x - self->b_P1x) + (sx - self->b_P2x)) * .5;
    t2y = ((self->b_P2y - self->b_P1y) + (sy - self->b_P2y)) * .5 ;

    /* Now interpolate using Hermite spline formula */
    for (i=self->b_Start; i < n; i++) {
        double t = (double)i / ((n>1)?(n-1):n);
        double t2 = t*t;
        double t3 = t*t*t;
        double h1 =  2*t3 - 3*t2 + 1;
        double h2 = -2*t3 + 3*t2;
        double h3 =    t3 - 2*t2 + t;
        double h4 =    t3 -   t2;
        double vx, vy, r;
        LONG x, y;
        
        /* Radius per dabs */
        r = radius * (self->b_Pressure*(1.-t) + pressure*t);

        vx = (myrand1()*2.-1.)*self->b_BasicValues[BV_RADIUS_RANDOM]*r;
        vy = (myrand2()*2.-1.)*self->b_BasicValues[BV_RADIUS_RANDOM]*r;

        x = h1*self->b_P1x + h2*self->b_P2x + h3*self->b_T1x + h4*t2x + vx + .5;
        y = h1*self->b_P1y + h2*self->b_P2y + h3*self->b_T1y + h4*t2y + vy + .5;

        ret = drawdab_solid(self, buflist, self->b_Surface,
                            x, y, r, yratio,
                            self->b_BasicValues[BV_HARDNESS],
                            self->b_BasicValues[BV_ERASE],
                            pressure * self->b_BasicValues[BV_OPACITY],
                            self->b_cs, self->b_sn);

        if (NULL == ret) {
            Py_CLEAR(buflist); /* BUG: let pa damaged ! */
            break;
        }
    }

    /* Now P2 => P1, P3 => P2, T2 => T1 */
    self->b_P1x = self->b_P2x;
    self->b_P1y = self->b_P2y;
    self->b_P2x = sx;
    self->b_P2y = sy;
    self->b_T1x = t2x;
    self->b_T1y = t2y;
    self->b_Pressure = pressure;
    self->b_Time = time; /* TODO: use it somewhere... */
    self->b_Start = 1;

    return buflist;
}
//-
//+ brush_invalid_cache
static PyObject *
brush_invalid_cache(PyBrush *self)
{
    ULONG i;

#ifdef STAT_TIMING
    ULONG tbclockfreq=0;

    Printf("Cache states: cache accesses = %lu, cache miss = %lu (%lu%%)\n",
        self->b_CacheAccesses, self->b_CacheMiss, (ULONG)(((float)self->b_CacheMiss * 100 / self->b_CacheAccesses) + 0.5));
    
    if (!NewGetSystemAttrs(&tbclockfreq,sizeof(tbclockfreq),SYSTEMINFOTYPE_TBCLOCKFREQUENCY,TAG_DONE))
        tbclockfreq = 33333333;

    for (i=0; i < sizeof(self->b_Times)/sizeof(*self->b_Times); i++) {
        float t = ((float)self->b_Times[i] / self->b_TimesCount[i] / tbclockfreq) * 10e6;
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
//+ brush_get_states
static PyObject *
brush_get_states(PyBrush *self)
{
    return PyBuffer_FromReadWriteMemory((APTR)self->b_BasicValues, sizeof(self->b_BasicValues));
}
//-
//+ brush_get_state
static PyObject *
brush_get_state(PyBrush *self, PyObject *args)
{
    ULONG index;

    if (!PyArg_ParseTuple(args, "I", &index))
        return NULL;

    if (index >= BASIC_VALUES_MAX)
        return PyErr_Format(PyExc_IndexError, "index shall be lower than %u", BASIC_VALUES_MAX);

    return PyFloat_FromDouble((double)self->b_BasicValues[index]);
}
//-
//+ brush_set_state
static PyObject *
brush_set_state(PyBrush *self, PyObject *args)
{
    ULONG index;
    FLOAT value;

    if (!PyArg_ParseTuple(args, "If", &index, &value))
        return NULL;

    if (index >= BASIC_VALUES_MAX)
        return PyErr_Format(PyExc_IndexError, "index shall be lower than %u", BASIC_VALUES_MAX);

    self->b_BasicValues[index] = value;

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
brush_get_float(PyBrush *self, int index)
{
    FLOAT *ptr = &self->b_BasicValues[index];

    return PyFloat_FromDouble((double)*ptr);
}
//-
//+ brush_set_float
static int
brush_set_float(PyBrush *self, PyObject *value, int index)
{
    FLOAT *ptr = &self->b_BasicValues[index];
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
brush_set_normalized_float(PyBrush *self, PyObject *value, int index)
{
    FLOAT *ptr = &self->b_BasicValues[index];
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
    {"surface", (getter)brush_get_surface, (setter)brush_set_surface, "Surface to use", NULL},

    {"radius",            (getter)brush_get_float, (setter)brush_set_float,            "Radius",   (APTR)BV_RADIUS},
    {"yratio",            (getter)brush_get_float, (setter)brush_set_float,            "Y-ratio",  (APTR)BV_YRATIO},
    {"hardness",          (getter)brush_get_float, (setter)brush_set_normalized_float, "Hardness", (APTR)BV_HARDNESS},
    {"opacity",           (getter)brush_get_float, (setter)brush_set_normalized_float, "Opacity",  (APTR)BV_OPACITY},
    {"erase",             (getter)brush_get_float, (setter)brush_set_normalized_float, "Erase",    (APTR)BV_ERASE},
    {"radius_random",     (getter)brush_get_float, (setter)brush_set_float,            "Radius Randomize", (APTR)BV_RADIUS_RANDOM},
    {"dabs_per_radius",   (getter)brush_get_float, (setter)brush_set_float,            "Dabs per radius", (APTR)BV_DABS_PER_RADIUS},
    {"grain",             (getter)brush_get_float, (setter)brush_set_normalized_float, "Grain factor", (APTR)BV_GRAIN_FAC},

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
    {"get_states",    (PyCFunction)brush_get_states, METH_NOARGS, NULL},
    {"get_state",    (PyCFunction)brush_get_state, METH_VARARGS, NULL},
    {"set_state",    (PyCFunction)brush_set_state, METH_VARARGS, NULL},
    {NULL} /* sentinel */
};

static PyMemberDef brush_members[] = {
    {"pressure",     T_FLOAT,  offsetof(PyBrush, b_Pressure), 0, NULL},
    {"t1x",          T_FLOAT,  offsetof(PyBrush, b_T1x), 0, NULL},
    {"t1y",          T_FLOAT,  offsetof(PyBrush, b_T1y), 0, NULL},
    {"p1x",          T_LONG,   offsetof(PyBrush, b_P1x), 0, NULL},
    {"p1y",          T_LONG,   offsetof(PyBrush, b_P1y), 0, NULL},
    {"p2x",          T_LONG,   offsetof(PyBrush, b_P2x), 0, NULL},
    {"p2y",          T_LONG,   offsetof(PyBrush, b_P2y), 0, NULL},
    {"start",        T_LONG,   offsetof(PyBrush, b_Start), 0, NULL},
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

//+ add_constants
static int add_constants(PyObject *m)
{
    INSI(m, "BV_RADIUS", BV_RADIUS);
    INSI(m, "BV_YRATIO", BV_YRATIO);
    INSI(m, "BV_HARDNESS", BV_HARDNESS);
    INSI(m, "BV_OPACITY", BV_OPACITY);
    INSI(m, "BV_ERASE", BV_ERASE);
    INSI(m, "BV_RADIUS_RANDOM", BV_RADIUS_RANDOM);
    INSI(m, "BV_DABS_PER_RADIUS", BV_DABS_PER_RADIUS);
    INSI(m, "BV_GRAIN_FAC", BV_GRAIN_FAC);
    INSI(m, "BASIC_VALUES_MAX", BASIC_VALUES_MAX);

    return 0;
}
//-
//+ INITFUNC()
PyMODINIT_FUNC
INITFUNC(void)
{
    PyObject *m, *_pixarray;

    if (PyType_Ready(&PyBrush_Type) < 0) return;

    m = Py_InitModule(MODNAME, _BrushMethods);
    if (NULL == m) return;

    if (add_constants(m)) return;

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
