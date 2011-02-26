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

//#define STAT_TIMING 1

#include "common.h"
#include "_pixbufmodule.h"
#include "math.h"

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

//#define DPRINT printf

#define PyBrush_Check(op) PyObject_TypeCheck(op, &PyBrush_Type)
#define PyBrush_CheckExact(op) ((op)->ob_type == &PyBrush_Type)

#define PB_CACHE_SIZE 15 /* good value for the case of big brushes */
#define DABS_PER_SECONDS 0

//#define STAT_TIMING

#define GET_INT_FROM_STROKE(state, var, name) {                   \
    PyObject *_o = PyObject_GetAttrString(state, name); /* NR */ \
    if (NULL == _o) return NULL; \
    else if (!PyInt_CheckExact(_o)) \
    { Py_DECREF(_o); return PyErr_Format(PyExc_TypeError, "Invalid '%s' attribute in stroke", name); } \
    var = PyInt_AS_LONG(_o); Py_DECREF(_o); }

#define GET_FLOAT_FROM_STROKE(state, var, name) {                \
    PyObject *_o = PyObject_GetAttrString(state, name); /* NR */ \
    if (NULL == _o) return NULL; \
    else if (!PyFloat_CheckExact(_o)) \
    { Py_DECREF(_o); return PyErr_Format(PyExc_TypeError, "Invalid '%s' attribute in stroke", name); } \
    var = PyFloat_AS_DOUBLE(_o); Py_DECREF(_o); }
    
#define GET_2T_FLOAT_FROM_STROKE(state, var0, var1, name) {      \
    PyObject *_o = PyObject_GetAttrString(state, name); /* NR */ \
    if (NULL == _o) return NULL; \
    else if (!PyTuple_CheckExact(_o)) \
    { Py_DECREF(_o); return PyErr_Format(PyExc_TypeError, "Invalid '%s' attribute in stroke", name); } \
    var0 = PyFloat_AsDouble(PyTuple_GET_ITEM(_o, 0)); \
    var1 = PyFloat_AsDouble(PyTuple_GET_ITEM(_o, 1)); \
    Py_DECREF(_o); }
    
#define GET_2T_INT_FROM_STROKE(state, var0, var1, name) {        \
    PyObject *_o = PyObject_GetAttrString(state, name); /* NR */ \
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
    BV_HARDNESS,
    BV_OPACITY_MIN,
    BV_OPACITY_MAX,
    BV_OPACITY_COMPENSATION,
    BV_ERASE,
    BV_RADIUS_RANDOM,
    BV_SPACING,
    BV_GRAIN_FAC,
    BV_MOTION_TRACK,
    BV_HI_SPEED_TRACK,
    BV_SMUDGE,
    BV_SMUDGE_VAR,
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

typedef struct
{
    int32_t x1, y1;
    int32_t x2, y2;
} MyRec;

typedef struct PyBrush
{
    PyObject_HEAD

    /* Object Data */
    PyObject *      b_Surface;
    PBNode          b_PBCache[PB_CACHE_SIZE];
    PBNode *        b_PBFirst;
    PBNode *        b_PBLast;
    PBNode *        b_FirstInvalid;

    /* Brush Model */
    double          b_Time;
    float           b_Pressure;
    float           b_cs, b_sn;
    float           b_RemainSteps; /* remaining dabs between last drawn dabs and last control knot */
    float           b_Length;
    float           b_Radius;
    float           b_Opacity;

    int             b_OldIX, b_OldIY;
    float           b_OldSX, b_OldSY;

    float           b_BasicValues[BASIC_VALUES_MAX];

    float           b_HSVColor[3]; /* HSV colorspace */
    float           b_RGBColor[3]; /* RGB colorspace */
    float           b_SmudgeColor[4];

#ifdef STAT_TIMING
    unsigned int    b_CacheAccesses;
    unsigned int    b_CacheMiss;
    uint64_t        b_Times[3];
    unsigned int    b_TimesCount[3];
#endif

} PyBrush;

static PyTypeObject PyBrush_Type;


/*
********************************************************************************
** Private routines
*/

#ifdef STAT_TIMING

/* Code from Python sources (ceval.c) */
#if defined(__PPC__) /* <- Don't know if this is the correct symbol; this
                           section should work for GCC on any PowerPC
                           platform, irrespective of OS.
                           POWER?  Who knows :-) */

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
#endif /* STAT_TIMING */

//+ obtain_pixbuffer
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
        o = PyObject_CallMethod(surface, "get_pixbuf", "ii", x, y); /* NR */
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
//-
//+ drawdab_solid
/* Solid spherical filling engine */
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
#ifdef STAT_TIMING
    uint64_t t1, t2;
#endif

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

    grain = self->b_BasicValues[BV_GRAIN_FAC];

    cs /= radius;
    sn /= radius;

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
            float cx, cy;

            /* Try to obtain the surface pixels buffer for the point (x, y).
            ** Search in internal cache for it, then ask directly to the surface object.
            **/

#ifdef STAT_TIMING
            READ_TIMESTAMP(t1);
#endif

            pb = obtain_pixbuffer(self, surface, x, y);

#ifdef STAT_TIMING
            READ_TIMESTAMP(t2);
            self->b_Times[2] += t2 - t1;
            self->b_TimesCount[2]++;
#endif
            if (NULL == pb)
                return -1;
                
            if ((void *)-1 == pb)
            {
                x++;
                goto next_pixel;
            }

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
             * OPTIMIZE: modulo can be avoided if pa (x,y) are correctly set.
             */
            bx_left = x - pb->x;
            //bx_left %= pb->width; /* /!\ modulo of neg is neg... */
            bx_right = MIN(bx_left+(maxx-x), pb->width-1);
            by_top = y - pb->y;
            //by_top %= pb->height;
            by_bottom = MIN(by_top+(maxy-y), pb->height-1);

            /* Start at the right pixel */
            bpp = (pb->bpc * pb->nc) >> 3;
            buf = pb->data + by_top*pb->bpr;

            DPRINT("BDraw: area = (%ld, %ld, %ld, %ld) size=(%lu, %lu)\n",
                   bx_left, by_top, bx_right, by_bottom,
                   bx_right-bx_left, by_bottom-by_top);

            /* Filling one pixel buffer (inner loop) */
#ifdef STAT_TIMING
            READ_TIMESTAMP(t1);
#endif

            /* Ellipse center in buffer coordinates.
             * Shift by a demi-pixel to be pixel centered.
             */
            cx = sx - pb->x - .5;
            cy = sy - pb->y - .5;

            /* OPTIM: linear data to compute pixels distance from center
             * using a scanline processing.
             */
            float yy0 = (float)by_top - cy;
            float yycs = yy0*cs;
            float yysn = yy0*sn;
            
            float xx0 = (float)bx_left - cx;
            float rx0 = xx0*cs;
            float ry0 = -xx0*sn*yratio;
            float ryd = -sn*yratio;
            float rxd = cs;
            
            for (by=by_top; by <= by_bottom; by++, yycs += cs, yysn += sn, buf += pb->bpr)
            {                
                uint8_t *pixel = buf + bx_left*bpp;
                
                /* Rotation */
                float rx = yysn + rx0;
                float ry = yycs*yratio + ry0;
                
                for (bx=bx_left; bx <= bx_right; bx++, rx += rxd, ry += ryd, pixel += bpp)
                {
                    float rr, opa;

                    /* Compute the square of pixel radius: rr^2 = rx^2 + ry^2
                     * Divide by the square of the ellipse radius to have
                     * a number relative to this radius (done in cs,sn).
                     *
                     * OPTIM: as pixel are processed in scanline way,
                     * rx and ry can be computed in linear way (additions).
                     */
                    rr = rx*rx + ry*ry;

                    /* (x, y) in the Ellipse ? */
                    if (rr <= 1.)
                    {
                        /* opacity = opacity_base * f(r), where:
                         *   - f is a fall-off function
                         *   - r the radius (we using the square radius (rr) in fact)
                         *
                         * hardness is the first zero of f (f(hardness)=0.0).
                         * hardness can't be zero (or density = -infinity, clamped to zero)
                         */
                        opa = opacity;
                        if (hardness < 1.0)
                        {
                            if (rr < hardness)
                                opa *= rr + 1.-(rr/hardness);
                            else
                                opa *= hardness/(1.-hardness)*(1.-rr);
                        }
                        
                        if (grain > 0)
                        {
                            float g = noise_2d((pb->x + (int)bx)*grain, (pb->y + (int)by)*grain);
                            opa = CLAMP(opa * ((g+1)/2), 0.0, 1.0);
                        }

                        pb->writepixel(pixel, opa, alpha, native_color);
                        pb->damaged = TRUE;
                    }
                }
            }

#ifdef STAT_TIMING
            READ_TIMESTAMP(t2);
            self->b_Times[1] += t2 - t1;
            self->b_TimesCount[1]++;
#endif

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
//-
//+ get_dab_color
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

    /* Loop on all pixels inside a bbox centered on (sx, sy) */
    for (y=miny; y <= maxy;)
    {
        for (x=minx; x <= maxx;)
        {
            PyPixbuf *pb;
            uint8_t *buf;
            unsigned int bx_left, bx_right, by_top, by_bottom;
            unsigned int bx, by; /* x, y in buffer space */
            unsigned int cx, cy;
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
                goto next_pixel;
            }

            /* 'buf' pointer is supposed to be an ARGB15X pixels buffer.
             * This pointer is directly positionned on pixel (box, boy).
             * Buffer is buf_width pixels of width and buf_height pixels of height.
             * buf_bpr gives the number of bytes to add to pass directly
             * to the pixel just below the current position.
             */

            /* Computing bbox inside the given buffer (surface units)
             * OPTIMIZE: modulo can be avoided if pa (x,y) are correctly set.
             */
            bx_left = x - pb->x;
            bx_left %= pb->width; /* /!\ modulo of neg is neg... */
            bx_right = MIN(bx_left+(maxx-x), pb->width-1);
            by_top = y - pb->y;
            by_top %= pb->height;
            by_bottom = MIN(by_top+(maxy-y), pb->height-1);

            /* Start at the right pixel */
            bpp = (pb->bpc * pb->nc) >> 3;
            buf = pb->data + by_top*pb->bpr;

            /* Ellipse center in buffer coordinates */
            cx = sx - pb->x - .5;
            cy = sy - pb->y - .5;

            float yy0 = (float)by_top - cy;
            float yycs = yy0*cs;
            float yysn = yy0*sn;
            
            float xx0 = (float)bx_left - cx;
            float rx0 = xx0*cs;
            float ry0 = -xx0*sn*yratio;
            float ryd = -sn*yratio;
            
            for (by=by_top; by <= by_bottom; by++, yycs += cs, yysn += sn, buf += pb->bpr)
            {                
                uint8_t *pixel = buf + bx_left*bpp;
                
                float rx = yysn + rx0;
                float ry = yycs*yratio + ry0;
                
                for (bx=bx_left; bx <= bx_right; bx++, rx += cs, ry += ryd, pixel += bpp)
                {
                    float rr, opa;
                    uint16_t tmp_color[MAX_CHANNELS];

                    /* square normalized radius */
                    rr = rx*rx + ry*ry;

                    /* (x, y) in the Ellipse ? */
                    if (rr <= 1.)
                    {
                        opa = 1.0; /* start at full opacity */
                        if (hardness < 1.)
                        {
                            if (rr < hardness)
                                opa *= rr + 1.-(rr/hardness);
                            else
                                opa *= hardness/(1.-hardness)*(1.-rr);
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
    color[chan_count-1] = sums[chan_count-1] / sum_weight;

    if (color[chan_count-1] > 0.0)
    {
        /* colors are alpha-premultiplied, so un-multiply it now */
        for (i=0; i<chan_count-1; i++)
        {
            /* OPTIM: no need to divide color by weight sum as alpha sum is also weighted */
            sums[i] /= sums[chan_count-1];
            color[i] = CLAMP(sums[i], 0.0, 1.0); /* fix rounding errors */
        }
    }
    else
    {
        /* fully transparent color */
        color[0] = 1.0; /* to see if alpha is not taken in account */
        for (i=1; i<chan_count-1; i++)
            color[i] = 0.0;
    }

    return 0;
}
//-
//+ decay
/* Inspired from http://en.wikipedia.org/wiki/Exponential_decay */
static float
decay(float t, float tau)
{
    t = -t / tau;
    if (t >= -87.) /* limits says, float_MIN = 1.17549435E-38 => ~= exp(-87) */
        return expf(t);
    else
        return 0.0;
}
//-
//+ process_smudge
static int
process_smudge(PyBrush *self,
               float x, float y,
               float radius, float yratio, float cs, float sn,
               float hardness, float *color, float *alpha)
{
    int i, err;
    float fac, avg_color[MAX_CHANNELS];

    *alpha = 1.0;

    if (!self->b_BasicValues[BV_SMUDGE]) return 0;

    err = get_dab_color(self, self->b_Surface,
                        x, y, radius, yratio, hardness,
                        cs, sn, avg_color);
    if (err < 0) return 1;
    
    /* fully transparent? => no changes */
    if (err > 0) return 0;

    fac = self->b_BasicValues[BV_SMUDGE];
    *alpha = 1.0*(1.0-fac) + self->b_SmudgeColor[3]*fac;
    if (*alpha > 0.0)
    {
        for (i=0; i<3; i++)
            color[i] = (color[i]*(1.0-fac) + self->b_SmudgeColor[i]*fac) / *alpha;
    }
    else
    {
        color[0] = 1.0;
        color[1] = 0.0;
        color[2] = 0.0;
    }

    fac = self->b_BasicValues[BV_SMUDGE_VAR];
    if (fac > 0.0)
    {
        self->b_SmudgeColor[3] = self->b_SmudgeColor[3]*(1.0-fac) + avg_color[3]*fac;
        for (i=0; i<3; i++)
            self->b_SmudgeColor[i] = self->b_SmudgeColor[i]*(1.0-fac) + avg_color[i]*avg_color[3]*fac;
    }

    return 0;
}
//-
//+ get_radius_from_pressure
static float
get_radius_from_pressure(PyBrush *self, float pressure)
{
    float min = self->b_BasicValues[BV_RADIUS_MIN];
    float max = self->b_BasicValues[BV_RADIUS_MAX];
    float radius = min + (max-min)*pressure;
    return CLAMP(radius, 0.5, 128.0);
}
//-
//+ get_opacity_from_pressure
static float
get_opacity_from_pressure(PyBrush *self, float pressure)
{
    float min = self->b_BasicValues[BV_OPACITY_MIN];
    float max = self->b_BasicValues[BV_OPACITY_MAX];
    float opa = min + (max-min)*pressure;
    return CLAMP(opa, 0.0, 1.0);
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
        self->b_BasicValues[BV_MOTION_TRACK] = 1.0;
        self->b_BasicValues[BV_HI_SPEED_TRACK] = 1.0;

        /* let remaining fields to 0 */
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
//-
//+ brush_drawstroke
static PyObject *
brush_drawstroke(PyBrush *self, PyObject *args)
{
    PyObject *state;
    int ix, iy;
    float sx, sy, radius, dist, pressure, dx, dy, tiltx, tilty, yratio;
    float hardness, spacing, opacity;
    MyRec area;
    double time;

    if (NULL == self->b_Surface)
        return PyErr_Format(PyExc_RuntimeError, "Uninitialized brush");

    if (!PyArg_ParseTuple(args, "O", &state))
        return NULL;

    /* Compute the total movement vector */
    GET_2T_FLOAT_FROM_STROKE(state, sx, sy, "spos");
    dx = sx - self->b_OldSX;
    dy = sy - self->b_OldSY;
    dist = hypotf(dx, dy);

    if (dist == 0.)
        Py_RETURN_NONE;
        
    GET_2T_INT_FROM_STROKE(state, ix, iy, "vpos");
    GET_FLOAT_FROM_STROKE(state, time, "time");
    GET_FLOAT_FROM_STROKE(state, tiltx, "xtilt");
    GET_FLOAT_FROM_STROKE(state, tilty, "ytilt");

    area.x1 = area.y1 = INT32_MAX;
    area.x2 = area.y2 = INT32_MIN;
    
    /* computing dynamic brush parameters */
    GET_FLOAT_FROM_STROKE(state, pressure, "pressure");
    pressure = CLAMP(pressure, 0.0, 1.0);
    radius = get_radius_from_pressure(self, pressure);
    
    if (0.0 == radius)
        Py_RETURN_NONE;
    
    /* clamping values */
    yratio = CLAMP(self->b_BasicValues[BV_YRATIO], 1.0, 100.0);
    hardness = CLAMP(self->b_BasicValues[BV_HARDNESS], 0.01, 1.0);
    spacing = MAX(self->b_BasicValues[BV_SPACING], 0.01);
    
    {
        double dtime = time - self->b_Time;
        float speed = hypot(ix-self->b_OldIX, iy-self->b_OldIY) / dtime;
        float lofac, fac = decay(1e3/speed, self->b_BasicValues[BV_HI_SPEED_TRACK]);
        float color[MAX_CHANNELS];

        /* TODO: CYMK colorspace handling */
        color[0] = self->b_RGBColor[0];
        color[1] = self->b_RGBColor[1];
        color[2] = self->b_RGBColor[2];
        color[3] = 1.0;
        
        /* Motion tracking filter */
        sx -= dx*fac;
        sy -= dy*fac;
        lofac = decay(self->b_BasicValues[BV_MOTION_TRACK], 1.0);
        sx = sx*lofac + self->b_OldSX*(1.0-lofac);
        sy = sy*lofac + self->b_OldSY*(1.0-lofac);
        
        dx = sx - self->b_OldSX;
        dy = sy - self->b_OldSY;
        dist = hypotf(dx, dy);
    
        float dabs_frac, dabs_todo;

        /* Number of dabs to draw.
         * d is the euclidian distance between 2 events.
         * Note: this distance is inaccurate when dabs positions
         * are interpolated on a curved path.
         *
         * But I don't care! :-p
         */
         
        float x, y, p, r, opa, rad_per_sp=radius*spacing;
        float rad_rand = self->b_BasicValues[BV_RADIUS_RANDOM] * radius;
    
        dabs_frac = self->b_RemainSteps; /* float value in [0.0, 1.0[ */
        dabs_todo  = dist / rad_per_sp;
        //dabs_todo += dist / (self->b_Radius*spacing);

        x = self->b_OldSX;
        y = self->b_OldSY;
        p = self->b_Pressure;
        r = self->b_Radius;
        
        fac = self->b_BasicValues[BV_OPACITY_COMPENSATION]/spacing;
        opa = powf(self->b_Opacity, fac);
        self->b_Opacity = get_opacity_from_pressure(self, pressure);
        opacity = powf(self->b_Opacity, fac);
        
        /* Brush direction (cos/sin) */
        self->b_cs = -dy/dist;
        self->b_sn = dx/dist;
        
        /* until dabs to drawn remain */
        while ((dabs_frac+dabs_todo) >= 1.0)
        {
            float alpha=1.0;
            float d, step_frac; /* represent the fraction of distance to do
                                 * between the 2 control knots.
                                 */

            if (dabs_frac > 0.0)
            {
                step_frac = (1.0 - dabs_frac) / dabs_todo;
                dabs_frac = 0.0;
            }
            else
                step_frac = 1.0 / dabs_todo;
            
            /* Compute per dab states */
            x += step_frac * (sx-x);
            y += step_frac * (sy-y);
            p += step_frac * (pressure-p);
            if (CLAMP(p, 0.0, 1.0) != p) printf("p warn\n");
            r += step_frac * (radius-r);
            opa += step_frac * (opacity-opa);
            
            /* Randomizing position */
            if (rad_rand > 0.0)
            {
                sx += (myrand1()*2.-1.)*rad_rand;
                sy += (myrand2()*2.-1.)*rad_rand;
            }
                
            /* smudge step */
            if (process_smudge(self, x, y,
                               r, yratio, self->b_cs, self->b_sn,
                               hardness, color, &alpha))
            {
                return NULL;
            }

            /* Do erase? */
            if (self->b_BasicValues[BV_ERASE] < 1.0)
                alpha *= self->b_BasicValues[BV_ERASE];

#ifdef STAT_TIMING
            uint64_t ts1, ts2;
            READ_TIMESTAMP(ts1);
#endif
            if (drawdab_solid(self, &area, self->b_Surface,
                              x, y, r, yratio, hardness,
                              alpha, opa,
                              self->b_cs, self->b_sn, color))
            {
                return NULL;
            }

#ifdef STAT_TIMING
            READ_TIMESTAMP(ts2);
            self->b_Times[0] += ts2 - ts1;
            self->b_TimesCount[0]++;
#endif

            dist = hypotf(sx-x, sy-y);
            d = dist / rad_per_sp;
            //d += dist / (self->b_Radius*spacing);
            if (d == dabs_todo) Py_RETURN_NONE; /* safe exit */
            dabs_todo = d;
        }
        
        self->b_RemainSteps = dabs_frac+dabs_todo;
    }
    
    /* Record values */
    self->b_OldIX = ix;
    self->b_OldIY = iy;
    self->b_OldSX = sx;
    self->b_OldSY = sy;
    self->b_Pressure = pressure;
    self->b_Time = time;
    self->b_Radius = radius;

    /* something drawn? */
    //printf("%d %d %d %d\n", area.x1, area.y1, area.x2, area.y2);
    if (area.x1 != INT32_MAX)
        return Py_BuildValue("iiII", area.x1, area.y1, area.x2-area.x1+1, area.y2-area.y1+1);
        
    Py_RETURN_NONE;
}
//-
//+ brush_invalid_cache
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
//-
//+ brush_stroke_start
static PyObject *
brush_stroke_start(PyBrush *self, PyObject *args)
{
    PyObject *state, *res;
    float xtilt, ytilt;
    float alpha, color[MAX_CHANNELS];

    if (!PyArg_ParseTuple(args, "O", &state))
        return NULL;

    /* Read device states */
    GET_2T_INT_FROM_STROKE(state, self->b_OldIX, self->b_OldIY, "vpos");
    GET_2T_FLOAT_FROM_STROKE(state, self->b_OldSX, self->b_OldSY, "spos");
    GET_FLOAT_FROM_STROKE(state, self->b_Pressure, "pressure");
    GET_FLOAT_FROM_STROKE(state, self->b_Time, "time");
    GET_FLOAT_FROM_STROKE(state, xtilt, "xtilt");
    GET_FLOAT_FROM_STROKE(state, ytilt, "ytilt");

    self->b_RemainSteps = 0.0;
    self->b_Pressure = CLAMP(self->b_Pressure, 0.0, 1.0);
    self->b_Radius = get_radius_from_pressure(self, self->b_Pressure);
    self->b_Opacity = get_opacity_from_pressure(self, self->b_Pressure);

    res = brush_invalid_cache(self);
    if (NULL == res)
        return NULL;

    Py_DECREF(res);

    memcpy(color, self->b_RGBColor, sizeof(self->b_RGBColor));
    
    /* setup starting smudge value */
    if (process_smudge(self, self->b_OldSX, self->b_OldSY,
                       self->b_Radius,
                       self->b_BasicValues[BV_YRATIO],
                       1.0, 0.0,
                       self->b_BasicValues[BV_HARDNESS],
                       color, &alpha))
    {
        return NULL;
    }

    Py_RETURN_NONE;
}
//-
//+ brush_stroke_end
static PyObject *
brush_stroke_end(PyBrush *self, PyObject *args)
{
    Py_RETURN_NONE;
}
//-
//+ brush_get_states
static PyObject *
brush_get_states(PyBrush *self)
{
    return PyBuffer_FromReadWriteMemory((void *)self->b_BasicValues, sizeof(self->b_BasicValues));
}
//-
//+ brush_get_state
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
//-
//+ brush_set_state
static PyObject *
brush_set_state(PyBrush *self, PyObject *args)
{
    unsigned int index;
    float value;

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
    float *ptr = &self->b_BasicValues[index];

    return PyFloat_FromDouble((double)*ptr);
}
//-
//+ brush_set_float
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

    *ptr = v;
    return 0;
}
//-
//+ brush_set_normalized_float
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
//-
//+ brush_get_hsvcolor
static PyObject *
brush_get_hsvcolor(PyBrush *self, void *closure)
{
    float ptr = self->b_HSVColor[(int)closure];
    return PyFloat_FromDouble(ptr);
}
//-
//+ brush_get_rgbcolor
static PyObject *
brush_get_rgbcolor(PyBrush *self, void *closure)
{
    float ptr = self->b_RGBColor[(int)closure];
    return PyFloat_FromDouble(ptr);
}
//-
//+ brush_set_hsvcolor
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
//-
//+ brush_set_rgbcolor
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
//-

//+ brush_get_hsv
static PyObject *
brush_get_hsv(PyBrush *self, void *closure)
{
    return Py_BuildValue("fff", self->b_HSVColor[0], self->b_HSVColor[1], self->b_HSVColor[2]);
}
//-
//+ brush_set_hsv
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
//-
//+ brush_get_rgb
static PyObject *
brush_get_rgb(PyBrush *self, void *closure)
{
    return Py_BuildValue("fff", self->b_RGBColor[0], self->b_RGBColor[1], self->b_RGBColor[2]);
}
//-
//+ brush_set_rgb
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
//-

static PyGetSetDef brush_getseters[] = {
    {"surface",         (getter)brush_get_surface, (setter)brush_set_surface,          "Surface to use", NULL},

    {"radius_min",      (getter)brush_get_float,   (setter)brush_set_float,            "Radius min",              (void *)BV_RADIUS_MIN},
    {"radius_max",      (getter)brush_get_float,   (setter)brush_set_float,            "Radius max",              (void *)BV_RADIUS_MAX},
    {"yratio",          (getter)brush_get_float,   (setter)brush_set_float,            "Y-ratio",                 (void *)BV_YRATIO},
    {"hardness",        (getter)brush_get_float,   (setter)brush_set_normalized_float, "Hardness",                (void *)BV_HARDNESS},
    {"opacity_min",     (getter)brush_get_float,   (setter)brush_set_normalized_float, "Opacity min",             (void *)BV_OPACITY_MIN},
    {"opacity_max",     (getter)brush_get_float,   (setter)brush_set_normalized_float, "Opacity max",             (void *)BV_OPACITY_MAX},
    {"opa_comp",        (getter)brush_get_float,   (setter)brush_set_float,            "Opacity compensation",    (void *)BV_OPACITY_COMPENSATION},
    {"erase",           (getter)brush_get_float,   (setter)brush_set_normalized_float, "Erase",                   (void *)BV_ERASE},
    {"radius_random",   (getter)brush_get_float,   (setter)brush_set_normalized_float, "Radius Randomize",        (void *)BV_RADIUS_RANDOM},
    {"spacing",         (getter)brush_get_float,   (setter)brush_set_float,            "Spacing",                 (void *)BV_SPACING},
    {"grain",           (getter)brush_get_float,   (setter)brush_set_normalized_float, "Grain factor",            (void *)BV_GRAIN_FAC},
    {"motion_track",    (getter)brush_get_float,   (setter)brush_set_float,            "Motion tracking factor",  (void *)BV_MOTION_TRACK},
    {"hi_speed_track",  (getter)brush_get_float,   (setter)brush_set_float,            "Hi speed tracking factor",(void *)BV_HI_SPEED_TRACK},
    {"smudge",          (getter)brush_get_float,   (setter)brush_set_normalized_float, "Smudge factor",           (void *)BV_SMUDGE},
    {"smudge_var",      (getter)brush_get_float,   (setter)brush_set_normalized_float, "Smudge variation factor", (void *)BV_SMUDGE_VAR},

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
    //{"drawdab_solid", (PyCFunction)brush_drawdab_solid, METH_VARARGS, NULL},
    {"draw_stroke",   (PyCFunction)brush_drawstroke,    METH_VARARGS, NULL},
    {"invalid_cache", (PyCFunction)brush_invalid_cache, METH_NOARGS,  NULL},
    {"stroke_start", (PyCFunction)brush_stroke_start, METH_VARARGS, NULL},
    {"stroke_end", (PyCFunction)brush_stroke_end, METH_VARARGS, NULL},
    {NULL} /* sentinel */
};

static PyMemberDef brush_members[] = {
    {"pressure", T_FLOAT, offsetof(PyBrush, b_Pressure), 0, NULL},
    {NULL}
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
    tp_getset       : brush_getseters,
    tp_members      : brush_members,
};


/*******************************************************************************************
** Module
*/

//+ _BrushMethods
static PyMethodDef _BrushMethods[] = {
    {NULL}
};
//-

//+ add_constants
static int add_constants(PyObject *m)
{
    INSI(m, "BV_RADIUS_MIN", BV_RADIUS_MIN);
    INSI(m, "BV_RADIUS_MAx", BV_RADIUS_MAX);
    INSI(m, "BV_YRATIO", BV_YRATIO);
    INSI(m, "BV_HARDNESS", BV_HARDNESS);
    INSI(m, "BV_OPACITY_MIN", BV_OPACITY_MIN);
    INSI(m, "BV_OPACITY_MAX", BV_OPACITY_MAX);
    INSI(m, "BV_OPACITY_COMPENSATION", BV_OPACITY_COMPENSATION);
    INSI(m, "BV_ERASE", BV_ERASE);
    INSI(m, "BV_RADIUS_RANDOM", BV_RADIUS_RANDOM);
    INSI(m, "BV_SPACING", BV_SPACING);
    INSI(m, "BV_GRAIN_FAC", BV_GRAIN_FAC);
    INSI(m, "BV_SMUDGE", BV_SMUDGE);
    INSI(m, "BV_SMUDGE_VAR", BV_SMUDGE_VAR);
    INSI(m, "BASIC_VALUES_MAX", BASIC_VALUES_MAX);

    return 0;
}
//-
//+ INITFUNC()
PyMODINIT_FUNC
INITFUNC(void)
{
    PyObject *m, *_pixbuf;

    if (PyType_Ready(&PyBrush_Type) < 0) return;

    m = Py_InitModule(MODNAME, _BrushMethods);
    if (NULL == m) return;

    if (add_constants(m)) return;

    ADD_TYPE(m, "Brush", &PyBrush_Type);

    /* Need the PyPixbuf_Type object from _pixbuf */
    _pixbuf = PyImport_ImportModule("model._pixbuf"); /* NR */
    if (NULL == _pixbuf)
        return;

    PyPixbuf_Type = (PyTypeObject *)PyObject_GetAttrString(_pixbuf, "Pixbuf"); /* NR */
    if (NULL == PyPixbuf_Type)
    {
        Py_DECREF(_pixbuf);
        return;
    }
}
//-
