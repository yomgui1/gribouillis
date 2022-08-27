/******************************************************************************
Copyright (c) 2009-2013 Guillaume Roguez

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

//#define STAT_TIMING 1

#include "common.h"
#include "_pixbufmodule.h"
#include "math.h"

#include <string.h>

#ifndef INITFUNC
#define INITFUNC PyInit__brush
#endif

#ifndef MODNAME
#define MODNAME "_brush"
#endif

#ifdef NDEBUG
#define DPRINT(x, ...)
#else
#define DPRINT dprintf
#endif

//#define DPRINT printf

#define PyBrush_Check(op) PyObject_TypeCheck(op, &PyBrush_Type)
#define PyBrush_CheckExact(op) ((op)->ob_type == &PyBrush_Type)

#define PB_CACHE_SIZE 15 /* good value for the case of big brushes */
#define DABS_PER_SECONDS 0

#define HERMITE_NUMPOINTS 3

//#define STAT_TIMING

#define GET_INT_FROM_STROKE(state, var, name) \
    { PyObject *_o = PyObject_GetAttrString(state, name); \
    if (NULL == _o) return NULL; \
    else if (!PyInt_CheckExact(_o)) \
    { Py_DECREF(_o); return PyErr_Format(PyExc_TypeError, "Invalid '%s' attribute in stroke", name); } \
    var = PyInt_AS_LONG(_o); Py_DECREF(_o); }

#define GET_FLOAT_FROM_STROKE(state, var, name) \
    { PyObject *_o = PyObject_GetAttrString(state, name); \
    if (NULL == _o) return NULL; \
    else if (!PyFloat_CheckExact(_o)) \
    { Py_DECREF(_o); return PyErr_Format(PyExc_TypeError, "Invalid '%s' attribute in stroke", name); } \
    var = PyFloat_AS_DOUBLE(_o); Py_DECREF(_o); }

#define GET_2T_FLOAT_FROM_STROKE(state, var0, var1, name) \
    { PyObject *_o = PyObject_GetAttrString(state, name); \
    if (NULL == _o) return NULL; \
    else if (!PyTuple_CheckExact(_o)) \
    { Py_DECREF(_o); return PyErr_Format(PyExc_TypeError, "Invalid '%s' attribute in stroke", name); } \
    var0 = PyFloat_AsDouble(PyTuple_GET_ITEM(_o, 0)); \
    var1 = PyFloat_AsDouble(PyTuple_GET_ITEM(_o, 1)); \
    Py_DECREF(_o); }

#define GET_2T_INT_FROM_STROKE(state, var0, var1, name) \
    { PyObject *_o = PyObject_GetAttrString(state, name); \
    if (NULL == _o) return NULL; \
    else if (!PyTuple_CheckExact(_o)) \
    { Py_DECREF(_o); return PyErr_Format(PyExc_TypeError, "Invalid '%s' attribute in stroke", name); } \
    var0 = PyInt_AsLong(PyTuple_GET_ITEM(_o, 0)); \
    var1 = PyInt_AsLong(PyTuple_GET_ITEM(_o, 1)); \
    Py_DECREF(_o); }


enum
{
    BV_RADIUS_MIN=0,
    BV_RADIUS_MAX,
    BV_YRATIO,
    BV_ANGLE,
    BV_HARDNESS,
    BV_OPACITY_MIN,
    BV_OPACITY_MAX,
    BV_OPACITY_COMPENSATION,
    BV_ERASE,
    BV_SPACING,
    BV_GRAIN_FAC,
    BV_MOTION_TRACK,
    BV_HI_SPEED_TRACK,
    BV_SMUDGE,
    BV_SMUDGE_VAR,
    BV_DIRECTION_JITTER,
    BV_DAB_POS_JITTER,
    BV_DAB_RADIUS_JITTER,
    BV_COLOR_SHIFT_H,
    BV_COLOR_SHIFT_S,
    BV_COLOR_SHIFT_V,
    BV_ALPHA_LOCK,
    BASIC_VALUES_MAX
};

struct PBNode;
typedef struct PBNode
{
    struct PBNode * pbn_Previous;
    struct PBNode * pbn_Next;
    PyObject *      pbn_Pixbuf;
    int             pbn_Valid;
} PBNode;

typedef struct MyRec
{
    int32_t x1, y1;
    int32_t x2, y2;
} MyRec;

typedef struct
{
    int     p_IX, p_IY;
    float   p_SX, p_SY;
    float   p_SXo, p_SYo;
    float   p_XTilt, p_YTilt;
    double  p_Time;
    float   p_Pressure;
    float   p_Radius;
    float   p_Opacity;
} Point;

typedef struct PyBrush
{
    PyObject_HEAD

    /* Object Data */
    PyObject *      b_Surface;
    PyObject *      b_GetPixBufFunc; /* cached method from b_Surface */
    PBNode          b_PBCache[PB_CACHE_SIZE];
    PBNode *        b_PBFirst;
    PBNode *        b_PBLast;
    PBNode *        b_FirstInvalid;

    /* Brush Model */
    float           b_RemainSteps; /* remaining dabs between last drawn dabs and last control knot */
    float           b_cs, b_sn;

    int             b_PointIndex;
    int             b_NeededPoints;
    float           b_SmudgeColor[4];
    Point           b_Points[4];

    float           b_BasicValues[BASIC_VALUES_MAX];

    float           b_HSVColor[3]; /* HSV colorspace */
    float           b_RGBColor[3]; /* RGB colorspace */
    float           b_Color[3];    /* Stroke saving */

#ifdef STAT_TIMING
    unsigned int    b_CacheAccesses;
    unsigned int    b_CacheMiss;
    uint64_t        b_Times[3];
    unsigned int    b_TimesCount[3];
#endif

} PyBrush;

static PyTypeObject PyBrush_Type;

#define CS_TABLE_SIZE 2048

static float fixed_cos[CS_TABLE_SIZE];
static float fixed_sin[CS_TABLE_SIZE];


/*********************************************************************************
** Private routines
*/

#ifdef STAT_TIMING

/* Code from Python sources (ceval.c) */
#if defined(__PPC__)
#define READ_TIMESTAMP(var) ppc_getcounter(&var)
static void
ppc_getcounter(uint64_t *v)
{
    register unsigned long tbu, tb, tbu2;

  loop:
    asm volatile ("mftbu %0" : "=r" (tbu) );
    asm volatile ("mftb  %0" : "=r" (tb)  );
    asm volatile ("mftbu %0" : "=r" (tbu2));
    if (__builtin_expect(tbu != tbu2, 0)) goto loop;

    /* The slightly peculiar way of writing the next lines is
       compiled better by GCC than any other way I tried. */
    ((long*)(v))[0] = tbu;
    ((long*)(v))[1] = tb;
}

#elif defined(__i386__)

/* this is for linux/x86 (and probably any other GCC/x86 combo) */

#define READ_TIMESTAMP(val) \
     __asm__ __volatile__("rdtsc" : "=A" (val))

#elif defined(__x86_64__)

/* for gcc/x86_64, the "A" constraint in DI mode means *either* rax *or* rdx;
   not edx:eax as it does for i386.  Since rdtsc puts its result in edx:eax
   even in 64-bit mode, we need to use "a" and "d" for the lower and upper
   32-bit pieces of the result. */

#define READ_TIMESTAMP(val) \
    __asm__ __volatile__("rdtsc" : \
                         "=a" (((int*)&(val))[0]), "=d" (((int*)&(val))[1]));


#else
#error "Don't know how to implement timestamp counter for this architecture"
#endif

#define START_TIMER(b, i) ({ READ_TIMESTAMP(b->b_Times[i]); })
#define STOP_TIMER(b, i) ({						\
	  uint64_t t;								\
	  READ_TIMESTAMP(t);						\
	  b->b_Times[i] = t - b->b_Times[i];		\
	  b->b_TimesCount[i]++;						\
	})

#else

#define START_TIMER(b, i)
#define STOP_TIMER(b, i)

#endif /* STAT_TIMING */

static PyPixbuf *
obtain_pixbuffer(PyBrush *self, PyObject *surface, int x, int y)
{
    PyObject *cached = NULL, *o = NULL;
    PBNode *node, *first_invalid = NULL;

#ifdef STAT_TIMING
    self->b_CacheAccesses++;
#endif

    /* Find the (x,y) point pixbuf container
     * by using cached ones first.
     */
    node = self->b_PBFirst;
    while (NULL != node)
    {
        PyPixbuf *pb;

        /* Stop on first invalid node */
        if (!node->pbn_Valid)
        {
            first_invalid = node;
            break;
        }

        pb = (void *)node->pbn_Pixbuf;

        /* (x,y) hits the pixbuf ? */
        if ((x >= pb->x) && (x < (pb->x + pb->width))
            && (y >= pb->y) && (y < (pb->y + pb->height)))
        {
            o = cached = (void *)pb;

            /* Put this node in first (next call will be faster) */
            if (self->b_PBFirst != node)
            {
                node->pbn_Previous->pbn_Next = node->pbn_Next;

                if (node->pbn_Next)
                    node->pbn_Next->pbn_Previous = node->pbn_Previous;
                else
                    self->b_PBLast = node->pbn_Previous;

                node->pbn_Previous = NULL;
                node->pbn_Next = self->b_PBFirst;
                self->b_PBFirst->pbn_Previous = node;
                self->b_PBFirst = node;
            }

            break;
        }

        node = node->pbn_Next;
    }

    if (NULL != first_invalid)
        self->b_FirstInvalid = first_invalid;
    else
        self->b_FirstInvalid = self->b_PBLast;

    /* Not in cache, so ask to the surface to give it */
    if (NULL == cached)
    {
#ifdef STAT_TIMING
        self->b_CacheMiss++;
#endif
        PyObject *args = PyTuple_New(2); /* NR */

        if (NULL == args)
            return NULL;

        /* A bit dangerous in theory (no errors checking)
         * but harmless in pratice as the tuple deallocation
         * will call Py_XDECREF() on each items.
         */
        PyTuple_SET_ITEM(args, 0, PyInt_FromLong(x));
        PyTuple_SET_ITEM(args, 1, PyInt_FromLong(y));

        /* Call the cached get_pixbuf surface method */
        o = PyObject_Call(self->b_GetPixBufFunc, args, NULL); /* NR */
        Py_DECREF(args);

        if (NULL == o)
            return NULL;

        if (o == Py_None)
            return (void *)-1;

        /* the object is supposed to exist until the end of stroke.
         * So decref it now is supposed to not delete the object.
         */
        Py_DECREF(o);

        if (!PyPixbuf_Check(o))
            return (void *)PyErr_Format(PyExc_TypeError,
                                        "Surface get_pixbuf() method shall return Pixbuf instance only, not %s",
                                        OBJ_TNAME(o));

        /* Take the first invalid room, replace pixbuf by this one,
         * and add it to the cache as first entry.
         */
        self->b_FirstInvalid->pbn_Pixbuf = o;
        self->b_FirstInvalid->pbn_Valid = TRUE;
        node = self->b_FirstInvalid;
        if (self->b_PBFirst != node)
        {
            node->pbn_Previous->pbn_Next = node->pbn_Next;

            if (node->pbn_Next)
                node->pbn_Next->pbn_Previous = node->pbn_Previous;
            else
                self->b_PBLast = node->pbn_Previous;

            node->pbn_Previous = NULL;
            node->pbn_Next = self->b_PBFirst;
            self->b_PBFirst->pbn_Previous = node;
            self->b_PBFirst = node;
        }
    }

    return (void *)o;
}

/* Solid elliptical filling engine */
static int
drawdab_solid(PyBrush *self,        /* In: brush object */
              MyRec *area,          /* In/Out: dirty area */
              PyObject *surface,    /* In: pixels surface */
              float sx, float sy,   /* In: dab position on surface */
              float radius,         /* In: dab radius */
              float yratio,         /* In: dab y/x ratios */
              float hardness,       /* In: dab edge hardness (Never set it to 0.0!) */
              float alpha,          /* In: color alpha value */
              float opacity,        /* In: 0.0=nothing drawn, 1.0=solid, between = translucent color */
              float cs,
              float sn,
              float *color          /* In: solid color (no alpha) */
    )
{
    int minx, miny, maxx, maxy, x, y, need_color=TRUE;
    float grain;
    uint16_t native_color[MAX_CHANNELS];

    DPRINT("BDraw: pos=(%f, %f), radius=%f\n", sx, sy, radius);

    /* Compute dab bounding box
     * FIXME: yratio is not used here,
     * not optimal for big radius and small ratio.
     */
    /* draw something even when radius is below 1 */
    float rad_box = radius + .5;
    minx = floorf(sx - rad_box);
    maxx = ceilf(sx + rad_box);
    miny = floorf(sy - rad_box);
    maxy = ceilf(sy + rad_box);

    DPRINT("BDraw: bbox = (%d, %d, %d, %d) (radius=%f)\n", minx, miny, maxx, maxy, radius);

    /* used for optimize the refresh */
    area->x1 = MIN(area->x1, minx);
    area->y1 = MIN(area->y1, miny);
    area->x2 = MAX(area->x2, maxx);
    area->y2 = MAX(area->y2, maxy);

    DPRINT("BDraw: update area = (%ld, %ld, %ld, %ld)\n",
            area->x1, area->y1, area->x2, area->y2);

    grain = self->b_BasicValues[BV_GRAIN_FAC] * radius;

    cs /= radius;
    sn /= radius;

    /* Ellipse radius derivatives */
    float rxdx = cs;
    float rydx = -sn*yratio;
    float rxdy = sn;
    float rydy = cs*yratio;

    /* Loop on all pixels inside a bbox centered on (sx, sy) */
    for (y=miny; y <= maxy;)
    {
        for (x=minx; x <= maxx;)
        {
            PyPixbuf *pb;
            uint8_t *buf;
            unsigned int bx_left, bx_right, by_top, by_bottom;
            unsigned int bx, by; /* x, y in buffer space */
            int bpp;

            START_TIMER(self, 2);

			/* Try to obtain the surface pixels buffer containing point (x, y) */
            pb = obtain_pixbuffer(self, surface, x, y);

            STOP_TIMER(self, 2);

            if (NULL == pb)
                return -1;

            if ((void *)-1 == pb)
            {
                x++;
                goto next_pixel;
            }

            writefunc writepixel;

            if (self->b_BasicValues[BV_ALPHA_LOCK] && pb->writepixel_alpha_locked)
                writepixel = pb->writepixel_alpha_locked;
            else
                writepixel = pb->writepixel;

            if (need_color)
            {
                int j;
                for (j=0; j < pb->nc-1; j++)
                    pb->cfromfloat(color[j], &native_color[j]);
                need_color = FALSE;
            }

            /* 'buf' pointer is supposed to be an ARGB15X pixels buffer.
             * This pointer is directly positionned on pixel (box, boy).
             * Buffer is buf_width pixels of width and buf_height pixels of height.
             * buf_bpr gives the number of bytes to add to pass directly
             * to the pixel just below the current position.
             */

            /* Computing bbox inside the given buffer (surface units)
             * OPTIMIZE: we trust in obtain_pixbuffer() results so modulo
             * is avoided to check bounds.
             */
            bx_left = x - pb->x;
            bx_right = MIN(bx_left+(maxx-x), pb->width-1);
            by_top = y - pb->y;
            by_bottom = MIN(by_top+(maxy-y), pb->height-1);

            /* Shift pixel pointer on the line containing the first pixel to process */
            bpp = (pb->bpc * pb->nc) >> 3;
            buf = pb->data + by_top*pb->bpr;

            DPRINT("BDraw: area = (%ld, %ld, %ld, %ld) size=(%lu, %lu)\n",
                   bx_left, by_top, bx_right, by_bottom,
                   bx_right-bx_left, by_bottom-by_top);

            START_TIMER(self, 1);

            /* linear coef. to compute pixels distance from center
             * using a scanline processing.
             * This is just a simple ellipse computation evaluated for each pixels,
             * using left to right and top to bottom processing.
             */

            /* Set origin at the ellipse center, pixel centered */
            float xx0 = (float)x - sx + .5;
            float yy0 = (float)y - sy + .5;

            /* Radius vector of the top-left pixel, taking care of direction */
            float rxy = xx0*rxdx + yy0*rxdy;
            float ryy = xx0*rydx + yy0*rydy;

			/* Filling one pixel buffer (inner loop) */
			int damaged = 0;
            for (by=by_top; by <= by_bottom; by++, rxy += rxdy, ryy += rydy, buf += pb->bpr)
            {
                uint8_t *pixel = buf + bx_left*bpp; /* X-axis offset */
                float rx = rxy;
                float ry = ryy;

                for (bx=bx_left; bx <= bx_right; bx++, rx += rxdx, ry += rydx, pixel += bpp)
                {
                    /* Compute the square of pixel radius: rr^2 = rx^2 + ry^2
                     * Divide by the square of the ellipse radius to have
                     * a number relative to this radius (done in cs,sn).
                     * Here this division is done during computation of rx and ry.
                     * Any point (x,y) is inside the ellipse, when the distance from
                     * the center is bellow or equal to the ellipse's radius.
                     *
                     * Note: one major problem of this method occures when the radius is large,
                     * as the wasted surface of pixels (pixels where the following condition is false)
                     * has a quadratic grow (Sw(r) = (4-pi) * r^2).
                     */

                    float rr = rx*rx + ry*ry;

                    if (rr <= 1.0)
                    {
                        float opa = opacity;

						/* Computing inner opacity using hardness value
						 * as split point between two linear interpolations:
						 * - zz <= hardness: between opacity and opacity * hardness
						 * - zz >= hardness: between opacity * hardness and zero
						 *
						 * This gives a simple falloff function for zz in [0, 1]
						 */
                        if (hardness < 1.0)
                        {
                            if (rr < hardness)
								opa *= rr + 1.0-(rr/hardness);
                            else
								opa *= hardness/(1.0-hardness)*(1.0-rr);
                        }

						/* add a grain factor to opacity */
                        if (grain > 0)
                        {
                            float noise = (noise_2d(sx + rx*grain, sy + ry*grain)+1.)*.5;

                            opa = MIN(opa * noise, 1.0);
                        }

                        writepixel(pixel, opa, alpha, native_color);
						damaged = 1;
                    }
                }
            }
			pb->damaged = damaged;

			STOP_TIMER(self, 1);

            /* Update x */
            x += bx_right - bx_left + 1;

next_pixel:
            /* Update the y only if x > maxx */
            if (x > maxx)
                y += by_bottom - by_top + 1;
        }
    }

    DPRINT("BDraw: done\n");
    return 0;
}

/* Get the average color under a dabs */
static int
get_dab_color(PyBrush *self,       /* In: */
              PyObject *surface,   /* In: Give information on color space also */
              float sx, float sy,  /* In: Dabs center on the given surface */
              float radius,        /* In: Dabs radius in pixels */
              float yratio,        /* In: Dabs y/x ratio */
              float hardness,      /* In: Dabs hardness => gives the pixel weight */
              float cs,            /* In: Dabs angle (cosinus) */
              float sn,            /* In: Dabs angle (sinus) */
              float *color         /* Out: resulting color */
    )
{
    float sums[MAX_CHANNELS], sum_weight;
    int minx, miny, maxx, maxy, x, y, i, chan_count;

    /* WARNING: code duplication with drawdab_solid */

    /* Compute dab bounding box (XXX: yratio?) */
    float rad_box = radius + .5;
    minx = floorf(sx - rad_box);
    maxx = ceilf(sx + rad_box);
    miny = floorf(sy - rad_box);
    maxy = ceilf(sy + rad_box);

    /* Prepare some data */
    sum_weight = 0.0;
    bzero(sums, sizeof(sums));

    /* TODO: CYMK handling */
    chan_count = 4; /* RGBA */

    cs /= radius;
    sn /= radius;

    /* Radius derivatives */
    float rxdx = cs;
    float rydx = -sn*yratio;
    float rxdy = sn;
    float rydy = cs*yratio;

    /* Loop on all pixels inside a bbox centered on (sx, sy) */
    for (y=miny; y <= maxy;)
    {
        for (x=minx; x <= maxx;)
        {
            PyPixbuf *pb;
            uint8_t *buf;
            unsigned int bx_left, bx_right, by_top, by_bottom;
            unsigned int bx, by; /* x, y in buffer space */
            int bpp;

            /* Try to obtain the surface pixels buffer for the point (x, y).
            ** Search in internal cache for it, then ask directly to the surface object.
            **/

            pb = obtain_pixbuffer(self, surface, x, y);
            if (NULL == pb)
                return -1;

            if ((void *)-1 == pb)
            {
                x++;
                by_top = miny;
                by_bottom = maxy;
                goto next_pixel;
            }

            bx_left = x - pb->x;
            bx_right = MIN(bx_left+(maxx-x), pb->width-1);
            by_top = y - pb->y;
            by_bottom = MIN(by_top+(maxy-y), pb->height-1);

            bpp = (pb->bpc * pb->nc) >> 3;
            buf = pb->data + by_top*pb->bpr;

            float xx0 = (float)x - sx + .5;
            float yy0 = (float)y - sy + .5;
            float rxy = xx0*rxdx + yy0*rxdy;
            float ryy = xx0*rydx + yy0*rydy;

            for (by=by_top; by <= by_bottom; by++, rxy += rxdy, ryy += rydy, buf += pb->bpr)
            {
                uint8_t *pixel = buf + bx_left*bpp;
                float rx = rxy;
                float ry = ryy;

                for (bx=bx_left; bx <= bx_right; bx++, rx += rxdx, ry += rydx, pixel += bpp)
                {
                    float rr = rx*rx + ry*ry;
                    if (rr <= 1.0)
                    {
                        float opa;
                        uint16_t tmp_color[MAX_CHANNELS];

                        opa = 1.0; /* start at full opacity */
                        if (hardness < 1.0)
                        {
                            if (rr < hardness)
                                opa *= rr + 1.0-(rr/hardness);
                            else
                                opa *= hardness/(1.0-hardness)*(1.0-rr);
                        }
                        sum_weight += opa;

                        /* Get color as native values (alpha always last) */
                        pb->readpixel(pixel, tmp_color);

                        /* Convert to float, weight and add to the sum  */
                        for (i=0; i<chan_count; i++)
                            sums[i] += opa * pb->ctofloat(&tmp_color[i]);
                    }
                }
            }

            /* Update x */
            x += bx_right - bx_left + 1;

next_pixel:
            /* Update the y only if x > maxx */
            if (x > maxx)
                y += by_bottom - by_top + 1;
        }
    }

    /* no weight => no color => full transparency */
    if (!sum_weight)
        return 1;

    /* Average alpha (always the last item) */
    float alpha_sum = sums[chan_count-1];

    color[chan_count-1] = alpha_sum / sum_weight;
    if (color[chan_count-1] >= (1.0 / (1 << 15)))
    {
        /* colors are alpha-premultiplied, so un-multiply it now */
        /* FIXME: it's not always the truth! */
        for (i=0; i<chan_count-1; i++)
        {
            /* OPTIM: no need to divide color by weight sum as alpha sum is also weighted */
            color[i] = CLAMP(sums[i] / alpha_sum, 0.0, 1.0); /* fix rounding errors */
        }
    }
    else
    {
        /* fully transparent color */
        //printf("%f\n", color[chan_count-1]);
        bzero(color, sizeof(color));
        color[0] = 1.0; /* to see if alpha is not taken in account */

        //return 1;
    }

    return 0;
}

static float
decay(float t, float tau)
{
    /* Inspired from http://en.wikipedia.org/wiki/Exponential_decay */

    t = -t / tau;
    if (t >= -87.) /* limits says, float_MIN = 1.17549435E-38 => ~= exp(-87) */
        return expf(t);
    else
        return 0.0;
}

static int
process_smudge(PyBrush *self,
               float x, float y,
               float radius, float yratio,
               float cs, float sn,
               float hardness,
               float *color, float *alpha)
{
    int i, err;
    float fac, avg_color[MAX_CHANNELS];

    if (self->b_BasicValues[BV_SMUDGE] == 0.0)
    {
        *alpha = 1.0;
        return 0;
    }

    fac = self->b_BasicValues[BV_SMUDGE];
    *alpha = 1.0*(1.0-fac) + self->b_SmudgeColor[3]*fac;

    if (*alpha > 0.0)
    {
        /* blender smudge color with given color */
        for (i=0; i<3; i++)
            color[i] = (color[i]*(1.0-fac) + self->b_SmudgeColor[i]*fac) / *alpha;
    }
    else
    {
        color[0] = 1.0; /* for bug tracking */
        color[1] = 0.0;
        color[2] = 0.0;
    }

    /* Get the average color under the brush */
    err = get_dab_color(self, self->b_Surface,
                        x, y, radius, yratio, hardness,
                        cs, sn, avg_color);
    if (err < 0) return 1;

    /* fully transparent? */
    /*if (err > 0) return 0;*/

    fac = self->b_BasicValues[BV_SMUDGE_VAR];
    if (fac > 0.0)
    {
        self->b_SmudgeColor[3] = self->b_SmudgeColor[3]*(1.0-fac) + avg_color[3]*fac;
        for (i=0; i<3; i++)
            self->b_SmudgeColor[i] = self->b_SmudgeColor[i]*(1.0-fac) + avg_color[i]*avg_color[3]*fac;
    }

    return 0;
}

static float
get_radius_from_pressure(PyBrush *self, float pressure)
{
    float min = self->b_BasicValues[BV_RADIUS_MIN];
    float max = self->b_BasicValues[BV_RADIUS_MAX];
    float radius = min + (max-min)*pressure;
    return CLAMP(radius, 0.5, 200.0);
}

static float
get_opacity_from_pressure(PyBrush *self, float pressure)
{
    float min = self->b_BasicValues[BV_OPACITY_MIN];
    float max = self->b_BasicValues[BV_OPACITY_MAX];
    float opa = min + (max-min)*pressure;
    return CLAMP(opa, 0.0, 1.0);
}

/* _draw_stroke:
 * Low level drawing routine that compute dab positions to draw
 * between two points.
 * The algorythm is first based on a constant number of points (dab density)
 * to produce, then from that we modulate this density depending on values
 * of extra brush parameters.
 *
 * As this routine handles curve smoothing drawing the drawing path
 * is interpolated using not 2 points but 4:
 * pt[1], pt[2] give current segment to draw.
 * pt[0], pt[1] give previous drawed segment.
 * pt[2], pt[3] give next segment to draw.
 *
 * We can see that this method need to buffer enough points
 * before drawing anything (4 points).
 */

static void
_draw_stroke(PyBrush *self, Point *pt[4], MyRec *area)
{
    float hardness, spacing, yratio;
    float color[MAX_CHANNELS];

    yratio = self->b_BasicValues[BV_YRATIO];
    hardness = self->b_BasicValues[BV_HARDNESS];
    spacing = self->b_BasicValues[BV_SPACING];

    /* TODO: CYMK colorspace handling */
    color[0] = self->b_Color[0];
    color[1] = self->b_Color[1];
    color[2] = self->b_Color[2];
    color[3] = 1.0;

	/* Euclidian length of drawn segment.
	 * This is used to compute number of dab's to drawn in respect of density.
	 * It's not accurate as dab's will not follow a straight line due to
	 * smoothing curve compensation. But it's near enough and keep code fast.
	 */
    float dx = pt[2]->p_SX - pt[1]->p_SX;
    float dy = pt[2]->p_SY - pt[1]->p_SY;
    float dist = hypotf(dx, dy);

    float radius = pt[2]->p_Radius;
    float rad_per_sp = radius * spacing;

    //printf("start: p=%g, r=%g\n", p, r);
    //printf("end:   p=%g, r=%g\n", pressure, radius);

    float fac = self->b_BasicValues[BV_OPACITY_COMPENSATION] / spacing;
    float opa0 = powf(pt[1]->p_Opacity, fac);
    float opa1 = powf(pt[2]->p_Opacity, fac);

    float xtilt = (pt[1]->p_XTilt + pt[2]->p_XTilt) * .5;
    float ytilt = (pt[1]->p_YTilt + pt[2]->p_YTilt) * .5;

    /* Discretized direction brush angle [0, 1023] */
    float angle;
    if (ytilt != 0.0)
		angle = atanf(xtilt/ytilt) + self->b_BasicValues[BV_ANGLE]*M_TWOPI/360.;
    else
		angle = 0.0;
    int dir_angle = angle * 1024./M_TWOPI;
    if (dir_angle == 1024)
		dir_angle = 0;

    /* Brush direction (cos/sin) */
    self->b_cs = cosf(angle);
    self->b_sn = sinf(angle);

    float m0x = (pt[2]->p_SX - pt[0]->p_SX) / 2;
    float m0y = (pt[2]->p_SY - pt[0]->p_SY) / 2;
    float m1x = (pt[3]->p_SX - pt[1]->p_SX) / 2;
    float m1y = (pt[3]->p_SY - pt[1]->p_SY) / 2;

    //printf("m0: (%g, %g)\n", m0x, m0y);
    //printf("m1: (%g, %g)\n", m1x, m1y);

    float dabs_frac = self->b_RemainSteps;
    float dabs_todo  = dist / rad_per_sp;
    //dabs_todo += dist / (radius * spacing);

	float t=0;
	float p=pt[1]->p_Pressure;
	float r=pt[1]->p_Radius;
	float opa=opa0;
	float x=pt[1]->p_SX;
	float y=pt[1]->p_SY;

    while ((dabs_frac + dabs_todo) >= 1.0)
    {
		float h00, h10, h01, h11;
		float alpha=1;
        float frac, t2, t3;

        if (dabs_frac > 0.0)
        {
            frac = (1 - dabs_frac) / dabs_todo;
            dabs_frac = 0.0;
        }
        else
            frac = 1.0 / dabs_todo;

		t += frac * (1 - t);
		t2 =  t * t;
		t3 = t2 * t;

		/* Computing Hermite Spline coefficients (Catmull-Rom case) */
		h00 =  2*t3 - 3*t2 + 1;
		h10 =    t3 - 2*t2 + t;
		h01 = -2*t3 + 3*t2;
		h11 =    t3 -   t2;

		/* Compute per dab position using cubic Hermite interpolation */
		x = h00 * pt[1]->p_SX + h10 * m0x + h01 * pt[2]->p_SX + h11 * m1x;
		y = h00 * pt[1]->p_SY + h10 * m0y + h01 * pt[2]->p_SY + h11 * m1y;

		//x += frac * (pt[2]->p_SX - x);
        //y += frac * (pt[2]->p_SY - y);

		/* Compute per dab others states using linear interpolation */
		p += frac * (pt[2]->p_Pressure - p);
		if (CLAMP(p, 0.0, 1.0) != p)
			printf("***> Pressure clamp warn: %g\n", p);
		r += frac * (radius - r);
		opa += frac * (opa1 - opa);

		/* Final dab values (with possible jittering) */
		float jitter, dab_x=x, dab_y=y, dab_r=r;

		/* Per-dab radius jitter */
		jitter = self->b_BasicValues[BV_DAB_RADIUS_JITTER];
		if (jitter > 0.0)
			dab_r *= 1. - myrand2()*jitter;

		/* Per-dab position jitter (from dab radius) */
		jitter = self->b_BasicValues[BV_DAB_POS_JITTER];
		if (jitter > 0.0)
		{
			jitter *= dab_r;
			dab_x += (myrand1()*2-1)*jitter;
			dab_y += (myrand2()*2-1)*jitter;
		}

		/* Direction jitter */
		jitter = self->b_BasicValues[BV_DIRECTION_JITTER];
		if (jitter > 0.0)
		{
			int da;

			/* Dabs are round by nature, so random factor is limited to +-90° */
			da = dir_angle + ((int)(myrand1()*jitter*512)-256);

			/* Cos/Sin tables are oversized to remove a modulo usage.
			 * So only negative values protection remains.
			 */
			if (da < 0)
				da += CS_TABLE_SIZE-1;

			self->b_cs = fixed_cos[da];
			self->b_sn = fixed_sin[da];
		}

		/* smudge step */
		if (process_smudge(self, dab_x, dab_y,
						   dab_r, yratio, self->b_cs, self->b_sn,
						   hardness, color, &alpha))
		{
			return;
		}

		/* Color HSV shift */
		float hsv[3];

        rgb_to_hsv(color, hsv);
        hsv[0] += self->b_BasicValues[BV_COLOR_SHIFT_H];
        hsv[1] += self->b_BasicValues[BV_COLOR_SHIFT_S];
        hsv[2] += self->b_BasicValues[BV_COLOR_SHIFT_V];
        hsv_to_rgb(hsv, color);

        /* Save for the next segment */
        self->b_Color[0] = color[0];
        self->b_Color[1] = color[1];
        self->b_Color[2] = color[2];

		/* Do erase? */
		if (self->b_BasicValues[BV_ERASE] < 1.0)
			alpha *= self->b_BasicValues[BV_ERASE];

#ifdef STAT_TIMING
		uint64_t ts1, ts2;
		READ_TIMESTAMP(ts1);
#endif
		if (drawdab_solid(self, area, self->b_Surface,
						  dab_x, dab_y,
						  dab_r, yratio, hardness,
						  alpha, opa,
						  self->b_cs, self->b_sn, color))
		{
			return;
		}

#ifdef STAT_TIMING
		READ_TIMESTAMP(ts2);
		self->b_Times[0] += ts2 - ts1;
		self->b_TimesCount[0]++;
#endif

        dx = pt[2]->p_SX-x;
        dy = pt[2]->p_SY-y;
        float d = hypot(dx, dy) / rad_per_sp;

        if (fabs(d-dabs_todo) < 1e-4) break;
        dabs_todo = d;
    }

    self->b_RemainSteps = dabs_frac + dabs_todo;
}

/*******************************************************************************************
** PyBrush_Type
*/


static PyObject *
brush_new(PyTypeObject *type, PyObject *args)
{
    PyBrush *self;

    self = (PyBrush *)type->tp_alloc(type, 0); /* NR */
    if (NULL != self)
    {
        PBNode *node, *prev=NULL;
        int i;

        /* Init pixbuf cache nodes */
        for (i=0; i < PB_CACHE_SIZE; i++)
        {
            node = &self->b_PBCache[i];
            node->pbn_Previous = prev;
            if (NULL != prev)
                prev->pbn_Next = node;
            prev = node;
        }
        node->pbn_Next = NULL;

        self->b_PBFirst = self->b_FirstInvalid = &self->b_PBCache[0];
        self->b_PBLast = node;

        self->b_BasicValues[BV_RADIUS_MIN] = 2.0;
        self->b_BasicValues[BV_RADIUS_MAX] = 2.0;
        self->b_BasicValues[BV_YRATIO] = 1.0;
        self->b_BasicValues[BV_HARDNESS] = 0.5;
        self->b_BasicValues[BV_OPACITY_MIN] = 1.0;
        self->b_BasicValues[BV_OPACITY_MAX] = 1.0;
        self->b_BasicValues[BV_ERASE] = 1.0;
        self->b_BasicValues[BV_OPACITY_COMPENSATION] = 1.0;
        self->b_BasicValues[BV_SPACING] = 0.25;
        self->b_BasicValues[BV_MOTION_TRACK] = 0.3;
        self->b_BasicValues[BV_HI_SPEED_TRACK] = 0.0;

        /* let remaining fields to 0 */
    }

    return (PyObject *)self;
}

static int
brush_traverse(PyBrush *self, visitproc visit, void *arg)
{
    Py_VISIT(self->b_GetPixBufFunc);
    Py_VISIT(self->b_Surface);
    return 0;
}

static int
brush_clear(PyBrush *self)
{
    Py_CLEAR(self->b_GetPixBufFunc);
    Py_CLEAR(self->b_Surface);
    return 0;
}

static void
brush_dealloc(PyBrush *self)
{
    brush_clear(self);
    self->ob_type->tp_free((PyObject *)self);
}

static PyObject *
brush_drawdab_solid(PyBrush *self, PyObject *args)
{
    int sx, sy; /* Center position (surface units) */
    float pressure; /* Pressure, range =  [0.0, 0.1] */
    float radius; /* Radius, range =  [0.0, 0.1] */
    float yratio; /* YRatio, range =  [0.0, inf] */
    float hardness; /* Hardness, range =  [0.0, inf] */
    MyRec area;

    if (NULL == self->b_Surface)
        return PyErr_Format(PyExc_RuntimeError, "No surface set.");

    /* Set defaults for optional arguments */
    radius = self->b_BasicValues[BV_RADIUS_MAX];
    yratio = self->b_BasicValues[BV_YRATIO];
    hardness = self->b_BasicValues[BV_HARDNESS];
    pressure = 0.5;

    if (!PyArg_ParseTuple(args, "(kk)|ffff", &sx, &sy,  &pressure, &radius, &yratio, &hardness))
        return NULL;

    CLAMP(pressure, 0.0, 1.0);
    CLAMP(radius, 0.0, 1.0);
    CLAMP(hardness, 0.001, 1.0);

    DPRINT("R=%.3f, P=%.3f, H=%.3f, Y=%.3f\n", radius, pressure, hardness, yratio);

    /* Check if have something to draw or just return the empty damaged list */
    if ((hardness <= .0) || (yratio <= .0) || (.0 == pressure) || (.0 == radius))
        Py_RETURN_NONE;

    area.x1 = area.y1 = INT32_MAX;
    area.x2 = area.y2 = INT32_MIN;

    if (drawdab_solid(self, &area, self->b_Surface,
                      sx, sy, radius, yratio,
                      hardness, self->b_BasicValues[BV_ERASE],
                      self->b_BasicValues[BV_OPACITY_MAX], 0.707106, 0.707106, self->b_RGBColor))
        Py_RETURN_NONE;

    return Py_BuildValue("iiii", area.x1, area.y1, area.x2, area.y2);
}

static PyObject *
brush_drawstroke(PyBrush *self, PyObject *args)
{
    Point *pt[4];
    PyObject *state;
	int i, j, ix, iy;
	float sx, sy, radius, dist, pressure, dx, dy, tiltx, tilty;
	double time;

    if (NULL == self->b_Surface)
        return PyErr_Format(PyExc_RuntimeError, "Uninitialized brush");

	if (!PyArg_ParseTuple(args, "O", &state))
		return NULL;

	/* Compute a points array with following indexes:
	 * 0 : last starting point
	 * 1 : starting point
	 * 2 : ending point
	 * 3 : current device point
	 */

	if (self->b_NeededPoints > 0)
		j = 5 - self->b_NeededPoints;
	else
		j = self->b_PointIndex;

	for (i=0; i < 4; i++)
		pt[i] = &self->b_Points[(i + j) % 4];

	/* Don't insert new point if no movement */
	GET_2T_FLOAT_FROM_STROKE(state, sx, sy, "spos");
	dx = sx - pt[2]->p_SX;
	dy = sy - pt[2]->p_SY;
	dist = hypotf(dx, dy);

	if (dist == 0.)
		Py_RETURN_NONE;

	GET_2T_INT_FROM_STROKE(state, ix, iy, "vpos");
	GET_FLOAT_FROM_STROKE(state, time, "time");
	GET_FLOAT_FROM_STROKE(state, tiltx, "xtilt");
	GET_FLOAT_FROM_STROKE(state, tilty, "ytilt");

	/* computing dynamic brush parameters */
	GET_FLOAT_FROM_STROKE(state, pressure, "pressure");
	pressure = CLAMP(pressure, 0.0, 1.0);
	radius = get_radius_from_pressure(self, pressure);

	if (0.0 == radius)
		Py_RETURN_NONE;

	double dtime = time - pt[2]->p_Time;

	/* Point states are computed and ok, record it */
	pt[3]->p_IX = ix;
	pt[3]->p_IY = iy;
	pt[3]->p_SXo = sx;
	pt[3]->p_SYo = sy;
	pt[3]->p_XTilt = tiltx;
	pt[3]->p_YTilt = tilty;
	pt[3]->p_Time = time;
	pt[3]->p_Pressure = pressure;
	pt[3]->p_Radius = radius;
	pt[3]->p_Opacity = get_opacity_from_pressure(self, pressure);

	/* Motion tracking filter */
	{
		float speed = hypot(ix - pt[2]->p_IX, iy - pt[2]->p_IY) / dtime;
		float lofac, fac = decay(1e3/speed, self->b_BasicValues[BV_HI_SPEED_TRACK]);

		sx -= dx*fac;
		sy -= dy*fac;
		lofac = decay(self->b_BasicValues[BV_MOTION_TRACK], 1.0);
		sx = sx*lofac + pt[2]->p_SX*(1.0-lofac);
		sy = sy*lofac + pt[2]->p_SY*(1.0-lofac);
	}

	pt[3]->p_SX = sx;
	pt[3]->p_SY = sy;

	/* Not enough points to start drawing? */
	if (self->b_NeededPoints > 0)
	{
		self->b_NeededPoints--;
		Py_RETURN_NONE;
	}

	self->b_PointIndex = (self->b_PointIndex + 1) % 4;

    /* Drawing dabs between pt[1] and pt[2] */
    MyRec area;

    area.x1 = area.y1 = INT32_MAX;
    area.x2 = area.y2 = INT32_MIN;

	_draw_stroke(self, pt, &area);

    /* something drawn? */
    //printf("%d %d %d %d\n", area.x1, area.y1, area.x2, area.y2);
    if (area.x1 != INT32_MAX)
        return Py_BuildValue("iiII", area.x1, area.y1, area.x2-area.x1+1, area.y2-area.y1+1);

    Py_RETURN_NONE;
}

static PyObject *
brush_invalid_cache(PyBrush *self)
{
    unsigned int i;

#ifdef STAT_TIMING
    printf("Cache states: cache accesses = %u, cache miss = %u (%u%%)\n",
            self->b_CacheAccesses, self->b_CacheMiss,
            (unsigned int)(((float)self->b_CacheMiss * 100 / self->b_CacheAccesses) + 0.5));

#ifdef __MORPHOS__
    unsigned int tbclockfreq=0;
    if (!NewGetSystemAttrs(&tbclockfreq,sizeof(tbclockfreq),SYSTEMINFOTYPE_TBCLOCKFREQUENCY,TAG_DONE))
        tbclockfreq = 33333333;
#endif

    for (i=0; i < sizeof(self->b_Times)/sizeof(*self->b_Times); i++)
    {
        float t = (float)self->b_Times[i] / self->b_TimesCount[i];

        printf("Time#%u: %f\n", i, t);
        self->b_Times[i] = 0;
        self->b_TimesCount[i] = 0;
    }

    self->b_CacheAccesses = 0;
    self->b_CacheMiss = 0;
#endif

    /* invalidate the whole cache */
    for (i=0; i < PB_CACHE_SIZE; i++)
        self->b_PBCache[i].pbn_Valid = FALSE;
    self->b_FirstInvalid = &self->b_PBCache[0];

    Py_RETURN_NONE;
}

static PyObject *
brush_stroke_start(PyBrush *self, PyObject *args)
{
    PyObject *state, *res;
    float alpha;
    Point *pt;

    if (!PyArg_ParseTuple(args, "O", &state))
        return NULL;

    self->b_RemainSteps = 0.0;
    self->b_PointIndex = 0;
    self->b_NeededPoints = 2;

    /* Read first point states (p0) */
    pt = &self->b_Points[0];

    GET_2T_INT_FROM_STROKE(state, pt->p_IX, pt->p_IY, "vpos");
    GET_2T_FLOAT_FROM_STROKE(state, pt->p_SX, pt->p_SY, "spos");
    GET_FLOAT_FROM_STROKE(state, pt->p_Pressure, "pressure");
    GET_FLOAT_FROM_STROKE(state, pt->p_Time, "time");
    GET_FLOAT_FROM_STROKE(state, pt->p_XTilt, "xtilt");
    GET_FLOAT_FROM_STROKE(state, pt->p_YTilt, "ytilt");

    pt->p_Pressure = CLAMP(pt->p_Pressure, 0.0, 1.0);
    pt->p_Radius = get_radius_from_pressure(self, pt->p_Pressure);
    pt->p_Opacity = get_opacity_from_pressure(self, pt->p_Pressure);

    /* Duplicate for Hermite spline initial conditions (need a tangent at first point) */
    memcpy(&pt[1], &pt[0], sizeof(Point));

    res = brush_invalid_cache(self); /* NR */
    if (NULL == res)
        return NULL;

    Py_DECREF(res);

    /* TODO: CYMK handling */
    bzero(self->b_SmudgeColor, sizeof(self->b_SmudgeColor));
    memcpy(self->b_Color, self->b_RGBColor, sizeof(self->b_Color));

    #if 1
    /* Brush direction (cos/sin) */
    float xtilt = pt->p_XTilt;
    float ytilt = pt->p_YTilt;

    /* Discretized direction brush angle [0, 1023] */
    float angle = atanf(xtilt/ytilt) + self->b_BasicValues[BV_ANGLE]*M_TWOPI/360.;

    /* setup starting smudge value */
    if (process_smudge(self, pt->p_SX, pt->p_SY, pt->p_Radius,
                       self->b_BasicValues[BV_YRATIO],
                       cosf(angle), sinf(angle),
                       self->b_BasicValues[BV_HARDNESS],
                       self->b_Color, &alpha))
    {
        return NULL;
    }
    #endif

    Py_RETURN_NONE;
}

static PyObject *
brush_stroke_end(PyBrush *self, PyObject *args)
{
	Point *pt[4];

	if (!self->b_NeededPoints)
	{
		MyRec area;
		int i;

		area.x1 = area.y1 = INT32_MAX;
		area.x2 = area.y2 = INT32_MIN;

		/* re-insert last point and draw dabs as usual, do it twice */
		for (i=0; i < 4; i++)
			pt[i] = &self->b_Points[(i + self->b_PointIndex) % 4];
		memcpy(pt[3], pt[2], sizeof(Point));
		pt[3]->p_SX = pt[3]->p_SXo;
		pt[3]->p_SY = pt[3]->p_SYo;
		_draw_stroke(self, pt, &area);

		for (i=0; i < 4; i++)
			pt[i] = &self->b_Points[(i + self->b_PointIndex + 1) % 4];
		memcpy(pt[3], pt[2], sizeof(Point));
		_draw_stroke(self, pt, &area);

		/* something drawn? */
		if (area.x1 != INT32_MAX)
			return Py_BuildValue("iiII", area.x1, area.y1, area.x2-area.x1+1, area.y2-area.y1+1);
	}

    Py_RETURN_NONE;
}

static PyObject *
brush_get_pixel(PyBrush *self, PyObject *args)
{
    float x, y, color[MAX_CHANNELS];
    int err;
    PyObject *res;

    if (!PyArg_ParseTuple(args, "ff", &x, &y))
        return NULL;

    res = brush_invalid_cache(self); /* NR */
    if (NULL == res)
        return NULL;

    Py_DECREF(res);

    /* use full surface under basic radius (i.e. displayed cursor area) */
    err = get_dab_color(self, self->b_Surface,
                        x, y,
                        self->b_BasicValues[BV_RADIUS_MAX],
                        1.0, 1.0, 1.0, 0.0, color);
    if (err != 0)
        Py_RETURN_NONE;

    /* Alpha-premul */
    color[0] *= color[3];
    color[1] *= color[3];
    color[2] *= color[3];

    return Py_BuildValue("fff", color[0], color[1], color[2]);
}

static PyObject *
brush_get_states(PyBrush *self)
{
    return PyBuffer_FromReadWriteMemory((void *)self->b_BasicValues, sizeof(self->b_BasicValues));
}

static PyObject *
brush_get_state(PyBrush *self, PyObject *args)
{
    unsigned int index;

    if (!PyArg_ParseTuple(args, "I", &index))
        return NULL;

    if (index >= BASIC_VALUES_MAX)
        return PyErr_Format(PyExc_IndexError, "index shall be lower than %u", BASIC_VALUES_MAX);

    return PyFloat_FromDouble((double)self->b_BasicValues[index]);
}

static PyObject *
brush_set_state(PyBrush *self, PyObject *args)
{
    unsigned int index;
    float value;

    if (!PyArg_ParseTuple(args, "If", &index, &value))
        return NULL;

    if (index >= BASIC_VALUES_MAX)
        return PyErr_Format(PyExc_IndexError, "index shall be lower than %u", BASIC_VALUES_MAX);

    /* Clamping */
    switch (index)
    {
        case BV_YRATIO: value = CLAMP(value, 1.0, 100.0); break;
        case BV_HARDNESS: value = CLAMP(value, 0.01, 1.0); break;
        case BV_SPACING: value = MAX(value, 0.01); break;
    }

    self->b_BasicValues[index] = value;

    Py_RETURN_NONE;
}

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

static int
brush_set_surface(PyBrush *self, PyObject *value, void *closure)
{
    if (value == self->b_Surface)
        return 0;

    if (NULL != self->b_Surface)
    {
        my_Py_DECREF(self->b_GetPixBufFunc);
        my_Py_DECREF(self->b_Surface);
    }

    if (NULL == value)
        return 0;

    Py_INCREF(value);
    self->b_Surface = value;

    /* Cache get_pixbuf method */
    self->b_GetPixBufFunc = PyObject_GetAttrString(value, "get_pixbuf"); /* NR */
	if (NULL == self->b_GetPixBufFunc)
    {
		PyErr_SetString(PyExc_AttributeError, "Surface doesn't provide get_pixbuf method");
		return 1;
	}

    return 0;
}

static PyObject *
brush_get_float(PyBrush *self, int index)
{
    float *ptr = &self->b_BasicValues[index];

    return PyFloat_FromDouble((double)*ptr);
}

static int
brush_set_float(PyBrush *self, PyObject *value, int index)
{
    float *ptr = &self->b_BasicValues[index];
    double v;

    if (NULL == value)
    {
        *ptr = 0;
        return 0;
    }

    v = PyFloat_AsDouble(value);
    if (PyErr_Occurred())
        return 1;

    /* Clamping */
    switch (index)
    {
        case BV_YRATIO: v = CLAMP(v, 1.0, 100.0); break;
        case BV_HARDNESS: v = CLAMP(v, 0.01, 1.0); break;
        case BV_SPACING: v = MAX(v, 0.01); break;
    }

    *ptr = v;
    return 0;
}

static int
brush_set_normalized_float(PyBrush *self, PyObject *value, int index)
{
    float *ptr = &self->b_BasicValues[index];
    double v;

    if (NULL == value)
    {
        *ptr = 0;
        return 0;
    }

    v = PyFloat_AsDouble(value);
    if (PyErr_Occurred())
        return 1;

    *ptr = CLAMP(v, 0.0, 1.0);
    return 0;
}

static PyObject *
brush_get_hsvcolor(PyBrush *self, void *closure)
{
    float ptr = self->b_HSVColor[(int)closure];
    return PyFloat_FromDouble(ptr);
}

static PyObject *
brush_get_rgbcolor(PyBrush *self, void *closure)
{
    float ptr = self->b_RGBColor[(int)closure];
    return PyFloat_FromDouble(ptr);
}

static int
brush_set_hsvcolor(PyBrush *self, PyObject *value, void *closure)
{
    float *ptr = &self->b_HSVColor[(int)closure];
    double v;

    if (NULL == value)
    {
        *ptr = 0.0;
        return 0;
    }

    v = PyFloat_AsDouble(value);
    if (PyErr_Occurred())
        return 1;

    *ptr = CLAMP(v, 0.0, 1.0);
    hsv_to_rgb(self->b_HSVColor, self->b_RGBColor);
    return 0;
}

static int
brush_set_rgbcolor(PyBrush *self, PyObject *value, void *closure)
{
    float *ptr = &self->b_RGBColor[(int)closure];
    double v;

    if (NULL == value)
    {
        *ptr = 0.0;
        return 0;
    }

    v = PyFloat_AsDouble(value);
    if (PyErr_Occurred())
        return 1;

    *ptr = CLAMP(v, 0.0, 1.0);
    rgb_to_hsv(self->b_RGBColor, self->b_HSVColor);
    return 0;
}

static PyObject *
brush_get_hsv(PyBrush *self, void *closure)
{
    return Py_BuildValue("fff", self->b_HSVColor[0], self->b_HSVColor[1], self->b_HSVColor[2]);
}

static int
brush_set_hsv(PyBrush *self, PyObject *value, void *closure)
{
    if (NULL == value)
    {
        bzero(self->b_HSVColor, sizeof(self->b_HSVColor));
        return 0;
    }

    if (!PyArg_ParseTuple(value, "fff", &self->b_HSVColor[0], &self->b_HSVColor[1], &self->b_HSVColor[2]))
        return 1;

    self->b_HSVColor[0] = CLAMP(self->b_HSVColor[0], 0.0, 1.0);
    self->b_HSVColor[1] = CLAMP(self->b_HSVColor[1], 0.0, 1.0);
    self->b_HSVColor[2] = CLAMP(self->b_HSVColor[2], 0.0, 1.0);
    hsv_to_rgb(self->b_HSVColor, self->b_RGBColor);
    return 0;
}

static PyObject *
brush_get_rgb(PyBrush *self, void *closure)
{
    return Py_BuildValue("fff", self->b_RGBColor[0], self->b_RGBColor[1], self->b_RGBColor[2]);
}

static int
brush_set_rgb(PyBrush *self, PyObject *value, void *closure)
{
    if (NULL == value)
    {
        bzero(self->b_RGBColor, sizeof(self->b_RGBColor));
        return 0;
    }

    if (!PyArg_ParseTuple(value, "fff", &self->b_RGBColor[0], &self->b_RGBColor[1], &self->b_RGBColor[2]))
        return 1;

    self->b_RGBColor[0] = CLAMP(self->b_RGBColor[0], 0.0, 1.0);
    self->b_RGBColor[1] = CLAMP(self->b_RGBColor[1], 0.0, 1.0);
    self->b_RGBColor[2] = CLAMP(self->b_RGBColor[2], 0.0, 1.0);
    rgb_to_hsv(self->b_RGBColor, self->b_HSVColor);
    return 0;
}

static PyGetSetDef brush_getsetters[] = {
    {"surface",         (getter)brush_get_surface, (setter)brush_set_surface,          "Surface to use", NULL},

    {"radius_min",      (getter)brush_get_float,   (setter)brush_set_float,            "Radius min",              (void *)BV_RADIUS_MIN},
    {"radius_max",      (getter)brush_get_float,   (setter)brush_set_float,            "Radius max",              (void *)BV_RADIUS_MAX},
    {"yratio",          (getter)brush_get_float,   (setter)brush_set_float,            "Y-ratio",                 (void *)BV_YRATIO},
    {"angle",           (getter)brush_get_float,   (setter)brush_set_float,            "Dab angle",               (void *)BV_ANGLE},
    {"hardness",        (getter)brush_get_float,   (setter)brush_set_normalized_float, "Hardness",                (void *)BV_HARDNESS},
    {"opacity_min",     (getter)brush_get_float,   (setter)brush_set_normalized_float, "Opacity min",             (void *)BV_OPACITY_MIN},
    {"opacity_max",     (getter)brush_get_float,   (setter)brush_set_normalized_float, "Opacity max",             (void *)BV_OPACITY_MAX},
    {"opa_comp",        (getter)brush_get_float,   (setter)brush_set_float,            "Opacity compensation",    (void *)BV_OPACITY_COMPENSATION},
    {"erase",           (getter)brush_get_float,   (setter)brush_set_normalized_float, "Erase",                   (void *)BV_ERASE},
    {"dab_radius_jitter",(getter)brush_get_float,   (setter)brush_set_normalized_float,"Per dab radius jitter",   (void *)BV_DAB_RADIUS_JITTER},
    {"dab_pos_jitter",  (getter)brush_get_float,   (setter)brush_set_float,            "Per dab position jitter", (void *)BV_DAB_POS_JITTER},
    {"direction_jitter",(getter)brush_get_float,   (setter)brush_set_normalized_float, "Direction jitter",        (void *)BV_DIRECTION_JITTER},
    {"spacing",         (getter)brush_get_float,   (setter)brush_set_float,            "Spacing",                 (void *)BV_SPACING},
    {"grain",           (getter)brush_get_float,   (setter)brush_set_normalized_float, "Grain factor",            (void *)BV_GRAIN_FAC},
    {"motion_track",    (getter)brush_get_float,   (setter)brush_set_float,            "Motion tracking factor",  (void *)BV_MOTION_TRACK},
    {"hi_speed_track",  (getter)brush_get_float,   (setter)brush_set_float,            "Hi speed tracking factor",(void *)BV_HI_SPEED_TRACK},
    {"smudge",          (getter)brush_get_float,   (setter)brush_set_normalized_float, "Smudge factor",           (void *)BV_SMUDGE},
    {"smudge_var",      (getter)brush_get_float,   (setter)brush_set_normalized_float, "Smudge variation factor", (void *)BV_SMUDGE_VAR},
    {"color_shift_h",   (getter)brush_get_float,   (setter)brush_set_float,            "Color H shifting",        (void *)BV_COLOR_SHIFT_H},
    {"color_shift_s",   (getter)brush_get_float,   (setter)brush_set_float,            "Color S shifting",        (void *)BV_COLOR_SHIFT_S},
    {"color_shift_v",   (getter)brush_get_float,   (setter)brush_set_float,            "Color V shifting",        (void *)BV_COLOR_SHIFT_V},
    {"alpha_lock",      (getter)brush_get_float,   (setter)brush_set_normalized_float, "Alpha Lock",              (void *)BV_ALPHA_LOCK},

    {"hsv",             (getter)brush_get_hsv,      (setter)brush_set_hsv,              "HSV Color",                    NULL},
    {"rgb",             (getter)brush_get_rgb,      (setter)brush_set_rgb,              "RGB Color",                    NULL},

    {"hue",             (getter)brush_get_hsvcolor, (setter)brush_set_hsvcolor,         "Color (Hue channel)",          (void *)0},
    {"saturation",      (getter)brush_get_hsvcolor, (setter)brush_set_hsvcolor,         "Color (Saturation channel)",   (void *)1},
    {"value",           (getter)brush_get_hsvcolor, (setter)brush_set_hsvcolor,         "Color (Value channel)",        (void *)2},

    {"red",             (getter)brush_get_hsvcolor, (setter)brush_set_rgbcolor,         "Color (Red channel)",          (void *)0},
    {"green",           (getter)brush_get_hsvcolor, (setter)brush_set_rgbcolor,         "Color (Green channel)",        (void *)1},
    {"blue",            (getter)brush_get_hsvcolor, (setter)brush_set_rgbcolor,         "Color (Blue channel)",         (void *)2},

    /*
    {"cyan",            (getter)brush_get_color,   (setter)brush_set_color,            "Color (Cyan channel)",    (void *)offsetof(PyBrush, b_CMYKColor[0])},
    {"magenta",         (getter)brush_get_color,   (setter)brush_set_color,            "Color (Magenta channel)", (void *)offsetof(PyBrush, b_CMYKColor[1])},
    {"yellow",          (getter)brush_get_color,   (setter)brush_set_color,            "Color (Yellow channel)",  (void *)offsetof(PyBrush, b_CMYKColor[2])},
    {"key",             (getter)brush_get_color,   (setter)brush_set_color,            "Color (Key channel)",     (void *)offsetof(PyBrush, b_CMYKColor[3])},
    */

    {NULL} /* sentinel */
};

static struct PyMethodDef brush_methods[] = {
    /*{"drawdab_solid", (PyCFunction)brush_drawdab_solid, METH_VARARGS, NULL},*/
    {"draw_stroke",   (PyCFunction)brush_drawstroke,    METH_VARARGS, NULL},
    {"invalid_cache", (PyCFunction)brush_invalid_cache, METH_NOARGS,  NULL},
    {"stroke_start", (PyCFunction)brush_stroke_start, METH_VARARGS, NULL},
    {"stroke_end", (PyCFunction)brush_stroke_end, METH_VARARGS, NULL},
    {"get_pixel", (PyCFunction)brush_get_pixel, METH_VARARGS, NULL},
    {NULL} /* sentinel */
};

static PyTypeObject PyBrush_Type = {
    PyObject_HEAD_INIT(NULL)

    tp_name         : "_brush.Brush",
    tp_basicsize    : sizeof(PyBrush),
    tp_flags        : Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE | Py_TPFLAGS_HAVE_GC,
    tp_doc          : "Brush Objects",

    tp_new          : (newfunc)brush_new,
    tp_traverse     : (traverseproc)brush_traverse,
    tp_clear        : (inquiry)brush_clear,
    tp_dealloc      : (destructor)brush_dealloc,
    tp_methods      : brush_methods,
    tp_getset       : brush_getsetters,
};

/*******************************************************************************************
** Module
*/

static PyMethodDef methods[] = {
    {NULL}
};

static int add_constants(PyObject *m)
{
    INSI(m, "BV_RADIUS_MIN", BV_RADIUS_MIN);
    INSI(m, "BV_RADIUS_MAX", BV_RADIUS_MAX);
    INSI(m, "BV_YRATIO", BV_YRATIO);
    INSI(m, "BV_ANGLE", BV_ANGLE);
    INSI(m, "BV_HARDNESS", BV_HARDNESS);
    INSI(m, "BV_OPACITY_MIN", BV_OPACITY_MIN);
    INSI(m, "BV_OPACITY_MAX", BV_OPACITY_MAX);
    INSI(m, "BV_OPACITY_COMPENSATION", BV_OPACITY_COMPENSATION);
    INSI(m, "BV_ERASE", BV_ERASE);
    INSI(m, "BV_DAB_RADIUS_JITTER", BV_DAB_RADIUS_JITTER);
    INSI(m, "BV_DAB_POS_JITTER", BV_DAB_POS_JITTER);
    INSI(m, "BV_DIRECTION_JITTER", BV_DIRECTION_JITTER);
    INSI(m, "BV_SPACING", BV_SPACING);
    INSI(m, "BV_GRAIN_FAC", BV_GRAIN_FAC);
    INSI(m, "BV_SMUDGE", BV_SMUDGE);
    INSI(m, "BV_SMUDGE_VAR", BV_SMUDGE_VAR);
    INSI(m, "BV_COLOR_SHIFT_H", BV_COLOR_SHIFT_H);
    INSI(m, "BV_SCOLOR_SHIFT_S", BV_COLOR_SHIFT_S);
    INSI(m, "BV_COLOR_SHIFT_V", BV_COLOR_SHIFT_V);
    INSI(m, "BV_ALPHA_LOCK", BV_ALPHA_LOCK);
    INSI(m, "BASIC_VALUES_MAX", BASIC_VALUES_MAX);

    return 0;
}

static struct PyModuleDef module =
{
    PyModuleDef_HEAD_INIT,
    MODNAME,
    "",
    -1,
	methods
};

PyMODINIT_FUNC
INITFUNC(void)
{
    PyObject *m;
    int i;

    /* pre-compute cos/sin tables */
    for (i=0; i<CS_TABLE_SIZE; i++)
    {
        float a = i * M_TWOPI/1024.0;

        fixed_cos[i] = cosf(a);
        fixed_sin[i] = sinf(a);
    }

    if (PyType_Ready(&PyBrush_Type) < 0) return NULL;

    m = PyModule_Create(&module);
    if (NULL == m) return NULL;

    if (add_constants(m)) return NULL;

    ADD_TYPE(m, "Brush", &PyBrush_Type);

    if (!import_pixbuf())
        return NULL;

	return m;
}
