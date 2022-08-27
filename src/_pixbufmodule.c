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

#define _PIXBUF_CORE

#include "common.h"
#include "_pixbufmodule.h"

#ifdef HAVE_GDK
#define GLIB_VERSION_MIN_REQUIRED GLIB_VERSION_2_36
#include <pygtk-2.0/pygobject.h>
#include <gdk-pixbuf/gdk-pixbuf.h>
#endif

#ifdef WITH_ALTIVEC
#include "altivec.h"
#endif

#ifndef INITFUNC
#define INITFUNC PyInit__pixbuf
#endif

#ifndef MODNAME
#define MODNAME "_pixbuf"
#endif

typedef struct PA_InitValue
{
    uint8_t        nc;
    uint8_t        bpc;
	uint8_t        bpp;
    colfloat2natif cfromfloat;
    colnatif2float ctofloat;
    writefunc      writepixel;
    write2func     write2pixel;
    readfunc       readpixel;
    writefunc      writepixel_alpha_locked;
} PA_InitValue;

typedef void (*blitfunc)(void* src, void *dst,
                         uint32_t width, uint32_t height,
                         Py_ssize_t src_stride, Py_ssize_t dst_stride);
typedef void (*blendfunc)(int count, uint16_t *dst, uint16_t *bg, uint16_t *fg);

static void rgb8_writepixel(void *, float, float, unsigned short *);
static void argb8_writepixel(void *, float, float, uint16_t *);
static void rgba8_writepixel(void *, float, float, uint16_t *);
static void argb8noa_writepixel(void *, float, float, uint16_t *);
static void rgba8noa_writepixel(void *, float, float, uint16_t *);
static void rgba15x_writepixel(void *, float, float, uint16_t *);
static void argb15x_writepixel(void *, float, float, uint16_t *);
static void cmyk8_writepixel(void *, float, float, uint16_t *);
static void cmyka15x_writepixel(void *, float, float, uint16_t *);

static void argb15x_writepixel_alpha_locked(void *, float, float, uint16_t *);

static void dummy_write2pixel(void *data, uint16_t *color);
static void argb8_write2pixel(void *data, uint16_t *color);
static void argb15x_write2pixel(void *data, uint16_t *color);

static void dummy_readpixel(void *, uint16_t *);
static void argb15x_readpixel(void *, uint16_t *);
static void rgba15x_readpixel(void *, uint16_t *);
static void rgba8_readpixel(void *, uint16_t *);
static void argb8_readpixel(void *, uint16_t *);

static void rgb8_fromfloat(float, void *);
static void rgba15x_fromfloat(float, void *);

static float rgb8_tofloat(void *);
static float rgba15x_tofloat(void *);

static const PA_InitValue gInitValues[] = {
    {/*PyPixBuf_PIXFMT_RGB_8,*/      3, 8,  3, rgb8_fromfloat,    rgb8_tofloat,    rgb8_writepixel,     dummy_write2pixel, dummy_readpixel, NULL},
    {/*PyPixBuf_PIXFMT_ARGB_8,*/     4, 8,  4, rgb8_fromfloat,    rgb8_tofloat,    argb8_writepixel,    argb8_write2pixel, argb8_readpixel, NULL},
    {/*PyPixBuf_PIXFMT_ARGB_8_NOA,*/ 4, 8,  4, rgb8_fromfloat,    rgb8_tofloat,    argb8noa_writepixel, dummy_write2pixel, dummy_readpixel, NULL},
    {/*PyPixBuf_PIXFMT_RGBA_8,*/     4, 8,  4, rgb8_fromfloat,    rgb8_tofloat,    rgba8_writepixel,    dummy_write2pixel, rgba8_readpixel, NULL},
    {/*PyPixbuf_PIXFMT_RGBA_8_NOA,*/ 4, 8,  4, rgb8_fromfloat,    rgb8_tofloat,    rgba8noa_writepixel, dummy_write2pixel, dummy_readpixel, NULL},
    {/*PyPixBuf_PIXFMT_CMYK_8,*/     4, 8,  4, rgb8_fromfloat,    rgb8_tofloat,    cmyk8_writepixel,    dummy_write2pixel, dummy_readpixel, NULL},
    {/*PyPixBuf_PIXFMT_RGBA_15X,*/   4, 16, 8, rgba15x_fromfloat, rgba15x_tofloat, rgba15x_writepixel,  dummy_write2pixel, rgba15x_readpixel, NULL},
    {/*PyPixBuf_PIXFMT_ARGB_15X,*/   4, 16, 8, rgba15x_fromfloat, rgba15x_tofloat, argb15x_writepixel,  argb15x_write2pixel, argb15x_readpixel, argb15x_writepixel_alpha_locked},
    {/*PyPixBuf_PIXFMT_CMYKA_15X,*/  5, 16, 10, rgba15x_fromfloat, rgba15x_tofloat, cmyka15x_writepixel, dummy_write2pixel, dummy_readpixel, NULL},

    {0}
};

/*******************************************************************************************
** Private routines
*/

/*** Pixel write functions ***/

static void
rgb8_writepixel(void *data, float opacity, float erase, uint16_t *color)
{
    static const float delta = 1.f / 510;
    uint8_t *pixel = data;
    uint32_t alpha, one_minus_alpha;

    opacity += delta;

    /* Adding delta to round values */
    alpha = (uint32_t)(opacity * erase * 255);
    one_minus_alpha = 255 - (uint32_t)(opacity * 255);

    /* R */ pixel[0] = (alpha*color[0] + one_minus_alpha*pixel[0]) / 255;
    /* G */ pixel[1] = (alpha*color[1] + one_minus_alpha*pixel[1]) / 255;
    /* B */ pixel[2] = (alpha*color[2] + one_minus_alpha*pixel[2]) / 255;
}

static void
rgba8_writepixel(void *data, float opacity, float erase, uint16_t *color)
{
    static const float delta = 1.f / 510;
    uint8_t *pixel = data;
    uint32_t alpha, one_minus_alpha;

    opacity += delta;

    /* Adding delta to round values */
    alpha = (uint32_t)(opacity * erase * 255);
    one_minus_alpha = 255 - (uint32_t)(opacity * 255);

    /* R */ pixel[0] = (alpha*color[0] + one_minus_alpha*pixel[0]) / 255;
    /* G */ pixel[1] = (alpha*color[1] + one_minus_alpha*pixel[1]) / 255;
    /* B */ pixel[2] = (alpha*color[2] + one_minus_alpha*pixel[2]) / 255;
    /* A */ pixel[3] =  alpha          + one_minus_alpha*pixel[3]  / 255;
}

static void
argb8_writepixel(void *data, float opacity, float erase, uint16_t *color)
{
    static const float delta = 1.f / 510;
    uint8_t *pixel = data;
    uint32_t alpha, one_minus_alpha;

    opacity += delta;

    /* Adding delta to round values */
    alpha = (uint32_t)(opacity * erase * 255);
    one_minus_alpha = 255 - (uint32_t)(opacity * 255);

    /* A */ pixel[0] =  alpha          + one_minus_alpha*pixel[0]  / 255;
    /* R */ pixel[1] = (alpha*color[0] + one_minus_alpha*pixel[1]) / 255;
    /* G */ pixel[2] = (alpha*color[1] + one_minus_alpha*pixel[2]) / 255;
    /* B */ pixel[3] = (alpha*color[2] + one_minus_alpha*pixel[3]) / 255;
}

static void
argb8noa_writepixel(void *data, float opacity, float erase, uint16_t *color)
{
    static const float delta = 1.f / 510;
    uint8_t *pixel = data;
    uint32_t alpha, one_minus_alpha;

    opacity += delta;

    /* Adding delta to round values */
    alpha = (uint32_t)(opacity * erase * 255);
    one_minus_alpha = 255 - (uint32_t)(opacity * 255);

    /* A */ pixel[0] =   alpha  + one_minus_alpha*pixel[0]/255;
    /* R */ pixel[1] = color[0] + one_minus_alpha*pixel[1]/255;
    /* G */ pixel[2] = color[1] + one_minus_alpha*pixel[2]/255;
    /* B */ pixel[3] = color[2] + one_minus_alpha*pixel[3]/255;
}

static void
rgba8noa_writepixel(void *data, float opacity, float erase, uint16_t *color)
{
    static const float delta = 1.f / 510;
    uint8_t *pixel = data;
    uint32_t alpha, one_minus_alpha;

    opacity += delta;

    /* Adding delta to round values */
    alpha = (uint32_t)(opacity * erase * 255);
    one_minus_alpha = 255 - (uint32_t)(opacity * 255);

    /* R */ pixel[0] = color[0] + one_minus_alpha*pixel[0]/255;
    /* G */ pixel[1] = color[1] + one_minus_alpha*pixel[1]/255;
    /* B */ pixel[2] = color[2] + one_minus_alpha*pixel[2]/255;
    /* A */ pixel[3] =   alpha  + one_minus_alpha*pixel[3]/255;
}

static void
cmyk8_writepixel(void *data, float opacity, float erase, uint16_t *color)
{
    static const float delta = 1.f / 510;
    uint8_t *pixel = data;
    uint32_t alpha, one_minus_alpha;

    opacity += delta;

    /* Adding delta to round values */
    alpha = (uint32_t)(opacity * erase * 255);
    one_minus_alpha = 255 - (uint32_t)(opacity * 255);

    /* C */ pixel[0] = (((alpha*color[0]*255)>>15) + one_minus_alpha*pixel[0]) / 255;
    /* M */ pixel[1] = (((alpha*color[1]*255)>>15) + one_minus_alpha*pixel[1]) / 255;
    /* Y */ pixel[2] = (((alpha*color[2]*255)>>15) + one_minus_alpha*pixel[2]) / 255;
    /* K */ pixel[3] = (((alpha*color[3]*255)>>15) + one_minus_alpha*pixel[3]) / 255;
}

static void
rgba15x_writepixel(void *data, float opacity, float erase, uint16_t *color)
{
    static const float delta = 1.f / (1<<16);
    uint16_t *pixel = data;
    uint32_t alpha, one_minus_alpha;

    opacity += delta;

    /* Adding delta to round values */
    alpha = (uint32_t)(opacity * erase * (1<<15));
    one_minus_alpha = (1<<15) - (uint32_t)(opacity * (1<<15));

    /* R */ pixel[0] = (alpha*color[0] + one_minus_alpha*pixel[0]) / (1<<15);
    /* G */ pixel[1] = (alpha*color[1] + one_minus_alpha*pixel[1]) / (1<<15);
    /* B */ pixel[2] = (alpha*color[2] + one_minus_alpha*pixel[2]) / (1<<15);
    /* A */ pixel[3] =  alpha          + one_minus_alpha*pixel[3]  / (1<<15);
}

static void
argb15x_writepixel(void *data, float opacity, float erase, uint16_t *color)
{
    static const float delta = 1.f / (1<<16);
    uint16_t *pixel = data;
    uint32_t alpha, one_minus_alpha;

    opacity += delta;

    /* Adding delta to round values */
    alpha = (uint32_t)(opacity * erase * (1<<15));
    one_minus_alpha = (1<<15) - (uint32_t)(opacity * (1<<15));

    /* A */ pixel[0] =  alpha          + one_minus_alpha*pixel[0]  / (1<<15);
    /* R */ pixel[1] = (alpha*color[0] + one_minus_alpha*pixel[1]) / (1<<15);
    /* G */ pixel[2] = (alpha*color[1] + one_minus_alpha*pixel[2]) / (1<<15);
    /* B */ pixel[3] = (alpha*color[2] + one_minus_alpha*pixel[3]) / (1<<15);
}

static void
argb15x_writepixel_alpha_locked(void *data, float opacity, float erase, uint16_t *color)
{
    static const float delta = 1.f / (1<<16);
    uint16_t *pixel = data;
    uint32_t alpha, one_minus_alpha;

    opacity += delta;

    /* Adding delta to round values */
    alpha = (uint32_t)(opacity * erase * (1<<15));
    one_minus_alpha = (1<<15) - (uint32_t)(opacity * (1<<15));

    ///* A */ pixel[0] =  alpha          + one_minus_alpha*pixel[0]  / (1<<15);
    /* R */ pixel[1] = (alpha*color[0] + one_minus_alpha*pixel[1]) / (1<<15);
    /* G */ pixel[2] = (alpha*color[1] + one_minus_alpha*pixel[2]) / (1<<15);
    /* B */ pixel[3] = (alpha*color[2] + one_minus_alpha*pixel[3]) / (1<<15);
}

static void
cmyka15x_writepixel(void *data, float opacity, float erase, uint16_t *color)
{
    static const float delta = 1.f / (1<<16);
    uint16_t *pixel = data;
    uint32_t alpha, one_minus_alpha;

    opacity += delta;

    /* Adding delta to round values */
    alpha = (uint32_t)(opacity * erase * (1<<15));
    one_minus_alpha = (1<<15) - (uint32_t)(opacity * (1<<15));

    /* C */ pixel[0] = (alpha*color[0] + one_minus_alpha*pixel[0]) / (1<<15);
    /* M */ pixel[1] = (alpha*color[1] + one_minus_alpha*pixel[1]) / (1<<15);
    /* Y */ pixel[2] = (alpha*color[2] + one_minus_alpha*pixel[2]) / (1<<15);
    /* K */ pixel[3] = (alpha*color[3] + one_minus_alpha*pixel[3]) / (1<<15);
    /* A */ pixel[4] =  alpha          + one_minus_alpha*pixel[4]  / (1<<15);
}

static void
dummy_write2pixel(void *data, uint16_t *color)
{
    /* pass */
}

static void
argb15x_write2pixel(void *data, uint16_t *color)
{
    uint16_t *pixel = data;

    /* A */ pixel[0] = color[3];
    /* R */ pixel[1] = color[0];
    /* G */ pixel[2] = color[1];
    /* B */ pixel[3] = color[2];
}

static void
argb8_write2pixel(void *data, uint16_t *color)
{
    uint8_t *pixel = data;

    /* A */ pixel[0] = color[3];
    /* R */ pixel[1] = color[0];
    /* G */ pixel[2] = color[1];
    /* B */ pixel[3] = color[2];
}

static void
dummy_readpixel(void *data, uint16_t *color)
{
    /* R */ color[0] = 0;
    /* G */ color[1] = 0;
    /* B */ color[2] = 0;
    /* A */ color[3] = 0;
}

static void
argb15x_readpixel(void *data, uint16_t *color)
{
    uint16_t *pixel = data;
    uint16_t alpha = pixel[0];

    /* R */ color[0] = pixel[1];
    /* G */ color[1] = pixel[2];
    /* B */ color[2] = pixel[3];
    /* A */ color[3] = alpha;
}

static void
rgba15x_readpixel(void *data, uint16_t *color)
{
    uint16_t *pixel = data;

    /* R */ color[0] = pixel[0];
    /* G */ color[1] = pixel[1];
    /* B */ color[2] = pixel[2];
    /* A */ color[3] = pixel[3];
}

static void
rgba8_readpixel(void *data, uint16_t *color)
{
    uint8_t *pixel = data;

    /* R */ color[0] = pixel[0];
    /* G */ color[1] = pixel[1];
    /* B */ color[2] = pixel[2];
    /* A */ color[3] = pixel[3];
}

static void
argb8_readpixel(void *data, uint16_t *color)
{
    uint8_t *pixel = data;
    uint8_t alpha = pixel[0];

    /* R */ color[0] = pixel[1];
    /* G */ color[1] = pixel[2];
    /* B */ color[2] = pixel[3];
    /* A */ color[3] = alpha;
}

/*** Color conversion functions ***/

/* /!\ no clamping applied ! */

static void
rgb8_fromfloat(float from, void *to)
{
    *((uint16_t *)to) = (uint8_t)(from * 255);
}

static void
rgba15x_fromfloat(float from, void *to)
{
    *((uint16_t *)to) = (uint16_t)(from * (1<<15));
}

static float
rgb8_tofloat(void *from)
{
    /* We expect no round errors causing float > 1.0 */
    return ((float)*(uint16_t *)from) / 255;
}

static float
rgba15x_tofloat(void *from)
{
    return (float)(*(uint16_t *)from) / (1<<15);
}

/********* Bliting **************************************/

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

/* Alpha-premul is conservated */
static inline void
argb15x_to_argb8_row(uint16_t *src, uint8_t *dst, unsigned int w)
{
    unsigned int x;

    for (x=0; x < w; x++)
    {
        uint32_t alpha = src[0];

        if (alpha > 0)
        {
            uint8_t r,g,b,a;

            /* Convert to range [0, 255], keep values alpha pre-multiplied */
            r = ((uint32_t)src[1] * 255 + ROUND_ERROR_15BITS) >> 15;
            g = ((uint32_t)src[2] * 255 + ROUND_ERROR_15BITS) >> 15;
            b = ((uint32_t)src[3] * 255 + ROUND_ERROR_15BITS) >> 15;
            a = (alpha * 255 + ROUND_ERROR_15BITS) >> 15;

            /* ARGB8 */
            dst[0] = a;
            dst[1] = r;
            dst[2] = g;
            dst[3] = b;
        }
        else
            *(uint32_t *)dst = 0;

        /* Next ARGB pixel */
        src += 4;
        dst += 4;
    }
}

static void
argb15x_to_argb8(uint16_t *src1, uint8_t *dst1,
                 unsigned int w, unsigned int h,
                 Py_ssize_t src_stride, Py_ssize_t dst_stride)
{
    unsigned int y;

#ifdef WITH_ALTIVEC
    const vector unsigned short v255 = (vector unsigned short){255,255,255,255,255,255,255,255};
    const vector unsigned int vshift15 = vec_splat_u32(15);
    const vector unsigned char vperm_h = (vector unsigned char) {3,19,7,23,11,27,15,31,0,0,0,0,0,0,0,0};
    const vector unsigned char vperm_l = (vector unsigned char) {0,0,0,0,0,0,0,0,3,19,7,23,11,27,15,31};
#endif

    src_stride /= sizeof(*src1);
    dst_stride /= sizeof(*dst1);

    for (y=0; y < h; y++, src1 += src_stride, dst1 += dst_stride)
    {
        uint16_t *src = src1;
        uint8_t *dst = dst1;

#ifdef WITH_ALTIVEC
        if ((w < 4) || ((unsigned int)src & 15) || ((unsigned int)dst & 15))
        {
            argb15x_to_argb8_row(src, dst, w);
        }
        else
        {
            unsigned int x;
            int remains = w & 3; /* one ARGB15X pixel = 8 bytes, we compute on 4 pixels per loop */

            /* 4 ARGB pixels loop */
            for (x=0; x < (w-remains); x += 4, src += 4*4, dst += 4*4)
            {
                /* Load 4 ARGB15X pixels in 2 vectors */
                const vector signed short vpixels15x_0 = vec_ld(0, (signed short *)src);
                const vector signed short vpixels15x_1 = vec_ld(16, (signed short *)src);

                /* Convert them to ARGB8 alpha-premul pixels */
                const vector unsigned int vagag_h = vec_sr(vec_mule((vector unsigned short)vpixels15x_0, v255), vshift15);
                const vector unsigned int vrbrb_h = vec_sr(vec_mulo((vector unsigned short)vpixels15x_0, v255), vshift15);
                const vector unsigned int vagag_l = vec_sr(vec_mule((vector unsigned short)vpixels15x_1, v255), vshift15);
                const vector unsigned int vrbrb_l = vec_sr(vec_mulo((vector unsigned short)vpixels15x_1, v255), vshift15);

                const vector unsigned char vpx8_h = vec_perm((vector unsigned char)vagag_h, (vector unsigned char)vrbrb_h, vperm_h);
                const vector unsigned char vpx8_l = vec_perm((vector unsigned char)vagag_l, (vector unsigned char)vrbrb_l, vperm_l);

                const vector unsigned char vpixels8 = vec_add(vpx8_h, vpx8_l);

                /* Save result as 4 ARGB8 pixels */
                vec_st(vpixels8, 0, (unsigned char *)dst);
            }

            argb15x_to_argb8_row(src, dst, remains);
            apx += w-remains;
        }
#else
            argb15x_to_argb8_row(src, dst, w);
#endif
    }
}

/* Alpha-premul is removed */
static void
argb15x_to_argb8_noa(uint16_t *src1, uint8_t *dst1,
                     uint32_t w, uint32_t h,
                     Py_ssize_t src_stride, Py_ssize_t dst_stride)
{
    uint32_t x, y;

    src_stride /= sizeof(*src1);
    dst_stride /= sizeof(*dst1);

    for (y=0; y < h; y++, src1 += src_stride, dst1 += dst_stride)
    {
        uint16_t *src = src1;
        uint8_t *dst = dst1;

        for (x=0; x < w; x++)
        {
            uint32_t alpha = src[0];

            if (alpha > 0)
            {
                uint8_t a,r,g,b;

                /* Un-multiply by alpha, rounding and convert to range [0, 255] */
                a = (alpha * 255 + ROUND_ERROR_15BITS) >> 15;
                r = ((((uint32_t)src[1]<<15) + alpha/2) / alpha * 255 + ROUND_ERROR_15BITS) >> 15;
                g = ((((uint32_t)src[2]<<15) + alpha/2) / alpha * 255 + ROUND_ERROR_15BITS) >> 15;
                b = ((((uint32_t)src[3]<<15) + alpha/2) / alpha * 255 + ROUND_ERROR_15BITS) >> 15;

                /* ARGB8 */
                dst[0] = a;
                dst[1] = r;
                dst[2] = g;
                dst[3] = b;
            }
            else
                *(uint32_t *)dst = 0;

            /* Next ARGB pixel */
            src += 4;
            dst += 4;
        }
    }
}

/* Alpha-premul is conservated */
static void
argb15x_to_bgra8(uint16_t *src1, uint8_t *dst1,
                 uint32_t w, uint32_t h,
                 Py_ssize_t src_stride, Py_ssize_t dst_stride)
{
    uint32_t x, y;

    src_stride /= sizeof(*src1);
    dst_stride /= sizeof(*dst1);

    for (y=0; y < h; y++, src1 += src_stride, dst1 += dst_stride)
    {
        uint16_t *src = src1;
        uint8_t *dst = dst1;

        for (x=0; x < w; x++)
        {
			uint8_t a,r,g,b;

			/* Convert to range [0, 255], keep values alpha pre-multiplied */
			a = ((uint32_t)src[0] * 255 + ROUND_ERROR_15BITS) >> 15;
			r = ((uint32_t)src[1] * 255 + ROUND_ERROR_15BITS) >> 15;
			g = ((uint32_t)src[2] * 255 + ROUND_ERROR_15BITS) >> 15;
			b = ((uint32_t)src[3] * 255 + ROUND_ERROR_15BITS) >> 15;

			/* BGRA8 */
			dst[0] = b;
			dst[1] = g;
			dst[2] = r;
			dst[3] = a;

            /* Next ARGB pixel */
            src += 4;
            dst += 4;
        }
    }
}

/* Alpha-premul is conservated */
static void
argb15x_to_rgba8(uint16_t *src1, uint8_t *dst1,
                 uint32_t w, uint32_t h,
                 Py_ssize_t src_stride, Py_ssize_t dst_stride)
{
    uint32_t x, y;

    src_stride /= sizeof(*src1);
    dst_stride /= sizeof(*dst1);

    for (y=0; y < h; y++, src1 += src_stride, dst1 += dst_stride)
    {
        uint16_t *src = src1;
        uint8_t *dst = dst1;

        for (x=0; x < w; x++)
        {
            uint32_t alpha = src[0];

            if (alpha > 0)
            {
                uint8_t r,g,b,a;

                /* Convert to range [0, 255], keep values alpha pre-multiplied */
                r = ((uint32_t)src[1] * 255 + ROUND_ERROR_15BITS) >> 15;
                g = ((uint32_t)src[2] * 255 + ROUND_ERROR_15BITS) >> 15;
                b = ((uint32_t)src[3] * 255 + ROUND_ERROR_15BITS) >> 15;
                a = (alpha * 255 + ROUND_ERROR_15BITS) >> 15;

                /* RGBA8 */
                dst[0] = r;
                dst[1] = g;
                dst[2] = b;
                dst[3] = a;
            }
            else
                *(uint32_t *)dst = 0;

            /* Next ARGB pixel */
            src += 4;
            dst += 4;
        }
    }
}

/* Alpha-premul is removed */
static void
argb15x_to_rgba8_noa(uint16_t *src1, uint8_t *dst1,
                     uint32_t w, uint32_t h,
                     Py_ssize_t src_stride, Py_ssize_t dst_stride)
{
    uint32_t x, y;

    src_stride /= sizeof(*src1);
    dst_stride /= sizeof(*dst1);

    for (y=0; y < h; y++, src1 += src_stride, dst1 += dst_stride)
    {
        uint16_t *src = src1;
        uint8_t *dst = dst1;

        for (x=0; x < w; x++)
        {
            uint32_t alpha = src[0];

            if (alpha > 0)
            {
                uint8_t r,g,b;

                /* Un-multiply by alpha, rounding and convert to range [0, 255]
                 * TODO: No dithering used here!
                 */
                r = ((((uint32_t)src[1]<<15) + alpha/2) / alpha * 255 + ROUND_ERROR_15BITS) >> 15;
                g = ((((uint32_t)src[2]<<15) + alpha/2) / alpha * 255 + ROUND_ERROR_15BITS) >> 15;
                b = ((((uint32_t)src[3]<<15) + alpha/2) / alpha * 255 + ROUND_ERROR_15BITS) >> 15;

                /* RGBA8_NOA */
                dst[0] = r;
                dst[1] = g;
                dst[2] = b;
                dst[3] = (alpha * 255 + ROUND_ERROR_15BITS) >> 15;
            }
            else
                *(uint32_t *)dst = 0;

            /* Next ARGB pixel */
            src += 4;
            dst += 4;
        }
    }
}

/* Alpha-premul is conservated */
static void
argb15x_to_abgr8(uint16_t *src1, uint8_t *dst1,
                 uint32_t w, uint32_t h,
                 Py_ssize_t src_stride, Py_ssize_t dst_stride)
{
    uint32_t x, y;

    src_stride /= sizeof(*src1);
    dst_stride /= sizeof(*dst1);

    for (y=0; y < h; y++, src1 += src_stride, dst1 += dst_stride)
    {
        uint16_t *src = src1;
        uint8_t *dst = dst1;

        for (x=0; x <w; x++)
        {
            uint32_t alpha = src[0];

            if (alpha > 0)
            {
                uint8_t r,g,b;

                /* Convert to range [0, 255], keep values alpha pre-multiplied */
                r = ((uint32_t)src[1] * 255 + ROUND_ERROR_15BITS) >> 15;
                g = ((uint32_t)src[2] * 255 + ROUND_ERROR_15BITS) >> 15;
                b = ((uint32_t)src[3] * 255 + ROUND_ERROR_15BITS) >> 15;

                /* ABGR8 */
                dst[0] = (alpha * 255 + ROUND_ERROR_15BITS) >> 15;
                dst[1] = b;
                dst[2] = g;
                dst[3] = r;
            }
            else
                *(uint32_t *)dst = 0;

            /* Next ARGB pixel */
            src += 4;
            dst += 4;
        }
    }
}

/* Alpha-premul is not conservated */
static void
argb15x_to_rgb8(uint16_t *src1, uint8_t *dst1,
                uint32_t w, uint32_t h,
                Py_ssize_t src_stride, Py_ssize_t dst_stride)
{
    uint32_t x, y;

    src_stride /= sizeof(*src1);
    dst_stride /= sizeof(*dst1);

    for (y=0; y < h; y++, src1 += src_stride, dst1 += dst_stride)
    {
        uint16_t *src = src1;
        uint8_t *dst = dst1;

        for (x=0; x < w; x++)
        {
            uint32_t alpha = src[0];

            if (alpha > 0)
            {
                uint8_t r,g,b;

                /* Un-multiply by alpha, rounding and convert to range [0, 255] */
                r = ((((uint32_t)src[1]<<15) + alpha/2) / alpha * 255 + ROUND_ERROR_15BITS) >> 15;
                g = ((((uint32_t)src[2]<<15) + alpha/2) / alpha * 255 + ROUND_ERROR_15BITS) >> 15;
                b = ((((uint32_t)src[3]<<15) + alpha/2) / alpha * 255 + ROUND_ERROR_15BITS) >> 15;

                /* RGB8 */
                dst[0] = r;
                dst[1] = g;
                dst[2] = b;
            }
            else
                *(uint32_t *)dst = 0;

            /* Next pixel */
            src += 4;
            dst += 3;
        }
    }
}

static void
rgba8_noa_to_argb15x(uint8_t *src1, uint16_t *dst1,
                     uint32_t w, uint32_t h,
                     Py_ssize_t src_stride, Py_ssize_t dst_stride)
{
    uint32_t x, y;

    src_stride /= sizeof(*src1);
    dst_stride /= sizeof(*dst1);

    for (y=0; y < h; y++, src1 += src_stride, dst1 += dst_stride)
    {
        uint8_t *src = src1;
        uint16_t *dst = dst1;

        for (x=0; x < w; x++)
        {
            /* 8bits -> 15Bits convertion using rouding error correction (the added 255/2) */
            uint32_t alpha = (((uint32_t)src[3] << 15) + ROUND_ERROR_8BITS) / 255;

            if (alpha > 0)
            {
                uint16_t r,g,b;

                /* Convert to 15-bits value, pre-mul values by alpha (with rounding error handling).
                 *
                 * Notes: Quality performance of this rounding algorithme:
                 * I'm using python here to compute the number of unique values generated by each algo
                 * for all possible combinaison of one channel values and alpha values.
                 * In follwing lines, f = lambda x: ((x<<15) + 255/2) / 255
                 *
                 * >>> d0=[(r,a) for r in xrange(256) for a in xrange(256)]
                 * >>> d1=[(r*a,a) for r in xrange(256) for a in xrange(256)]
                 * >>> d2=[((f(r) * f(a) + (1<<15)/2) / (1<<15), a) for r in xrange(256) for a in xrange(256)]
                 * >>> d3=[((r * f(a) + 255/2) / 255, a) for r in xrange(256) for a in xrange(256)]
                 * >>> len(set(d0))
                 * 65536
                 * >>> len(set(d1))
                 * 65281
                 * >>> len(set(d2))
                 * 65155
                 * >>> len(set(d3))
                 * 65155
                 *
                 * What we can see:
                 *   - d0 is the best case: all combinaisons!
                 *   - d1: 16bits buffer, no losses, the missing 255 values are all fully transparent data (a=0, r=any).
                 *   - d2: 15bits buffer, algo from MyPaint, less than 0.2% of quality loss.
                 *   - d3: 15bits buffer, my algo, same losses.
                 *
                 * Even if d2 and d3 are equals in term of quality, my algo don't use twice the f function!
                 * => my algo is faster (timeit gives 30%).
                 */
                r = ((uint32_t)src[0] * alpha + ROUND_ERROR_8BITS) / 255;
                g = ((uint32_t)src[1] * alpha + ROUND_ERROR_8BITS) / 255;
                b = ((uint32_t)src[2] * alpha + ROUND_ERROR_8BITS) / 255;

                /* ARGB15X */
                dst[0] = alpha;
                dst[1] = r;
                dst[2] = g;
                dst[3] = b;
            }
            else
            {
                /* ARGB15X = 16 bytes */
                ((uint32_t *)dst)[0] = 0;
                ((uint32_t *)dst)[1] = 0;
            }

            /* Next ARGB pixel */
            src += 4;
            dst += 4;
        }
    }
}

static void
argb8_to_argb15x(uint8_t *src1, uint16_t *dst1,
                 uint32_t w, uint32_t h,
                 Py_ssize_t src_stride, Py_ssize_t dst_stride)
{
    uint32_t x, y;

    src_stride /= sizeof(*src1);
    dst_stride /= sizeof(*dst1);

    for (y=0; y < h; y++, src1 += src_stride, dst1 += dst_stride)
    {
        uint8_t *src = src1;
        uint16_t *dst = dst1;

        for (x=0; x < w; x++)
        {
            uint32_t alpha = (uint32_t)src[0] << 7;

            if (alpha > 0)
            {
                uint16_t r,g,b;

                /* Convert to 15-bits value, pre-mul values by alpha */
                r = (uint16_t)src[1] << 7;
                g = (uint16_t)src[2] << 7;
                b = (uint16_t)src[3] << 7;

                /* ARGB15X */
                dst[0] = alpha;
                dst[1] = r;
                dst[2] = g;
                dst[3] = b;
            }
            else
            {
                /* ARGB15X = 16 bytes */
                ((uint32_t *)dst)[0] = 0;
                ((uint32_t *)dst)[1] = 0;
            }

            /* Next ARGB pixel */
            src += 4;
            dst += 4;
        }
    }
}

static void
bgra8_to_argb15x(uint8_t *src1, uint16_t *dst1,
                 uint32_t w, uint32_t h,
                 Py_ssize_t src_stride, Py_ssize_t dst_stride)
{
    uint32_t x, y;

    src_stride /= sizeof(*src1);
    dst_stride /= sizeof(*dst1);

    for (y=0; y < h; y++, src1 += src_stride, dst1 += dst_stride)
    {
        uint8_t *src = src1;
        uint16_t *dst = dst1;

        for (x=0; x < w; x++)
        {
            uint16_t alpha = (uint16_t)src[3] << 7;

            if (alpha > 0)
            {
                uint16_t r,g,b;

                /* Convert to 15-bits value, pre-mul values by alpha */
                b = (uint16_t)src[0] << 7;
                g = (uint16_t)src[1] << 7;
                r = (uint16_t)src[2] << 7;

                /* ARGB15X */
                dst[0] = alpha;
                dst[1] = r;
                dst[2] = g;
                dst[3] = b;
            }
            else
            {
                /* ARGB15X = 16 bytes */
                ((uint32_t *)dst)[0] = 0;
                ((uint32_t *)dst)[1] = 0;
            }

            /* Next ARGB pixel */
            src += 4;
            dst += 4;
        }
    }
}

static void
argb8_to_rgba8(uint8_t *src1, uint8_t *dst1,
               uint32_t w, uint32_t h,
               Py_ssize_t src_stride, Py_ssize_t dst_stride)
{
    uint32_t x, y;

    src_stride /= sizeof(*src1);
    dst_stride /= sizeof(*dst1);

    for (y=0; y < h; y++, src1 += src_stride, dst1 += dst_stride)
    {
        uint8_t *src = src1;
        uint8_t *dst = dst1;

        for (x=0; x < w; x++)
        {
            uint32_t alpha = src[0];

            if (alpha > 0)
            {
                uint32_t r,g,b;

                /* Read ARGB8 */
                r = src[1];
                g = src[2];
                b = src[3];

                /* Write RGBA8 */
                dst[0] = r;
                dst[1] = g;
                dst[2] = b;
                dst[3] = alpha;
            }
            else
                *(uint32_t *)dst = 0;

            /* Next ARGB pixel */
            src += 4;
            dst += 4;
        }
    }
}

static void
argb8_to_argb8_noa(uint8_t *src1, uint8_t *dst1,
                   uint32_t w, uint32_t h,
                   Py_ssize_t src_stride, Py_ssize_t dst_stride)
{
    uint32_t x, y;

    src_stride /= sizeof(*src1);
    dst_stride /= sizeof(*dst1);

    for (y=0; y < h; y++, src1 += src_stride, dst1 += dst_stride)
    {
        uint8_t *src = src1;
        uint8_t *dst = dst1;

        for (x=0; x < w; x++)
        {
            uint32_t alpha = src[0];

            if (alpha > 0)
            {
                uint32_t r,g,b;

                /* Un-multiply by alpha, rounding and convert to range [0, 255] */
                r = ((uint32_t)src[1] * 255 + alpha/2) / alpha;
                g = ((uint32_t)src[2] * 255 + alpha/2) / alpha;
                b = ((uint32_t)src[3] * 255 + alpha/2) / alpha;

                /* ARGB8_NOA */
                dst[0] = alpha;
                dst[1] = r;
                dst[2] = g;
                dst[3] = b;
            }
            else
                *(uint32_t *)dst = 0;

            /* Next ARGB pixel */
            src += 4;
            dst += 4;
        }
    }
}

static void
argb8_to_rgba8_noa(uint8_t *src1, uint8_t *dst1,
                   uint32_t w, uint32_t h,
                   Py_ssize_t src_stride, Py_ssize_t dst_stride)
{
    uint32_t x, y;

    src_stride /= sizeof(*src1);
    dst_stride /= sizeof(*dst1);

    for (y=0; y < h; y++, src1 += src_stride, dst1 += dst_stride)
    {
        uint8_t *src = src1;
        uint8_t *dst = dst1;

        for (x=0; x < w; x++)
        {
            uint32_t alpha = src[0];

            if (alpha > 0)
            {
                uint32_t r,g,b;

                /* Un-multiply by alpha, rounding and convert to range [0, 255] */
                r = ((uint32_t)src[1] * 255 + alpha/2) / alpha;
                g = ((uint32_t)src[2] * 255 + alpha/2) / alpha;
                b = ((uint32_t)src[3] * 255 + alpha/2) / alpha;

                /* RGBA8_NOA */
                dst[0] = r;
                dst[1] = g;
                dst[2] = b;
                dst[3] = alpha;
            }
            else
                *(uint32_t *)dst = 0;

            /* Next ARGB pixel */
            src += 4;
            dst += 4;
        }
    }
}

static void
argb8_noa_to_argb8_noa(uint8_t *src1, uint8_t *dst1,
                       uint32_t w, uint32_t h,
                       Py_ssize_t src_stride, Py_ssize_t dst_stride)
{
    uint32_t y;

    src_stride /= sizeof(*src1);
    dst_stride /= sizeof(*dst1);

    for (y=0; y < h; y++, src1 += src_stride, dst1 += dst_stride)
        memcpy(dst1, src1, w*sizeof(dst1));
}

static void
rgbx15x_to_rgbx15x(uint16_t *src1, uint16_t *dst1,
                   uint32_t w, uint32_t h,
                   Py_ssize_t src_stride, Py_ssize_t dst_stride)
{
    uint32_t y;

    src_stride /= sizeof(*src1);
    dst_stride /= sizeof(*dst1);

    for (y=0; y < h; y++, src1 += src_stride, dst1 += dst_stride)
        memcpy(dst1, src1, w*8);
}

/********* Compositing **********************************/

static void
compose_argb8_noa_to_argb8_noa(uint8_t *src1, uint8_t *dst1,
                               uint32_t w, uint32_t h,
                               Py_ssize_t src_stride, Py_ssize_t dst_stride)
{
    uint32_t x, y;

    src_stride /= sizeof(*src1);
    dst_stride /= sizeof(*dst1);

    for (y=0; y < h; y++, src1 += src_stride, dst1 += dst_stride)
    {
        uint8_t *src = src1;
        uint8_t *dst = dst1;

        for (x=0; x < w; x++)
        {
            uint32_t alpha = src[0];

            if (alpha > 0)
            {
                uint32_t one_minus_alpha = 255 - alpha;

                /* ARGB8 -> ARGB8 */
                dst[0] = MAX(dst[0], alpha);
                dst[1] = (one_minus_alpha * dst[1] + alpha * src[1]) / 255;
                dst[2] = (one_minus_alpha * dst[2] + alpha * src[2]) / 255;
                dst[3] = (one_minus_alpha * dst[3] + alpha * src[3]) / 255;

            } /* else unchange the destination */

            /* Next ARGB pixel */
            src += 4;
            dst += 4;
        }
    }
}

/* Alpha-premul is removed */
static void
compose_argb8_to_argb8_noa(uint8_t *src1, uint8_t *dst1,
                           uint32_t w, uint32_t h,
                           Py_ssize_t src_stride, Py_ssize_t dst_stride)
{
    uint32_t x, y;

    src_stride /= sizeof(*src1);
    dst_stride /= sizeof(*dst1);

    for (y=0; y < h; y++, src1 += src_stride, dst1 += dst_stride)
    {
        uint8_t *src = src1;
        uint8_t *dst = dst1;

        for (x=0; x < w; x++)
        {
            uint32_t alpha = src[0];

            if (alpha > 0)
            {
                uint32_t one_minus_alpha = 255 - alpha;
                uint32_t r,g,b;

                /* rounding and convert to range [0, 255], but let alpha multiplied for the composing */
                r = ((uint32_t)src[1] * 255 + alpha/2);
                g = ((uint32_t)src[2] * 255 + alpha/2);
                b = ((uint32_t)src[3] * 255 + alpha/2);

                /* ARGB8_NOA */
                dst[0] = MAX(dst[0], alpha);
                dst[1] = (one_minus_alpha * dst[1] + r + ROUND_ERROR_8BITS) / 255;
                dst[2] = (one_minus_alpha * dst[2] + g + ROUND_ERROR_8BITS) / 255;
                dst[3] = (one_minus_alpha * dst[3] + b + ROUND_ERROR_8BITS) / 255;

            } /* else unchange the destination */

            /* Next ARGB pixel */
            src += 4;
            dst += 4;
        }
    }
}

static void
compose_argb15x_to_argb15x(uint16_t *src1, uint16_t *dst1,
                           uint32_t w, uint32_t h,
                           Py_ssize_t src_stride, Py_ssize_t dst_stride)
{
    uint32_t x, y;

    src_stride /= sizeof(*src1);
    dst_stride /= sizeof(*dst1);

    for (y=0; y < h; y++, src1 += src_stride, dst1 += dst_stride)
    {
        uint16_t *src = src1;
        uint16_t *dst = dst1;

        for (x=0; x < w; x++)
        {
            uint32_t alpha = src[0];

            if (alpha > 0)
            {
                uint32_t one_minus_alpha = (1<<15) - alpha;

                /* ARGB15X -> ARGB15X */
                dst[0] = MAX(dst[0], alpha);
                dst[1] = (one_minus_alpha * dst[1] / (1<<15) + src[1]);
                dst[2] = (one_minus_alpha * dst[2] / (1<<15) + src[2]);
                dst[3] = (one_minus_alpha * dst[3] / (1<<15) + src[3]);

            } /* else unchange the destination */

            /* Next ARGB pixel */
            src += 4;
            dst += 4;
        }
    }
}

/********* Others ***************************************/

const PA_InitValue *
get_init_values(int pixfmt)
{
    switch (pixfmt)
    {
        case PyPixbuf_PIXFMT_RGB_8:         return &gInitValues[0];
        case PyPixbuf_PIXFMT_ARGB_8:        return &gInitValues[1];
        case PyPixbuf_PIXFMT_ARGB_8_NOA:    return &gInitValues[2];
        case PyPixbuf_PIXFMT_RGBA_8:        return &gInitValues[3];
        case PyPixbuf_PIXFMT_RGBA_8_NOA:    return &gInitValues[4];
        case PyPixbuf_PIXFMT_CMYK_8:        return &gInitValues[5];
        case PyPixbuf_PIXFMT_RGBA_15X:      return &gInitValues[6];
        case PyPixbuf_PIXFMT_ARGB_15X:      return &gInitValues[7];
        case PyPixbuf_PIXFMT_CMYKA_15X:     return &gInitValues[8];

        default: return NULL;
    }
}

static blitfunc
get_blit_function(int src_fmt, int dst_fmt, int endian_care)
{
    if (src_fmt == PyPixbuf_PIXFMT_ARGB_15X)
    {
#if BYTE_ORDER == LITTLE_ENDIAN
#warning "I'm little"
        if (endian_care)
        {
            switch (dst_fmt)
            {
                case PyPixbuf_PIXFMT_ARGB_8:    return (blitfunc)argb15x_to_bgra8;
                case PyPixbuf_PIXFMT_RGBA_8:    return (blitfunc)argb15x_to_abgr8;
                case PyPixbuf_PIXFMT_RGB_8:     return (blitfunc)argb15x_to_rgb8;
            }
        }
#endif
        switch (dst_fmt)
        {
            case PyPixbuf_PIXFMT_ARGB_8:        return (blitfunc)argb15x_to_argb8;
            case PyPixbuf_PIXFMT_ARGB_8_NOA:    return (blitfunc)argb15x_to_argb8_noa;
            case PyPixbuf_PIXFMT_RGBA_8:        return (blitfunc)argb15x_to_rgba8;
            case PyPixbuf_PIXFMT_RGBA_8_NOA:    return (blitfunc)argb15x_to_rgba8_noa;
            case PyPixbuf_PIXFMT_RGB_8:         return (blitfunc)argb15x_to_rgb8;
            case PyPixbuf_PIXFMT_ARGB_15X:      return (blitfunc)rgbx15x_to_rgbx15x;
        }
    }
    else if (src_fmt == PyPixbuf_PIXFMT_RGBA_15X)
    {
        switch (dst_fmt)
        {
            case PyPixbuf_PIXFMT_RGBA_15X:      return (blitfunc)rgbx15x_to_rgbx15x;
        }
    }
    else if (src_fmt == PyPixbuf_PIXFMT_ARGB_8)
    {
#if BYTE_ORDER == LITTLE_ENDIAN
#warning "I'm little"
        if (endian_care)
        {
            switch (dst_fmt)
            {
                case PyPixbuf_PIXFMT_ARGB_15X:   return (blitfunc)bgra8_to_argb15x;
            }
        }
#endif

        switch (dst_fmt)
        {
            case PyPixbuf_PIXFMT_ARGB_15X:      return (blitfunc)argb8_to_argb15x;
            case PyPixbuf_PIXFMT_RGBA_8:        return (blitfunc)argb8_to_rgba8;
            case PyPixbuf_PIXFMT_ARGB_8_NOA:    return (blitfunc)argb8_to_argb8_noa;
            case PyPixbuf_PIXFMT_RGBA_8_NOA:    return (blitfunc)argb8_to_rgba8_noa;
        }
    }
    else if (src_fmt == PyPixbuf_PIXFMT_RGBA_8_NOA)
    {
        switch (dst_fmt)
        {
            case PyPixbuf_PIXFMT_ARGB_15X:      return (blitfunc)rgba8_noa_to_argb15x;
        }
    }
    else if (src_fmt == PyPixbuf_PIXFMT_ARGB_8_NOA)
    {
        switch (dst_fmt)
        {
            case PyPixbuf_PIXFMT_ARGB_8_NOA:    return (blitfunc)argb8_noa_to_argb8_noa;
        }
    }

    return NULL;
}

static blitfunc
get_compose_function(int src_fmt, int dst_fmt, int endian_care)
{
    if (src_fmt == PyPixbuf_PIXFMT_ARGB_15X)
    {
#if BYTE_ORDER == LITTLE_ENDIAN
#warning "I'm little"
        if (endian_care)
        {
            switch (dst_fmt)
            {

            }
        }
#endif
        switch (dst_fmt)
        {
            case PyPixbuf_PIXFMT_ARGB_15X: return (blitfunc)compose_argb15x_to_argb15x;
        }
    }
    else if (src_fmt == PyPixbuf_PIXFMT_ARGB_8)
    {
#if BYTE_ORDER == LITTLE_ENDIAN
#warning "I'm little"
        if (endian_care)
        {
            switch (dst_fmt)
            {

            }
        }
#endif

        switch (dst_fmt)
        {
            case PyPixbuf_PIXFMT_ARGB_8_NOA: return (blitfunc)compose_argb8_to_argb8_noa;
        }
    }
    else if (src_fmt == PyPixbuf_PIXFMT_ARGB_8_NOA)
    {
#if BYTE_ORDER == LITTLE_ENDIAN
#warning "I'm little"
        if (endian_care)
        {
            switch (dst_fmt)
            {

            }
        }
#endif

        switch (dst_fmt)
        {
            case PyPixbuf_PIXFMT_ARGB_8_NOA: return (blitfunc)compose_argb8_noa_to_argb8_noa;
        }
    }

    return NULL;
}

static int
clip_area(PyPixbuf *self,
          PyPixbuf *dst_pixbuf,
          int *dxoff,
          int *dyoff,
          unsigned int *sxoff,
          unsigned int *syoff,
          unsigned int *width,
          unsigned int *height)
{
    /* Clip area to the source */
    if (*sxoff >= self->width)
        return 1;
    else if ((*sxoff+*width) > self->width)
        *width = self->width - *sxoff;

    if (*syoff >= self->height)
        return 1;
    else if ((*syoff+*height) > self->height)
        *height = self->height - *syoff;

    /* Clip the write area on destination */
    if (*dxoff < 0)
    {
        if (-*dxoff >= *width)
            return 1;

        *sxoff -= *dxoff;
        *width += *dxoff;
        *dxoff = 0;

        if (*width > dst_pixbuf->width)
            *width = dst_pixbuf->width;
    }
    else if (*dxoff >= dst_pixbuf->width)
        return 1;
    else if ((*dxoff+*width) > dst_pixbuf->width)
        *width = dst_pixbuf->width - *dxoff;

    if (*dyoff < 0)
    {
        if (-*dyoff >= *height)
            return 1;

        *syoff  -= *dyoff;
        *height += *dyoff;
        *dyoff = 0;

        if (*height > dst_pixbuf->height)
            *height = dst_pixbuf->height;
    }
    else if (*dyoff >= dst_pixbuf->height)
        return 1;
    else if ((*dyoff+*height) > dst_pixbuf->height)
        *height = dst_pixbuf->height - *dyoff;

    //printf("dxoff=%d, dyoff=%d, w=%u, h=%u, sxoff=%d, syoff=%d\n", *dxoff, *dyoff, *width, *height, *sxoff, *syoff);

    return 0;
}

static inline int
get_pixel_size(int pixfmt)
{
    const PA_InitValue *pa = get_init_values(pixfmt);
    if (pa)
        return pa->bpp;
    return -1;
}

static PyPixbuf *g_cache_pb=NULL; /* cache result of last get_tile_cb() call */

static int
get_pixel_color(PyObject *get_tile_cb, const int x, const int y,
				uint16_t color[MAX_CHANNELS])
{
    PyPixbuf *tile;

    if (g_cache_pb
        && BETWEEN(x, g_cache_pb->x, g_cache_pb->x + g_cache_pb->width)
        && BETWEEN(y, g_cache_pb->y, g_cache_pb->y + g_cache_pb->height))
    {
        tile = g_cache_pb;
    }
    else
    {
		/* Note: we keep pb cache valid if next call fails */
        tile = (PyPixbuf *)PyObject_CallFunction(get_tile_cb, "iii", x, y, 0); /* NR */
        if (!tile)
            return -1;

		if ((PyObject *)tile != Py_None)
		{
			Py_XDECREF(g_cache_pb);
			g_cache_pb = tile;
		} else
			Py_CLEAR(tile);
    }

    if (tile)
    {
        void *src_data = tile->data + (y - tile->y) * tile->bpr + (x - tile->x) * tile->bpp;
        tile->readpixel(src_data, color);
    }
    else
		CLEAR(color);

    return 0;
}

/********* Sampling *************************************/

static int
pixel_sampling_direct(PyObject *get_tile_cb, const int ix, const int iy,
					  uint16_t color[MAX_CHANNELS], const float coeffs[6])
{
	const float ixf = ix + 0.5;
	const float iyf = iy + 0.5;
	const float ox = floorf(ixf * coeffs[0] + iyf * coeffs[1] + coeffs[2]);
	const float oy = floorf(ixf * coeffs[3] + iyf * coeffs[4] + coeffs[5]);
	return get_pixel_color(get_tile_cb, (int)ox, (int)oy, color);
}

static int
pixel_sampling_bilinear(PyObject *get_tile_cb, const int ix, const int iy,
						uint16_t color[MAX_CHANNELS], const float coeffs[6],
						int channels)
{
	uint16_t c0[MAX_CHANNELS];
	uint16_t c1[MAX_CHANNELS];
	uint16_t c2[MAX_CHANNELS];
	uint16_t c3[MAX_CHANNELS];

	/* Start with "pixel centered" coordinates */
	const double ixf = ix + 0.5;
	const double iyf = iy + 0.5;

	const double ox = trunc(ixf * coeffs[0] + iyf * coeffs[1] + coeffs[2]);
	const double oy = trunc(ixf * coeffs[3] + iyf * coeffs[4] + coeffs[5]);

	const int x_lo = trunc(ox);
	const int x_hi = ceil(ox);
	const int y_lo = trunc(oy);
	const int y_hi = ceil(oy);

	/* Read four pixels for interpolations */
	if (get_pixel_color(get_tile_cb, x_lo, y_lo, c0))
		return -1;

	if (get_pixel_color(get_tile_cb, x_hi, y_lo, c1))
		return -1;

	if (get_pixel_color(get_tile_cb, x_hi, y_hi, c2))
		return -1;

	if (get_pixel_color(get_tile_cb, x_lo, y_hi, c3))
		return -1;

	/* Compute interpolation factors */
	const double fx = ox - floor(ox);
	const double fy = oy - floor(oy);
	const double f0 = (1. - fx) * (1. - fy);
	const double f1 =       fx  * (1. - fy);
	const double f2 =       fx  *       fy ;
	const double f3 = (1. - fx) *       fy ;

	/* Bilinear interpolation on each channel */
	int i;
	for (i=0; i < channels; i++) {
		color[i]  = (double)c0[i] * f0;
		color[i] += (double)c1[i] * f1;
		color[i] += (double)c2[i] * f2;
		color[i] += (double)c3[i] * f3;
	}

	return 0;
}

static int
pixel_sampling_bresenham_redux(PyObject *get_tile_cb, const int ix, const int iy,
							   uint16_t color[MAX_CHANNELS], const float coeffs[4],
							   int channels)
{
	uint16_t c0[MAX_CHANNELS];
	uint16_t c1[MAX_CHANNELS];
	uint16_t c2[MAX_CHANNELS];
	uint16_t c3[MAX_CHANNELS];

	const float ox = (ix + .5f) * coeffs[0] + coeffs[2];
	const float oy = (iy + .5f) * coeffs[1] + coeffs[3];

	const int x_lo = floorf(ox);
	const int x_hi = ceilf(ox);
	const int y_lo = floorf(oy);
	const int y_hi = ceilf(oy);

	/* Read four pixels for interpolations */
	if (get_pixel_color(get_tile_cb, x_lo, y_lo, c0))
		return -1;

	if (get_pixel_color(get_tile_cb, x_hi, y_lo, c1))
		return -1;

	if (get_pixel_color(get_tile_cb, x_hi, y_hi, c2))
		return -1;

	if (get_pixel_color(get_tile_cb, x_lo, y_hi, c3))
		return -1;

	/* Compute interpolation factors */
	const double fx = ox - trunc(ox);
	const double fy = oy - trunc(oy);
	const double f0 = (1. - fx) * (1. - fy);
	const double f1 =       fx  * (1. - fy);
	const double f2 =       fx  *       fy ;
	const double f3 = (1. - fx) *       fy ;

	/* Bilinear interpolation on each channel */
	int i;
	for (i=0; i < channels; i++) {
		color[i]  = (double)c0[i] * f0;
		color[i] += (double)c1[i] * f1;
		color[i] += (double)c2[i] * f2;
		color[i] += (double)c3[i] * f3;
	}

	return 0;
}

/********* Blending *************************************/

static void
blend_fg(int count, uint16_t *dc, uint16_t *fg, uint16_t *bg)
{ memcpy(dc, fg, count * sizeof(uint16_t)); }

static void
blend_bg(int count, uint16_t *dc, uint16_t *fg, uint16_t *bg)
{ memcpy(dc, bg, count * sizeof(uint16_t)); }

/*******************************************************************************************
** PyPixbuf_Type
*/

static int
initialize_pixbuf(PyPixbuf *self, int width, int height, int pixfmt, PyPixbuf *src, void *data)
{
    const PA_InitValue *init_values = get_init_values(pixfmt);

    if ((width == 0) || (height == 0))
    {
        PyErr_SetString(PyExc_ValueError, "Null dimensions");
        return 1;
    }

    if (NULL == init_values)
    {
        PyErr_Format(PyExc_ValueError, "Invalid pixel format (0x%x)", pixfmt);
        return 1;
    }

    self->bpc = init_values->bpc;
    self->nc = init_values->nc;
	self->bpp = init_values->bpp;
    self->bpr = width * self->bpp;

	if (!data) {
		self->data_alloc = AllocVecTaskPooled((self->bpr*height)+15);
		if (!self->data_alloc)
		{
			PyErr_NoMemory();
			return 1;
		}

		/* 16-bytes alignment */
		self->data = (void*)((((unsigned long)self->data_alloc)+15) & ~15);

		if (NULL != src)
			memcpy(self->data, src->data, self->bpr * height);
	} else {
		self->data_alloc = NULL;
		self->data = data;
	}

    self->damaged = FALSE;
    self->x = self->y = 0;
    self->pixfmt = pixfmt;
    self->width = width;
    self->height = height;
    self->cfromfloat = init_values->cfromfloat;
    self->ctofloat = init_values->ctofloat;
    self->writepixel = init_values->writepixel;
    self->write2pixel = init_values->write2pixel;
    self->readpixel = init_values->readpixel;
    self->writepixel_alpha_locked = init_values->writepixel_alpha_locked;

    return 0;
}

static PyObject *
pixbuf_new(PyTypeObject *type, PyObject *args)
{
    PyPixbuf *self, *src=NULL;
    uint16_t w, h;
    int pixfmt;

    if (!PyArg_ParseTuple(args, "IHH|O!:__new__", &pixfmt, &w, &h, &PyPixbuf_Type, &src)) /* BR */
        return NULL;

    /* Is src buffer valid? */
    if ((NULL != src) && ((src->pixfmt != pixfmt) || (src->width != w) || (src->height != h)))
        return PyErr_Format(PyExc_TypeError, "Source pixbuf is not of the same type");

    self = (PyPixbuf *)type->tp_alloc(type, 0); /* NR */
    if (NULL != self)
    {
        if (initialize_pixbuf(self, w, h, pixfmt, src, NULL))
            Py_CLEAR(self);
    }

    return (PyObject *)self;
}

static void
pixbuf_dealloc(PyPixbuf *self)
{
    if (NULL != self->data_alloc) FreeVecTaskPooled(self->data_alloc);
    Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyObject *
pixbuf_get_item(PyPixbuf *self, Py_ssize_t i)
{
    Py_RETURN_NONE;
}

static int
pixbuf_compare(PyPixbuf *self, PyPixbuf *other)
{
    Py_ssize_t s1, s2;
    int r;

    if (!PyPixbuf_Check(other))
    {
        PyErr_SetString(PyExc_TypeError, "Can compare against Pixbuf object");
        return -1;
    }

    s1 = self->height*self->bpr;
    s2 = other->height*other->bpr;

    if (s1 > s2)
        return 1;

    if (s1 < s2)
        return -1;

    r = memcmp(self->data, other->data, s1);
    return r>0?1:r<0?-1:0;
}

static PyObject *
pixbuf_set_pixel(PyPixbuf *self, PyObject *args)
{
    int x, y, i;
    PyObject *py_color;
    uint8_t *pix;
    uint16_t color[4];

    if (self->nc > 4)
        Py_RETURN_NONE;

    if (!PyArg_ParseTuple(args, "IIO!", &x, &y, &PyTuple_Type, &py_color))
        return NULL;

    if (PyTuple_GET_SIZE(py_color) != self->nc)
        return PyErr_Format(PyExc_TypeError, "Color must be a %u-tuple", self->nc);

    for (i=0; i < PyTuple_GET_SIZE(py_color); i++)
    {
        PyObject *o = PyTuple_GET_ITEM(py_color, i);
        float v;

        v = PyFloat_AsDouble(o);
        if (PyErr_Occurred())
            return NULL;

        self->cfromfloat(v, &color[i]);
    }

    x = MIN(MAX(0, x), self->width-1);
    y = MIN(MAX(0, y), self->height-1);

    pix = &self->data[y*self->bpr + x*(self->bpc/8)*self->nc];
    self->writepixel(pix, 1.f, 1.f, color);

    Py_RETURN_NONE;
}

static PyObject *
pixbuf_get_pixel(PyPixbuf *self, PyObject *args)
{
    int x, y;
    PyObject *py_color;
    uint8_t *pix;
    uint16_t color[MAX_CHANNELS];

    if (!PyArg_ParseTuple(args, "ii", &x, &y))
        return NULL;

    if ((x < 0) || (y < 0) || (x >= self->width) || (y >= self->height))
    {
        PyErr_SetString(PyExc_ValueError, "Out of bound coordinates");
        return NULL;
    }

    pix = self->data + y*self->bpr + x*self->bpp;
    self->readpixel(pix, color);

    py_color = PyTuple_New(self->nc);
    if (NULL != py_color)
    {
        int i;

        for (i=0; i<self->nc; i++)
        {
            PyObject *o = PyFloat_FromDouble(self->ctofloat(&color[i])); /* NR */

            if (NULL == o)
            {
                Py_DECREF(py_color);
                return NULL;
            }

            PyTuple_SET_ITEM(py_color, i, o);
        }
    }

    return py_color;
}

static PyObject *
pixbuf_get_average_pixel(PyPixbuf *self, PyObject *args)
{
    float radius, sums[MAX_CHANNELS];
    int minx, miny, maxx, maxy, sx, sy, x, y, i;
    PyObject *py_color;
    float color[MAX_CHANNELS];

    if (!PyArg_ParseTuple(args, "fii", &radius, &sx, &sy))
        return NULL;

    if ((sx < 0) || (sy < 0) || (sx >= self->width) || (sy >= self->height))
    {
        PyErr_SetString(PyExc_ValueError, "Out of bound coordinates");
        return NULL;
    }

    radius = CLAMP(radius, 0.0, 300.);

    /* Compute dab bounding box (XXX: yratio?) */
    float rad_box = radius + .5;
    minx = floorf(sx - rad_box);
    maxx = ceilf(sx + rad_box);
    miny = floorf(sy - rad_box);
    maxy = ceilf(sy + rad_box);
    //printf("area: %u,%u -> %u,%u\n", minx, miny, maxx, maxy);

    /* Prepare some data */
    int bpp = self->bpp;
    unsigned int sum_weight = 0;
    bzero(sums, sizeof(sums));

    /* Radius derivatives */
    const float rd = 1.0 / radius;
    const float xx0 = (float)(minx - sx) + .5; /* center of pixel */
    const float yy0 = (float)(miny - sy) + .5;
    float rxy = xx0*rd;
    float ryy = yy0*rd;

    int chan_count = self->nc;
    uint8_t *buf = self->data + miny*self->bpr;

    /* Loop on all pixels inside a bbox centered on (x, y) */
    for (y=miny; y <= maxy; y++, ryy += rd, buf += self->bpr)
    {
        uint8_t *pixel = buf + minx*bpp;
        float rx = rxy;
        float ry = ryy;

        for (x=minx; x <= maxx; x++, rx += rd, pixel += bpp)
        {
            float rr = rx*rx + ry*ry;

            if (rr <= 1.0)
            {
                uint16_t tmp_color[MAX_CHANNELS];

                sum_weight++;

                /* Get color as native values (alpha always last) */
                self->readpixel(pixel, tmp_color);

                /* Convert to float, weight and add to the sum  */
                for (i=0; i<chan_count; i++)
                    sums[i] += self->ctofloat(&tmp_color[i]);
            }
        }
    }

    //printf("sums: %f %f %f %f, w=%u\n", sums[0], sums[1], sums[2], sums[3], sum_weight);

    if (!sum_weight)
        Py_RETURN_NONE;

    /* Average alpha (always the last item) */
    float alpha, alpha_sum = sums[chan_count-1];

    alpha = CLAMP(alpha_sum / sum_weight, 0.0, 1.0);
    if (alpha >= (1.0 / (1 << 15)))
    {
        /* colors are alpha-premultiplied, so un-multiply it now */
        /* FIXME: it's not always the truth! */
        for (i=0; i<chan_count-1; i++)
        {
            /* OPTIM: no need to divide color by weight sum as alpha sum is also weighted */
            color[i] = CLAMP(sums[i] / alpha_sum, 0.0, 1.0); /* fix rounding errors */
        }

        color[chan_count-1] = alpha;
        //printf("colors: %f %f %f %f\n", color[0], color[1], color[2], color[3]);
    }
    else
    {
        bzero(color, sizeof(color));
        color[0] = 1.0; /* for debugging */
    }

    py_color = PyTuple_New(self->nc);
    if (NULL != py_color)
    {
        int i;

        for (i=0; i<self->nc; i++)
        {
            PyObject *o = PyFloat_FromDouble(color[i]); /* NR */

            if (NULL == o)
            {
                Py_DECREF(py_color);
                return NULL;
            }

            PyTuple_SET_ITEM(py_color, i, o);
        }
    }

    return py_color;
}

static PyObject *
pixbuf_get_mem_size(PyPixbuf *self, void *closure)
{
    return PyLong_FromUnsignedLong(self->bpr * self->height);
}

static PyObject *
pixbuf_get_size(PyPixbuf *self, void *closure)
{
    return Py_BuildValue("II", self->width, self->height);
}

static PyObject *
pixbuf_blit(PyPixbuf *self, PyObject *args)
{
    /* NOTE: This is the most important function in Gribouillis!
     * This function is heavy called during all drawing operations.
     * So most of optimisation efforts must be here!
     */

    PyPixbuf *dst_pixbuf;
    int dxoff=0, dyoff=0;
    unsigned int sxoff=0, syoff=0;
    unsigned int width, height;
    blitfunc blit;
    int endian_care=TRUE, dst_pix_size;
    void *src_data, *dst_data;

    width = self->width;
    height = self->height;

    if (!PyArg_ParseTuple(args, "O!|iiIIIIi", &PyPixbuf_Type, &dst_pixbuf,
                          &dxoff, &dyoff, &sxoff, &syoff,
                          &width, &height, &endian_care))
        return NULL;

    blit = get_blit_function(self->pixfmt, dst_pixbuf->pixfmt, endian_care);
    if (NULL == blit)
        return PyErr_Format(PyExc_TypeError,
                            "Don't know how to blit from format 0x%08x"
                            " to format 0x%08x",
                            self->pixfmt, dst_pixbuf->pixfmt);

    if (clip_area(self, dst_pixbuf, &dxoff, &dyoff, &sxoff, &syoff, &width, &height))
        Py_RETURN_NONE;

    dst_pix_size = get_pixel_size(dst_pixbuf->pixfmt); //dst_pixbuf->bpp;
	int toto = get_pixel_size(self->pixfmt);

    src_data = self->data + syoff * self->bpr + sxoff * toto;
    if (src_data < (void *)self->data || src_data >= (void *)(self->data + self->height * self->bpr))
    {
        printf("PixBuf buf: buffer overflow on src_data, off = (%d, %d)\n", sxoff, syoff);
        Py_RETURN_NONE;
    }

    dst_data = dst_pixbuf->data + dyoff * dst_pixbuf->bpr + dxoff * dst_pix_size;
    if (dst_data < (void *)dst_pixbuf->data || dst_data >= (void *)(dst_pixbuf->data + dst_pixbuf->height * dst_pixbuf->bpr))
    {
        printf("PixBuf buf: buffer overflow on dst_data, off = (%d, %d)\n", dxoff, dyoff);
        Py_RETURN_NONE;
    }

    /* Rasterize pixels to the given buffer */
    blit(src_data, dst_data, width, height, self->bpr, dst_pixbuf->bpr);

    Py_RETURN_NONE;
}

static PyObject *
pixbuf_compose(PyPixbuf *self, PyObject *args)
{
    PyPixbuf *dst_pixbuf;
    int dxoff=0, dyoff=0;
    unsigned int sxoff=0, syoff=0;
    unsigned int width, height;
    blitfunc compose;
    int endian_care=TRUE, dst_pix_size, src_pix_size;
    void *src_data, *dst_data;

    width = self->width;
    height = self->height;

    if (!PyArg_ParseTuple(args, "O!|iiIIIIi", &PyPixbuf_Type, &dst_pixbuf, &dxoff, &dyoff, &sxoff, &syoff, &width, &height, &endian_care))
        return NULL;

    compose = get_compose_function(self->pixfmt, dst_pixbuf->pixfmt, endian_care);
    if (NULL == compose)
        return PyErr_Format(PyExc_TypeError, "Don't know how to compose from format 0x%08x to format 0x%08x",
                            self->pixfmt, dst_pixbuf->pixfmt);

    if (clip_area(self, dst_pixbuf, &dxoff, &dyoff, &sxoff, &syoff, &width, &height))
        Py_RETURN_NONE;

    dst_pix_size = dst_pixbuf->bpp;
    src_pix_size = self->bpp;

    src_data = self->data + syoff * self->bpr + sxoff * src_pix_size;
    if (src_data < (void *)self->data || src_data >= (void *)(self->data + self->height * self->bpr))
    {
        printf("PixBuf buf: buffer overflow on src_data, off = (%d, %d)\n", sxoff, syoff);
        Py_RETURN_NONE;
    }

    dst_data = dst_pixbuf->data + dyoff * dst_pixbuf->bpr + dxoff * dst_pix_size;
    if (dst_data < (void *)dst_pixbuf->data || dst_data >= (void *)(dst_pixbuf->data + dst_pixbuf->height * dst_pixbuf->bpr))
    {
        printf("PixBuf buf: buffer overflow on dst_data, off = (%d, %d)\n", dxoff, dyoff);
        Py_RETURN_NONE;
    }

    /* Rasterize pixels to the given buffer */
    compose(src_data, dst_data, width, height, self->bpr, dst_pixbuf->bpr);

    Py_RETURN_NONE;
}

static PyObject *
pixbuf_from_buffer(PyPixbuf *self, PyObject *args)
{
    Py_ssize_t size;
    int dxoff=0, dyoff=0, sxoff, syoff;
    unsigned int src_stride, src_pixfmt, sw, sh, dw, dh;
    int endian_care=TRUE, dst_pix_size, src_pix_size;
    uint8_t *src;
    blitfunc blit;

    if (!PyArg_ParseTuple(args, "Is#IiiII|i", &src_pixfmt, &src, &size, &src_stride, &sxoff, &syoff, &sw, &sh, &endian_care))
        return NULL;

    blit = get_blit_function(src_pixfmt, self->pixfmt, endian_care);
    if (NULL == blit)
        return PyErr_Format(PyExc_TypeError, "Don't know how to blit from format 0x%08x to format 0x%08x",
                            src_pixfmt, self->pixfmt);

    src_pix_size = get_pixel_size(src_pixfmt);
    if (src_pix_size <= 0)
        return PyErr_Format(PyExc_TypeError, "Don't know pixel size of format 0x%08x", src_pixfmt);

    /* compute src/dst offsets and dst size */
    dxoff = sxoff - self->x;
    if (dxoff < 0)
    { /* pixbuf at right */
        if (-dyoff >= sw)
            Py_RETURN_NONE;

        sxoff = -dxoff;
        dxoff = 0;
        dw = MIN(self->width, sw - sxoff);
    }
    else if (dxoff >= self->width)
        Py_RETURN_NONE;
    else /* pixbuf at left */
    {
        sxoff = 0;
        dw = MIN(sw, self->width - dxoff);
    }

    dyoff = syoff - self->y;
    if (dyoff < 0)
    { /* pixbuf at bottom */
        if (-dyoff >= sh)
            Py_RETURN_NONE;

        syoff = -dyoff;
        dyoff = 0;
        dh = MIN(self->height, sh - syoff);
    }
    else if (dyoff >= self->height)
        Py_RETURN_NONE;
    else /* pixbuf at top */
    {
        syoff = 0;
        dh = MIN(sh, self->height - dyoff);
    }

    dst_pix_size = self->bpp;

    /* Rasterize pixels to the given buffer */
    blit((void *)(src + syoff*src_stride + sxoff*src_pix_size),
         (void *)(self->data + dyoff*self->bpr + dxoff*dst_pix_size),
         dw, dh, src_stride, self->bpr);

    Py_RETURN_NONE;
}

static PyObject *
pixbuf_clear(PyPixbuf *self)
{
    bzero(self->data, self->bpr * self->height);
    Py_RETURN_NONE;
}

static PyObject *
pixbuf_clear_area(PyPixbuf *self, PyObject *args)
{
    int x1, y1, x2, y2, w, h;
    unsigned int y, pixel_size;
    unsigned char *ptr = self->data;

    if (!PyArg_ParseTuple(args, "iiII", &x1, &y1, &w, &h))
        return NULL;

    /* No size? */
    if (!w || !h) goto bye;

    x2 = x1+w-1;
    y2 = y1+h-1;

    /* Clipping */

    if (x1 < 0) x1 = 0;
    else if (x1 >= self->width) x1 = self->width - 1;

    if (y1 < 0) y1 = 0;
    else if (y1 >= self->height) y1 = self->height - 1;

    if (x2 < 0) x2 = 0;
    else if (x2 >= self->width) x2 = self->width - 1;

    if (y2 < 0) y2 = 0;
    else if (y2 >= self->height) y2 = self->height - 1;

    w = x2-x1+1;
    h = y2-y1+1;

    /* clear */
    pixel_size = self->bpp;
    ptr += y1*self->bpr + x1*pixel_size;
    for (y=0; y < h; y++, ptr += self->bpr)
        bzero(ptr, w*pixel_size);

bye:
    Py_RETURN_NONE;
}

static PyObject *
pixbuf_clear_white(PyPixbuf *self, PyObject *args)
{
    unsigned int y, x;
    void *pix = self->data;
    int pixoff = (self->bpc * self->nc) / 8;
    static uint16_t white[] = {0x7fff, 0x7fff, 0x7fff};

    for (y=0; y < self->height; y++)
    {
        for (x=0; x < self->width; x++)
        {
            self->writepixel(pix, 1.0, 1.0, white);
            pix += pixoff;
        }
    }

    Py_RETURN_NONE;
}

static PyObject *
pixbuf_clear_value(PyPixbuf *self, PyObject *args)
{
    unsigned int i, y, x;
    void *pix = self->data;
    int pixoff = (self->bpc * self->nc) / 8;
    float value;
    static uint16_t color[MAX_CHANNELS];

    if (!PyArg_ParseTuple(args, "f", &value))
        return NULL;

    value = CLAMP(value, 0., 1.);
    for (i=0; i < self->nc; i++)
        self->cfromfloat(value, &color[i]);

    for (y=0; y < self->height; y++)
    {
        for (x=0; x < self->width; x++)
        {
            self->writepixel(pix, 1.0, 1.0, color);
            pix += pixoff;
        }
    }

    Py_RETURN_NONE;
}

static PyObject *
pixbuf_clear_alpha(PyPixbuf *self, PyObject *args)
{
    unsigned int y, x;
    void *pix = self->data;
    int pixoff = (self->bpc * self->nc) / 8;
    float value;
    static uint16_t color[MAX_CHANNELS] = {0};

    if (!PyArg_ParseTuple(args, "f", &value))
        return NULL;

    for (y=0; y < self->height; y++)
    {
        for (x=0; x < self->width; x++)
        {
            self->writepixel(pix, 1.0, value, color);
            pix += pixoff;
        }
    }

    Py_RETURN_NONE;
}

static PyObject *
pixbuf_empty(PyPixbuf *self, PyObject *args)
{
    unsigned int y, x;
    void *pix = self->data;
    int na, pixsize = (self->bpc * self->nc) / 8;
    uint16_t color[MAX_CHANNELS];

    /* No alpha? => non sense here */
    if (!(self->pixfmt & PyPixbuf_FLAG_HAS_ALPHA))
        Py_RETURN_FALSE;

    na = self->nc-1;
    for (y=0; y < self->height; y++)
    {
        for (x=0; x < self->width; x++, pix += pixsize)
        {
            self->readpixel(pix, color);

            /* not full transparent? */
            if (color[na])
                Py_RETURN_FALSE;
        }
    }

    Py_RETURN_TRUE;
}

static Py_ssize_t
pixbuf_getsegcount(PyPixbuf *self, Py_ssize_t *lenp)
{
    if (NULL != lenp)
        *lenp = self->bpr * self->height;
    return 1;
}

static Py_ssize_t
pixbuf_getbuffer(PyPixbuf *self, Py_ssize_t segment, void **ptrptr)
{
    if (segment != 0)
    {
        PyErr_SetString(PyExc_TypeError, "Only segment 0 is allowed");
        return -1;
    }

    *ptrptr = self->data;
    return self->bpr * self->height;
}

static PyObject *
pixbuf_scroll(PyPixbuf *self, PyObject *args)
{
    int dx, dy;
    unsigned int pixel_size, size;
    register int y;
    register uint8_t *ptr_src = self->data;
    register uint8_t *ptr_dst = self->data;

    if (!PyArg_ParseTuple(args, "ii", &dx, &dy))
        return NULL;

    /* No size? */
    if (!dx && !dy)
        Py_RETURN_NONE;

    /* Clipping */
    if ((dx >= self->width) || (-dx >= self->width))
        return pixbuf_clear(self);

    if ((dy >= self->height) || (-dy >= self->height))
        return pixbuf_clear(self);

    pixel_size = self->bpp;

    if (dx >= 0)
    {
        ptr_dst += dx * pixel_size;
    }
    else
    {
        dx = -dx;
        ptr_src += dx * pixel_size;
    }

    size = pixel_size*(self->width - dx);

    Forbid();
    if (dy > 0)
    {
        y = self->height - 1;
        ptr_src += (y-dy)*self->bpr;
        ptr_dst += y*self->bpr;

        for (; y >= dy; y--, ptr_src -= self->bpr, ptr_dst -= self->bpr)
            memcpy(ptr_dst, ptr_src, size);
    }
    else if (dy < 0)
    {
        y = -dy;
        ptr_src += y*self->bpr;

        for (; y < self->height; y++, ptr_src += self->bpr, ptr_dst += self->bpr)
            memcpy(ptr_dst, ptr_src, size);
    }
    else
    {
        for (y = 0; y < self->height; y++, ptr_src += self->bpr, ptr_dst += self->bpr)
            memmove(ptr_dst, ptr_src, size);
    }
    Permit();

    Py_RETURN_NONE;
}

static PyObject *
pixbuf_slow_transform_affine(PyPixbuf *self, PyObject *args)
{
	PyObject *ret = NULL;
    float coeffs[6]; /* Affine matrix coefficients */
    PyObject *get_tile_cb; /* Python callable that gives the pixbuf container object of a given point */
    PyPixbuf *pb_dst; /* pixbuf destination */
    unsigned char ss=PB_SS_NONE; /* sub-sampling pixels? */
    void *dst_row_ptr;
	int ix, iy;

    if (!PyArg_ParseTuple(args, "OO!(ffffff)|B", &get_tile_cb, &PyPixbuf_Type,
						  &pb_dst, &coeffs[0], &coeffs[3], &coeffs[1],
						  &coeffs[4], &coeffs[2], &coeffs[5], &ss))
        return NULL;

    dst_row_ptr = pb_dst->data;

    /* destination row-col scanline */
    for (iy=pb_dst->y; iy < (pb_dst->y + pb_dst->height); iy++, dst_row_ptr += pb_dst->bpr)
    {
        char *dst_data = dst_row_ptr;

        for (ix=pb_dst->x; ix < (pb_dst->x + pb_dst->width); ix++, dst_data += pb_dst->bpp)
        {
            uint16_t color[MAX_CHANNELS];

			switch (ss)
			{
			case PB_SS_NONE:
				if (pixel_sampling_direct(get_tile_cb, ix, iy, color, coeffs))
					goto clear_cache;
				break;
            case PB_SS_BILINEAR:
				if (pixel_sampling_bilinear(get_tile_cb, ix, iy, color, coeffs,
											pb_dst->nc))
					goto clear_cache;
			default:
				PyErr_Format(PyExc_ValueError, "unknown sampling value %u", ss);
				goto clear_cache;
			}

            pb_dst->write2pixel(dst_data, color);
        }
    }

	ret = Py_None;
	Py_INCREF(ret);

clear_cache:
	Py_CLEAR(g_cache_pb);
	return ret;
}

static PyObject *
pixbuf_blend(PyPixbuf *self, PyObject *args)
{
	PyObject *get_tile_cb;
	float coeffs[4];
	float opacity;
    unsigned int subsampling, mipmap_level=0;

    if (!PyArg_ParseTuple(args, "OIfffff|I", &get_tile_cb, &subsampling, &opacity,
						  &coeffs[0], &coeffs[1], &coeffs[2], &coeffs[3], &mipmap_level))
        return NULL;

	assert(self->pixfmt == pb_fg->pixfmt);

	const blendfunc blendfunc = blend_fg;
	const int n_chan = self->nc;
	void *dst_row_ptr = self->data;
	uint16_t fg_color[MAX_CHANNELS];
	uint16_t dst_color[MAX_CHANNELS];
	uint32_t iopa = opacity * (1<<15);

	const int x_max = self->x + self->width;
	const int y_max = self->y + self->height;

    /* row-col scanline on self (i.e. destination) */
	if (subsampling == PB_SS_NONE)
	{
		const float ox0 = (self->x + .5f) * coeffs[0] + coeffs[2];
		const float oy0 = (self->y + .5f) * coeffs[1] + coeffs[3];
		const float dox = coeffs[0];
		const float doy = coeffs[1];

		float oy = oy0;
		int iy = self->y;

		while (iy < y_max)
		{
			const int ioy = floorf(oy);
			char *dst_data = dst_row_ptr;
			float ox = ox0;
			int ix = self->x;

			while (ix < x_max)
			{
				int iox = floorf(ox);

				PyPixbuf *src_pb = (PyPixbuf *)PyObject_CallFunction(get_tile_cb, "iii", iox, ioy, 0); /* NR */
				if (!src_pb)
					return NULL;

				if ((PyObject *)src_pb != Py_None)
				{
					const int iox_max = src_pb->x + src_pb->width;
					void *src_data = src_pb->data + (ioy - src_pb->y) * src_pb->bpr - src_pb->x * src_pb->bpp;

					while (ix < x_max && iox < iox_max)
					{
						src_pb->readpixel(src_data + iox * src_pb->bpp, fg_color);

						/* fully transparent? */
						if (fg_color[3]) {
							self->readpixel(dst_data, dst_color);

							//blendfunc(n_chan, dst_color, fg_color, dst_color);
							const uint32_t fg_a = (fg_color[3] * iopa) / (1<<15);
							const uint32_t fg_a_1 = (1<<15) - fg_a;
							dst_color[0] = ((uint32_t)dst_color[0] * fg_a_1) / (1<<15) + fg_color[0];
							dst_color[1] = ((uint32_t)dst_color[1] * fg_a_1) / (1<<15) + fg_color[1];
							dst_color[2] = ((uint32_t)dst_color[2] * fg_a_1) / (1<<15) + fg_color[2];
							dst_color[3] = ((uint32_t)dst_color[3] * fg_a_1) / (1<<15) + fg_a;

							self->write2pixel(dst_data, dst_color);
						}

						dst_data += self->bpp;
						ix++;
						ox += dox;
						iox = floorf(ox);
					}
				}
				else
				{
					dst_data += self->bpp;
					ix++;
					ox += dox;
				}

				Py_DECREF(src_pb);
			}

			dst_row_ptr += self->bpr;
			iy++;
			oy += doy;
		}
	}
	else if (subsampling == PB_SS_BRESENHAM)
	{
		int iy;
		for (iy=self->y; iy < self->y + self->height; iy++)
		{
			char *dst_data = dst_row_ptr;

			int ix;
			for (ix=self->x; ix < self->x + self->width; ix++)
			{
				self->readpixel(dst_data, dst_color);

				if (pixel_sampling_bresenham_redux(get_tile_cb, ix, iy, fg_color,
												   coeffs, n_chan))
					goto clear_cache;

				//blendfunc(n_chan, dst_color, fg_color, dst_color);
				const uint32_t fg_a = (fg_color[3] * iopa) / (1<<15);
				const uint32_t fg_a_1 = (1<<15) - fg_a;
				dst_color[0] = ((uint32_t)dst_color[0] * fg_a_1) / (1<<15) + fg_color[0];
				dst_color[1] = ((uint32_t)dst_color[1] * fg_a_1) / (1<<15) + fg_color[1];
				dst_color[2] = ((uint32_t)dst_color[2] * fg_a_1) / (1<<15) + fg_color[2];
				dst_color[3] = ((uint32_t)dst_color[3] * fg_a_1) / (1<<15) + fg_a;

				// for debug
				//dst_color[0] = ((uint32_t)dst_color[0] * (1<<14)) / (1<<15) + (1<<15);
				//dst_color[1] = ((uint32_t)dst_color[1] * (1<<14)) / (1<<15);
				//dst_color[2] = ((uint32_t)dst_color[2] * (1<<14)) / (1<<15);
				//dst_color[3] = ((uint32_t)dst_color[3] * (1<<14)) / (1<<15) + (1<<14);

				self->write2pixel(dst_data, dst_color);

				dst_data += self->bpp;
			}

			dst_row_ptr += self->bpr;
		}
	}
	else
	{
		PyErr_Format(PyExc_ValueError, "unknown sampling value %u",
					 subsampling);
		goto clear_cache;
	}

clear_cache:
	Py_CLEAR(g_cache_pb);
	Py_RETURN_NONE;
}

static struct PyMethodDef pixbuf_methods[] = {
    {"set_pixel", (PyCFunction)pixbuf_set_pixel, METH_VARARGS, NULL},
    {"get_pixel", (PyCFunction)pixbuf_get_pixel, METH_VARARGS, NULL},
    {"get_average_pixel", (PyCFunction)pixbuf_get_average_pixel, METH_VARARGS, NULL},
    {"blit", (PyCFunction)pixbuf_blit, METH_VARARGS, NULL},
    {"compose", (PyCFunction)pixbuf_compose, METH_VARARGS, NULL},
    {"from_buffer", (PyCFunction)pixbuf_from_buffer, METH_VARARGS, NULL},
    {"clear", (PyCFunction)pixbuf_clear, METH_NOARGS, NULL},
    {"clear_area", (PyCFunction)pixbuf_clear_area, METH_VARARGS, NULL},
    {"clear_white", (PyCFunction)pixbuf_clear_white, METH_NOARGS, NULL},
    {"clear_value", (PyCFunction)pixbuf_clear_value, METH_VARARGS, NULL},
    {"clear_alpha", (PyCFunction)pixbuf_clear_alpha, METH_VARARGS, NULL},
    {"empty", (PyCFunction)pixbuf_empty, METH_NOARGS, NULL},
    {"scroll", (PyCFunction)pixbuf_scroll, METH_VARARGS, NULL},
    {"slow_transform_affine", (PyCFunction)pixbuf_slow_transform_affine, METH_VARARGS, NULL},
    {"blend", (PyCFunction)pixbuf_blend, METH_VARARGS, NULL},

    {NULL} /* sentinel */
};

static PyMemberDef pixbuf_members[] = {
    {"x", T_INT, offsetof(PyPixbuf, x), 0, NULL},
    {"y", T_INT, offsetof(PyPixbuf, y), 0, NULL},
    {"width", T_INT, offsetof(PyPixbuf, width), RO, NULL},
    {"height", T_INT, offsetof(PyPixbuf, height), RO, NULL},
    {"pixfmt", T_UINT, offsetof(PyPixbuf, pixfmt), RO, NULL},
    {"stride", T_UINT, offsetof(PyPixbuf, bpr), RO, NULL},
    {"ro", T_BYTE, offsetof(PyPixbuf, readonly), 0, NULL},
    {"damaged", T_BOOL, offsetof(PyPixbuf, damaged), 0, NULL},

    {NULL}
};

static PyGetSetDef pixbuf_getseters[] = {
    {"memsize", (getter)pixbuf_get_mem_size, NULL, "Memory occupied by pixels data", (void *)0},
    {"size", (getter)pixbuf_get_size, NULL, "Buffer size (width, height)", (void *)0},
    {NULL} /* sentinel */
};

static PyBufferProcs pixbuf_as_buffer = {
    bf_getreadbuffer  : (readbufferproc)pixbuf_getbuffer,
    bf_getwritebuffer : (writebufferproc)pixbuf_getbuffer,
    bf_getsegcount    : (segcountproc)pixbuf_getsegcount,
};

static PyNumberMethods pixbuf_as_number = {
    //nb_nonzero : (inquiry)pixbuf_nonzero,
};

static PySequenceMethods pixbuf_as_sequence = {
    sq_item: (ssizeargfunc)pixbuf_get_item,
};

static PyTypeObject PyPixbuf_Type = {
    PyObject_HEAD_INIT(NULL)

    tp_name         : "model.Pixbuf",
    tp_basicsize    : sizeof(PyPixbuf),
    tp_flags        : Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    tp_doc          : "Pixbuf Objects",

    tp_new          : (newfunc)pixbuf_new,
    tp_dealloc      : (destructor)pixbuf_dealloc,
    tp_compare      : (cmpfunc)pixbuf_compare,
    tp_methods      : pixbuf_methods,
    tp_members      : pixbuf_members,
    tp_getset       : pixbuf_getseters,
    tp_as_buffer    : &pixbuf_as_buffer,
    tp_as_number    : &pixbuf_as_number,
    tp_as_sequence  : &pixbuf_as_sequence,
};

/*******************************************************************************************
** Module
*/

static PyObject *
module_format_from_colorspace(PyObject *self, PyObject *args)
{
    unsigned int cs, flags=0;

    if (!PyArg_ParseTuple(args, "I|I", &cs, &flags))
        return NULL;

    cs &= PyPixbuf_FLAG_RGB | PyPixbuf_FLAG_CMYK;
    flags &= PyPixbuf_FLAG_15X
        |PyPixbuf_FLAG_8
        |PyPixbuf_FLAG_ALPHA_FIRST
        |PyPixbuf_FLAG_ALPHA_LAST;

    return PyLong_FromUnsignedLong(cs | flags);
}

#ifdef HAVE_GDK
static PyObject *
module_pixbuf_from_gdk_pixbuf(PyObject *self, PyObject *args)
{
	PyPixbuf *pb;
	PyGObject *pygdk_pixbuf;
	GdkPixbuf *_gdk_pixbuf;
	int pixfmt;

    if (!PyArg_ParseTuple(args, "OI", &pygdk_pixbuf, &pixfmt))
        return NULL;

	_gdk_pixbuf = (GdkPixbuf *)pygobject_get(pygdk_pixbuf);

	pb = (PyPixbuf*)PyObject_New(PyPixbuf, &PyPixbuf_Type); /* NR */
	if (pb && initialize_pixbuf(pb, gdk_pixbuf_get_width(_gdk_pixbuf),
								gdk_pixbuf_get_height(_gdk_pixbuf),
								pixfmt, NULL,
								gdk_pixbuf_get_pixels(_gdk_pixbuf)))
		Py_CLEAR(pb);

    return (PyObject *)pb;
}
#endif

static PyMethodDef methods[] = {
    {"format_from_colorspace", (PyCFunction)module_format_from_colorspace, METH_VARARGS, NULL},
#ifdef HAVE_GDK
    {"pixbuf_from_gdk_pixbuf", (PyCFunction)module_pixbuf_from_gdk_pixbuf, METH_VARARGS, NULL},
#endif
	{NULL} /* sentinel */
};

static int add_constants(PyObject *m)
{
    INSI(m, "FLAG_RGB", PyPixbuf_FLAG_RGB);
    INSI(m, "FLAG_CMYK", PyPixbuf_FLAG_CMYK);
    INSI(m, "FLAG_15X", PyPixbuf_FLAG_15X);
    INSI(m, "FLAG_8", PyPixbuf_FLAG_8);
    INSI(m, "FLAG_ALPHA_FIRST", PyPixbuf_FLAG_ALPHA_FIRST);
    INSI(m, "FLAG_ALPHA_LAST", PyPixbuf_FLAG_ALPHA_LAST);
    INSI(m, "FORMAT_RGB8", PyPixbuf_PIXFMT_RGB_8);
    INSI(m, "FORMAT_RGBA8", PyPixbuf_PIXFMT_RGBA_8);
    INSI(m, "FORMAT_ARGB8", PyPixbuf_PIXFMT_ARGB_8);
    INSI(m, "FORMAT_ARGB8_NOA", PyPixbuf_PIXFMT_ARGB_8_NOA);
    INSI(m, "FORMAT_RGBA8_NOA", PyPixbuf_PIXFMT_RGBA_8_NOA);
    INSI(m, "FORMAT_ARGB15X", PyPixbuf_PIXFMT_ARGB_15X);
    INSI(m, "FORMAT_RGBA15X", PyPixbuf_PIXFMT_RGBA_15X);
	INSI(m, "SAMPLING_NONE", PB_SS_NONE);
	INSI(m, "SAMPLING_BILINEAR", PB_SS_BILINEAR);
	INSI(m, "SAMPLING_BRESENHAM", PB_SS_BRESENHAM);

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

    if (PyType_Ready(&PyPixbuf_Type) < 0) return NULL;

    m = PyModule_Create(&module);
    if (NULL == m) return NULL;

    add_constants(m);
    ADD_TYPE(m, "Pixbuf", &PyPixbuf_Type);

	return m;
}
