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

#define _PIXBUF_CORE

#include "common.h"
#include "_pixbufmodule.h"

#ifdef WITH_ALTIVEC
#include "altivec.h"
#endif

#ifndef INITFUNC
#define INITFUNC init_pixbuf
#endif

#ifndef MODNAME
#define MODNAME "_pixbuf"
#endif

typedef struct PA_InitValue
{
    uint8_t        nc;
    uint8_t        bpc;
    colfloat2natif cfromfloat;
    colnatif2float ctofloat;
    writefunc      writepixel;
    write2func     write2pixel;
    readfunc       readpixel;
} PA_InitValue;

typedef void (*blitfunc)(void* src, void *dst,
                         uint32_t width, uint32_t height,
                         Py_ssize_t src_stride, Py_ssize_t dst_stride);

static void rgb8_writepixel(void *, float, float, unsigned short *);
static void argb8_writepixel(void *, float, float, uint16_t *);
static void rgba8_writepixel(void *, float, float, uint16_t *);
static void argb8noa_writepixel(void *, float, float, uint16_t *);
static void rgba8noa_writepixel(void *, float, float, uint16_t *);
static void rgba15x_writepixel(void *, float, float, uint16_t *);
static void argb15x_writepixel(void *, float, float, uint16_t *);
static void cmyk8_writepixel(void *, float, float, uint16_t *);
static void cmyka15x_writepixel(void *, float, float, uint16_t *);

static void dummy_write2pixel(void *data, uint16_t *color);
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
    {/*PyPixBuf_PIXFMT_RGB_8,*/      3, 8,  rgb8_fromfloat,    rgb8_tofloat,    rgb8_writepixel,     dummy_write2pixel, dummy_readpixel},
    {/*PyPixBuf_PIXFMT_ARGB_8,*/     4, 8,  rgb8_fromfloat,    rgb8_tofloat,    argb8_writepixel,    dummy_write2pixel, argb8_readpixel},
    {/*PyPixBuf_PIXFMT_ARGB_8_NOA,*/ 4, 8,  rgb8_fromfloat,    rgb8_tofloat,    argb8noa_writepixel, dummy_write2pixel, dummy_readpixel},
    {/*PyPixBuf_PIXFMT_RGBA_8,*/     4, 8,  rgb8_fromfloat,    rgb8_tofloat,    rgba8_writepixel,    dummy_write2pixel, rgba8_readpixel},
    {/*PyPixbuf_PIXFMT_RGBA_8_NOA,*/ 4, 8,  rgb8_fromfloat,    rgb8_tofloat,    rgba8noa_writepixel, dummy_write2pixel, dummy_readpixel},
    {/*PyPixBuf_PIXFMT_CMYK_8,*/     4, 8,  rgb8_fromfloat,    rgb8_tofloat,    cmyk8_writepixel,    dummy_write2pixel, dummy_readpixel},
    {/*PyPixBuf_PIXFMT_RGBA_15X,*/   4, 16, rgba15x_fromfloat, rgba15x_tofloat, rgba15x_writepixel,  dummy_write2pixel, rgba15x_readpixel},
    {/*PyPixBuf_PIXFMT_ARGB_15X,*/   4, 16, rgba15x_fromfloat, rgba15x_tofloat, argb15x_writepixel,  argb15x_write2pixel, argb15x_readpixel},
    {/*PyPixBuf_PIXFMT_CMYKA_15X,*/  5, 16, rgba15x_fromfloat, rgba15x_tofloat, cmyka15x_writepixel, dummy_write2pixel, dummy_readpixel},

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

    /* Adding delta to round values */
    alpha = (uint32_t)((opacity * erase + delta) * 255);
    one_minus_alpha = 255 - (uint32_t)((opacity + delta) * 255);

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

    /* Adding delta to round values */
    alpha = (uint32_t)((opacity * erase + delta) * 255);
    one_minus_alpha = 255 - (uint32_t)((opacity + delta) * 255);

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

    /* Adding delta to round values */
    alpha = (uint32_t)((opacity * erase + delta) * 255);
    one_minus_alpha = 255 - (uint32_t)((opacity + delta) * 255);

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

    /* Adding delta to round values */
    alpha = (uint32_t)((opacity * erase + delta) * 255);
    one_minus_alpha = 255 - (uint32_t)((opacity + delta) * 255);

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

    /* Adding delta to round values */
    alpha = (uint32_t)((opacity * erase + delta) * 255);
    one_minus_alpha = 255 - (uint32_t)((opacity + delta) * 255);

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

    /* Adding delta to round values */
    alpha = (uint32_t)((opacity * erase + delta) * 255);
    one_minus_alpha = 255 - (uint32_t)((opacity + delta) * 255);

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
    
    /* Adding delta to round values */
    alpha = (uint32_t)((opacity * erase + delta) * (1<<15));
    one_minus_alpha = (1<<15) - (uint32_t)((opacity + delta) * (1<<15));
    
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
    erase += delta;
    
    /* Adding delta to round values */
    alpha = (uint32_t)(opacity * erase * (1<<15));
    one_minus_alpha = (1<<15) - (uint32_t)(opacity * (1<<15));

    /* A */ pixel[0] =  alpha          + one_minus_alpha*pixel[0]  / (1<<15);
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
    
    /* Adding delta to round values */
    alpha = (uint32_t)((opacity * erase + delta) * (1<<15));
    one_minus_alpha = (1<<15) - (uint32_t)((opacity + delta) * (1<<15));

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

//+ rgb8_fromfloat
static void
rgb8_fromfloat(float from, void *to)
{
    *((uint16_t *)to) = (uint8_t)(from * 255);
}
//-
//+ rgba15x_fromfloat
static void
rgba15x_fromfloat(float from, void *to)
{
    *((uint16_t *)to) = (uint16_t)(from * (1<<15));
}
//-

//+ rgb8_tofloat
static float
rgb8_tofloat(void *from)
{
    /* We expect no round errors causing float > 1.0 */
    return ((float)*(uint16_t *)from) / 255;
}
//-
//+ rgba15x_tofloat
static float
rgba15x_tofloat(void *from)
{
    return (float)(*(uint16_t *)from) / (1<<15);
}
//-

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
            uint8_t r,g,b;

            /* Convert to range [0, 255], keep values alpha pre-multiplied */
            r = ((uint32_t)src[1] * 255) >> 15;
            g = ((uint32_t)src[2] * 255) >> 15;
            b = ((uint32_t)src[3] * 255) >> 15;

            /* ARGB8 */
            dst[0] = (alpha * 255) >> 15;
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
                uint8_t r,g,b;

                /* Un-multiply by alpha, rounding and convert to range [0, 255] */
                r = ((((uint32_t)src[1]<<15) + alpha/2) / alpha * 255) >> 15;
                g = ((((uint32_t)src[2]<<15) + alpha/2) / alpha * 255) >> 15;
                b = ((((uint32_t)src[3]<<15) + alpha/2) / alpha * 255) >> 15;

                /* ARGB8 */
                dst[0] = (alpha * 255) >> 15;
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
            uint32_t alpha = src[0];

            if (alpha > 0)
            {
                uint8_t r,g,b;

                /* Convert to range [0, 255], keep values alpha pre-multiplied */
                r = ((uint32_t)src[1] * 255) >> 15;
                g = ((uint32_t)src[2] * 255) >> 15;
                b = ((uint32_t)src[3] * 255) >> 15;

                /* BGRA8 */
                dst[0] = b;
                dst[1] = g;
                dst[2] = r;
                dst[3] = (alpha * 255) >> 15;
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
                uint8_t r,g,b;

                /* Convert to range [0, 255], keep values alpha pre-multiplied */
                r = ((uint32_t)src[1] * 255) >> 15;
                g = ((uint32_t)src[2] * 255) >> 15;
                b = ((uint32_t)src[3] * 255) >> 15;

                /* RGBA8 */
                dst[0] = r;
                dst[1] = g;
                dst[2] = b;
                dst[3] = (alpha * 255) >> 15;
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

                /* Un-multiply by alpha, rounding and convert to range [0, 255] */
                r = ((((uint32_t)src[1]<<15) + alpha/2) / alpha * 255) >> 15;
                g = ((((uint32_t)src[2]<<15) + alpha/2) / alpha * 255) >> 15;
                b = ((((uint32_t)src[3]<<15) + alpha/2) / alpha * 255) >> 15;

                /* RGBA8_NOA */
                dst[0] = r;
                dst[1] = g;
                dst[2] = b;
                dst[3] = (alpha * 255) >> 15;
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
                r = ((uint32_t)src[1] * 255) >> 15;
                g = ((uint32_t)src[2] * 255) >> 15;
                b = ((uint32_t)src[3] * 255) >> 15;

                /* ABGR8 */
                dst[0] = (alpha * 255) >> 15;
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
                r = ((((uint32_t)src[1]<<15) + alpha/2) / alpha * 255) >> 15;
                g = ((((uint32_t)src[2]<<15) + alpha/2) / alpha * 255) >> 15;
                b = ((((uint32_t)src[3]<<15) + alpha/2) / alpha * 255) >> 15;

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
            uint32_t alpha = ((uint32_t)src[3] << 15) / 255;

            if (alpha > 0)
            {
                uint16_t r,g,b;

                /* Convert to 15-bits value, pre-mul values by alpha */
                r = (uint32_t)src[0] * alpha / 255;
                g = (uint32_t)src[1] * alpha / 255;
                b = (uint32_t)src[2] * alpha / 255;

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
                dst[1] = (one_minus_alpha * dst[1] + r) / 255;
                dst[2] = (one_minus_alpha * dst[2] + g) / 255;
                dst[3] = (one_minus_alpha * dst[3] + b) / 255;
                
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

    return NULL;
}

static int
get_pixel_size(int pixfmt)
{
    const PA_InitValue *pa = get_init_values(pixfmt);

    if (NULL != pa)
        return (pa->nc*pa->bpc + 7)/8;
    return -1;
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

static PyPixbuf *g_last;
static int
_get_color(PyObject *get_tile_cb, int x, int y, int pix_size, uint16_t *color)
{
    PyPixbuf *tile;
    
    if (g_last &&
        (x >= g_last->x) && (x < (g_last->x + g_last->width)) &&
        (y >= g_last->y) && (y < (g_last->y + g_last->height)))
    {
        tile = g_last;
    }
    else
    {
        tile = (PyPixbuf *)PyObject_CallFunction(get_tile_cb, "iii", x, y, 0); /* NR */
        if (tile == NULL)
            return 1;
            
        Py_DECREF(tile); /* the owner dict keep refcount > 0, so we don't track it here */
    }
        
    if ((PyObject *)tile != Py_None)
    {
        void *src_data = tile->data + (y - tile->y) * tile->bpr + (x - tile->x) * pix_size;
        tile->readpixel(src_data, color);
        g_last = tile;
    }
    else
        bzero(color, sizeof(uint16_t) * MAX_CHANNELS);
        
    //Py_DECREF(tile); /* the owner dict keep refcount > 0, so we don't track it here */
    return 0;
}

/*******************************************************************************************
** PyPixbuf_Type
*/

static int
initialize_pixbuf(PyPixbuf *self, int width, int height, int pixfmt, PyPixbuf *src)
{
    const PA_InitValue *init_values = get_init_values(pixfmt);

    if (NULL == init_values)
    {
        PyErr_Format(PyExc_ValueError, "Invalid pixel format (0x%x)", pixfmt);
        return 0;
    }

    self->bpc = init_values->bpc;
    self->nc = init_values->nc;
    self->bpr = width * ((self->bpc * self->nc) >> 3);

    self->data_alloc = AllocVecTaskPooled((self->bpr*height)+15);
    if (NULL != self->data_alloc)
    {
        self->data = (void*)((((unsigned long)self->data_alloc)+15) & ~15);
        if (NULL != src)
            memcpy(self->data, src->data, self->bpr * height);

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

        return 1;
    }
    else
        PyErr_NoMemory();

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

    if ((NULL != src) && ((src->pixfmt != pixfmt) || (src->width != w) || (src->height != h)))
        return PyErr_Format(PyExc_TypeError, "Source pixbuf is not of the same type");

    self = (PyPixbuf *)type->tp_alloc(type, 0); /* NR */
    if (NULL != self)
    {
        if (!initialize_pixbuf(self, w, h, pixfmt, src))
            Py_CLEAR(self);
    }

    return (PyObject *)self;
}

static void
pixbuf_dealloc(PyPixbuf *self)
{
    if (NULL != self->data_alloc) FreeVecTaskPooled(self->data_alloc);
    self->ob_type->tp_free((PyObject *)self);
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

    pix = self->data + y*self->bpr + x*get_pixel_size(self->pixfmt);
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
    int bpp = get_pixel_size(self->pixfmt);
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
    PyPixbuf *dst_pixbuf;
    int dxoff=0, dyoff=0;
    unsigned int sxoff=0, syoff=0;
    unsigned int width, height;
    blitfunc blit;
    int endian_care=TRUE, dst_pix_size, src_pix_size;
    void *src_data, *dst_data;

    width = self->width;
    height = self->height;

    if (!PyArg_ParseTuple(args, "O!|iiIIIIi", &PyPixbuf_Type, &dst_pixbuf, &dxoff, &dyoff, &sxoff, &syoff, &width, &height, &endian_care))
        return NULL;

    blit = get_blit_function(self->pixfmt, dst_pixbuf->pixfmt, endian_care);
    if (NULL == blit)
        return PyErr_Format(PyExc_TypeError, "Don't know how to blit from format 0x%08x to format 0x%08x",
                            self->pixfmt, dst_pixbuf->pixfmt);

    if (clip_area(self, dst_pixbuf, &dxoff, &dyoff, &sxoff, &syoff, &width, &height))
        Py_RETURN_NONE;

    dst_pix_size = get_pixel_size(dst_pixbuf->pixfmt);
    src_pix_size = get_pixel_size(self->pixfmt);
    
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
        
    dst_pix_size = get_pixel_size(dst_pixbuf->pixfmt);
    src_pix_size = get_pixel_size(self->pixfmt);
    
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
        
    dst_pix_size = get_pixel_size(self->pixfmt);

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
    pixel_size = get_pixel_size(self->pixfmt);
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
    int dx, dy, x, y;
    unsigned int pixel_size;
    uint8_t *ptr_src = self->data;
    uint8_t *ptr_dst = self->data;
    
    if (!PyArg_ParseTuple(args, "ii", &dx, &dy))
        return NULL;

    /* No size? */
    if (!dx || !dy)
        Py_RETURN_NONE;
    
    /* Clipping */
    if ((dx >= self->width) || (-dx >= self->width))
        return pixbuf_clear(self);
        
    if ((dy >= self->height) || (-dy >= self->height))
        return pixbuf_clear(self);

    pixel_size = get_pixel_size(self->pixfmt);
        
    if (dy > 0)
    {
        y = self->height - 1;
        
        if (dx > 0)
        {
            x = self->width - 1;
            ptr_src += y*self->bpr + x*pixel_size;
            ptr_dst += (y-dy)*self->bpr + (x-dx)*pixel_size;
            
            for (; y; y--, ptr_src -= self->bpr, ptr_dst -= self->bpr)
            {
                uint8_t *src = ptr_src;
                uint8_t *dst = ptr_dst;
                
                for (; x; x--, src -= pixel_size, dst -= pixel_size);
                    memcpy(src, dst, pixel_size);
            }
        }
        else
        {
            x = -dx;
            ptr_src += y*self->bpr + x*pixel_size;
            ptr_dst += (y-dy)*self->bpr;
            
            for (; y; y--, ptr_src -= self->bpr, ptr_dst -= self->bpr)
            {
                uint8_t *src = ptr_src;
                uint8_t *dst = ptr_dst;
                
                for (; x < self->width; x++, src += pixel_size, dst += pixel_size);
                    memcpy(dst, src, pixel_size);
            }
        }
    }
    else
    {
        y = -dy;
        
        if (dx > 0)
        {
            x = self->width - 1;
            ptr_src += y*self->bpr + x*pixel_size;
            ptr_dst += (x-dx)*pixel_size;
            
            for (; y < self->height; y++, ptr_src += self->bpr, ptr_dst += self->bpr)
            {
                uint8_t *src = ptr_src;
                uint8_t *dst = ptr_dst;
                
                for (; x; x--, src -= pixel_size, dst -= pixel_size);
                    memcpy(dst, src, pixel_size);
            }
        }
        else
        {
            x = -dx;
            ptr_src += y*self->bpr + x*pixel_size;
            
            for (; y < self->height; y++, ptr_src += self->bpr, ptr_dst += self->bpr)
            {
                uint8_t *src = ptr_src;
                uint8_t *dst = ptr_dst;
                
                for (; x < self->width; x++, src += pixel_size, dst += pixel_size);
                    memcpy(dst, src, pixel_size);
            }
        }
    }

    Py_RETURN_NONE;
}


static PyObject *
pixbuf_slow_transform_affine(PyPixbuf *self, PyObject *args)
{
    double fa, fb, fc, fd, fe, ff; /* Affine matrix coefiscients */
    PyObject *get_tile_cb;
    PyPixbuf *pb_dst; /* pixbuf destination */
    int ix, iy;
    int dst_pix_size, src_pix_size;
    void *dst_row_ptr;
    
    if (!PyArg_ParseTuple(args, "OO!dddddd", &get_tile_cb, &PyPixbuf_Type, &pb_dst, &fa, &fb, &fc, &fd, &fe, &ff))
        return NULL;
    
    src_pix_size = get_pixel_size(self->pixfmt);    
    dst_pix_size = get_pixel_size(pb_dst->pixfmt);
    
    dst_row_ptr = pb_dst->data;
    g_last = NULL;
    
    /* destination row-col scanline */
    for (iy=pb_dst->y; iy < (pb_dst->y + pb_dst->height); iy++, dst_row_ptr += pb_dst->bpr)
    {
        void *dst_data = dst_row_ptr;
        
        for (ix=pb_dst->x; ix < (pb_dst->x + pb_dst->width); ix++, dst_data += dst_pix_size)
        {
            double ox, oy;
            
            /* Transform destination point into original coordinates
             * (using pixbuf relative coordinates)
             */
            ox = ix * fa + iy * fc + fe;
            oy = ix * fb + iy * fd + ff;
                
            uint16_t color[MAX_CHANNELS];
            uint16_t c0[MAX_CHANNELS];
            uint16_t c1[MAX_CHANNELS];
            uint16_t c2[MAX_CHANNELS];
            uint16_t c3[MAX_CHANNELS];
            
            int x_lo, x_hi;
            int y_lo, y_hi;
            
            x_lo = trunc(ox);
            x_hi = ceil(ox);
            y_lo = trunc(oy);
            y_hi = ceil(oy);
            
            /* Read four pixels for interpolations */
            if (_get_color(get_tile_cb, x_lo, y_lo, src_pix_size, c0))
                return NULL;
                
            if (_get_color(get_tile_cb, x_hi, y_lo, src_pix_size, c1))
                return NULL;
                
            if (_get_color(get_tile_cb, x_hi, y_hi, src_pix_size, c2))
                    return NULL;
                    
            if (_get_color(get_tile_cb, x_lo, y_hi, src_pix_size, c3))
                return NULL;

            /* Compute interpolation factors */
            double fx, fy, f0, f1, f2, f3;
            
            fx = ox - floor(ox);
            fy = oy - floor(oy);
            
            f0 = (1. - fx) * (1. - fy);
            f1 =       fx  * (1. - fy);
            f2 =       fx  *       fy ;
            f3 = (1. - fx) *       fy ;
            
            /* Bilinear interpolation on each channel */
            int i;
            for (i=0; i < pb_dst->nc; i++)
                color[i] = (((double)c0[i]/(1<<15)*f0) + ((double)c1[i]/(1<<15)*f1) + ((double)c2[i]/(1<<15)*f2) + ((double)c3[i]/(1<<15)*f3)) * (1<<15);
            
            pb_dst->write2pixel(dst_data, color);
        }
    }
    
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
    {"empty", (PyCFunction)pixbuf_empty, METH_NOARGS, NULL},
    {"scroll", (PyCFunction)pixbuf_scroll, METH_VARARGS, NULL},
    {"slow_transform_affine", (PyCFunction)pixbuf_slow_transform_affine, METH_VARARGS, NULL},

    {NULL} /* sentinel */
};

static PyMemberDef pixbuf_members[] = {
    {"x", T_INT, offsetof(PyPixbuf, x), 0, NULL},
    {"y", T_INT, offsetof(PyPixbuf, y), 0, NULL},
    {"width", T_INT, offsetof(PyPixbuf, width), RO, NULL},
    {"height", T_INT, offsetof(PyPixbuf, height), RO, NULL},
    {"pixfmt", T_ULONG, offsetof(PyPixbuf, pixfmt), RO, NULL},
    {"stride", T_ULONG, offsetof(PyPixbuf, bpr), RO, NULL},
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
    bf_getreadbuffer  : (getreadbufferproc)pixbuf_getbuffer,
    bf_getwritebuffer : (getwritebufferproc)pixbuf_getbuffer,
    bf_getsegcount    : (getsegcountproc)pixbuf_getsegcount,
};

static PyNumberMethods pixbuf_as_number = {
    //nb_nonzero : (inquiry)pixbuf_nonzero,
};

static PySequenceMethods pixbuf_as_sequence = {
    sq_item: (ssizeargfunc)pixbuf_get_item,
};

static PyTypeObject PyPixbuf_Type = {
    PyObject_HEAD_INIT(NULL)

    tp_name         : "_surface.Pixbuf",
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

static PyMethodDef methods[] = {
    {"format_from_colorspace", (PyCFunction)module_format_from_colorspace, METH_VARARGS, NULL},
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

    return 0;
}

PyMODINIT_FUNC
INITFUNC(void)
{
    PyObject *m;

    if (PyType_Ready(&PyPixbuf_Type) < 0) return;

    m = Py_InitModule(MODNAME, methods);
    if (NULL == m)
        return;

    add_constants(m);

    ADD_TYPE(m, "Pixbuf", &PyPixbuf_Type);
}

