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
    readfunc       readpixel;
} PA_InitValue;

typedef void (*blitfunc)(void* src, void *dst,
                         uint32_t width, uint32_t height,
                         Py_ssize_t src_stride, Py_ssize_t dst_stride);

static void rgb8_writepixel(void *, float, float, unsigned short *);
static void argb8_writepixel(void *, float, float, uint16_t *);
static void rgba8_writepixel(void *, float, float, uint16_t *);
static void rgba15x_writepixel(void *, float, float, uint16_t *);
static void argb15x_writepixel(void *, float, float, uint16_t *);
static void cmyk8_writepixel(void *, float, float, uint16_t *);
static void cmyka15x_writepixel(void *, float, float, uint16_t *);

static void dummy_readpixel(void *, uint16_t *);
static void argb15x_readpixel(void *, uint16_t *);
static void rgba15x_readpixel(void *, uint16_t *);

static void rgb8_fromfloat(float, void *);
static void rgba15x_fromfloat(float, void *);

static float rgb8_tofloat(void *);
static float rgba15x_tofloat(void *);

static const PA_InitValue gInitValues[] = {
    {/*PyPixBuf_PIXFMT_RGB_8,*/      3, 8,  rgb8_fromfloat,    rgb8_tofloat,    rgb8_writepixel, dummy_readpixel},
    {/*PyPixBuf_PIXFMT_ARGB_8,*/     4, 8,  rgb8_fromfloat,    rgb8_tofloat,    argb8_writepixel, dummy_readpixel},
    {/*PyPixBuf_PIXFMT_RGBA_8,*/     4, 8,  rgb8_fromfloat,    rgb8_tofloat,    rgba8_writepixel, dummy_readpixel},
    {/*PyPixbuf_PIXFMT_RGBA_8_NOA,*/ 4, 8,  rgb8_fromfloat,    rgb8_tofloat,    rgba8_writepixel, dummy_readpixel},
    {/*PyPixBuf_PIXFMT_CMYK_8,*/     4, 8,  rgb8_fromfloat,    rgb8_tofloat,    cmyk8_writepixel, dummy_readpixel},
    {/*PyPixBuf_PIXFMT_RGBA_15X,*/   4, 16, rgba15x_fromfloat, rgba15x_tofloat, rgba15x_writepixel, rgba15x_readpixel},
    {/*PyPixBuf_PIXFMT_ARGB_15X,*/   4, 16, rgba15x_fromfloat, rgba15x_tofloat, argb15x_writepixel, argb15x_readpixel},
    {/*PyPixBuf_PIXFMT_CMYKA_15X,*/  5, 16, rgba15x_fromfloat, rgba15x_tofloat, cmyka15x_writepixel, dummy_readpixel},

    {0}
};

/*******************************************************************************************
** Private routines
*/

/*** Pixel write functions ***/

//+ rgb8_writepixel
static void
rgb8_writepixel(void * data, float opacity, float erase, uint16_t *color)
{
    uint8_t *pixel = data;
    uint32_t alpha = (uint32_t)(opacity * 255);
    uint32_t one_minus_alpha = 255 - alpha;

    alpha *= erase;

    /* R */ pixel[0] = (((alpha*color[0]*255)>>15) + one_minus_alpha*pixel[0]) / 255;
    /* G */ pixel[1] = (((alpha*color[1]*255)>>15) + one_minus_alpha*pixel[1]) / 255;
    /* B */ pixel[2] = (((alpha*color[2]*255)>>15) + one_minus_alpha*pixel[2]) / 255;
}
//-
//+ rgba8_writepixel
static void
rgba8_writepixel(void * data, float opacity, float erase, uint16_t *color)
{
    uint8_t *pixel = data;
    uint32_t alpha = (uint32_t)(opacity * 255);
    uint32_t one_minus_alpha = 255 - alpha;

    alpha *= erase;

    /* R */ pixel[0] = (((alpha*color[0]*255)>>15) + one_minus_alpha*pixel[0]) / 255;
    /* G */ pixel[1] = (((alpha*color[1]*255)>>15) + one_minus_alpha*pixel[1]) / 255;
    /* B */ pixel[2] = (((alpha*color[2]*255)>>15) + one_minus_alpha*pixel[2]) / 255;
    /* A */ pixel[3] =    alpha                    + one_minus_alpha*pixel[3]  / 255;
}
//-
//+ argb8_writepixel
static void
argb8_writepixel(void * data, float opacity, float erase, uint16_t *color)
{
    uint8_t *pixel = data;
    uint32_t alpha = (uint32_t)(opacity * 255);
    uint32_t one_minus_alpha = 255 - alpha;

    alpha *= erase;

    /* A */ pixel[0] =    alpha                    + one_minus_alpha*pixel[0]  / 255;
    /* R */ pixel[1] = (((alpha*color[0]*255)>>15) + one_minus_alpha*pixel[1]) / 255;
    /* G */ pixel[2] = (((alpha*color[1]*255)>>15) + one_minus_alpha*pixel[2]) / 255;
    /* B */ pixel[3] = (((alpha*color[2]*255)>>15) + one_minus_alpha*pixel[3]) / 255;
}
//-
//+ cmyk8_writepixel
static void
cmyk8_writepixel(void * data, float opacity, float erase, uint16_t *color)
{
    uint8_t *pixel = data;
    uint32_t alpha = (uint32_t)(opacity * 255);
    uint32_t one_minus_alpha = 255 - alpha;

    alpha *= erase;

    /* C */ pixel[0] = (((alpha*color[0]*255)>>15) + one_minus_alpha*pixel[0]) / 255;
    /* M */ pixel[1] = (((alpha*color[1]*255)>>15) + one_minus_alpha*pixel[1]) / 255;
    /* Y */ pixel[2] = (((alpha*color[2]*255)>>15) + one_minus_alpha*pixel[2]) / 255;
    /* K */ pixel[3] = (((alpha*color[3]*255)>>15) + one_minus_alpha*pixel[3]) / 255;
}
//-
//+ rgba15x_writepixel
static void
rgba15x_writepixel(void * data, float opacity, float erase, uint16_t *color)
{
    uint16_t *pixel = data;
    uint32_t alpha = (uint32_t)(opacity*erase * (1<<15));
    uint32_t one_minus_alpha = (1<<15) - alpha;

    /* R */ pixel[0] = (alpha*color[0] + one_minus_alpha*pixel[0]) / (1<<15);
    /* G */ pixel[1] = (alpha*color[1] + one_minus_alpha*pixel[1]) / (1<<15);
    /* B */ pixel[2] = (alpha*color[2] + one_minus_alpha*pixel[2]) / (1<<15);
    /* A */ pixel[3] =  alpha          + one_minus_alpha*pixel[3]  / (1<<15);
}
//-
//+ argb15x_writepixel
static void
argb15x_writepixel(void * data, float opacity, float erase, uint16_t *color)
{
    uint16_t *pixel = data;
    uint32_t alpha = (uint32_t)(opacity*erase * (1<<15));
    uint32_t one_minus_alpha = (1<<15) - (uint32_t)(opacity * (1<<15));

    /* A */ pixel[0] =  alpha          + one_minus_alpha*pixel[0]  / (1<<15);
    /* R */ pixel[1] = (alpha*color[0] + one_minus_alpha*pixel[1]) / (1<<15);
    /* G */ pixel[2] = (alpha*color[1] + one_minus_alpha*pixel[2]) / (1<<15);
    /* B */ pixel[3] = (alpha*color[2] + one_minus_alpha*pixel[3]) / (1<<15);
}
//-
//+ cmyka15x_writepixel
static void
cmyka15x_writepixel(void * data, float opacity, float erase, uint16_t *color)
{
    uint16_t *pixel = data;
    uint32_t alpha = (uint32_t)(opacity * (1<<15));
    uint32_t one_minus_alpha = (1<<15) - alpha;

    alpha *= erase;

    /* C */ pixel[0] = (alpha*color[0] + one_minus_alpha*pixel[0]) / (1<<15);
    /* M */ pixel[1] = (alpha*color[1] + one_minus_alpha*pixel[1]) / (1<<15);
    /* Y */ pixel[2] = (alpha*color[2] + one_minus_alpha*pixel[2]) / (1<<15);
    /* K */ pixel[3] = (alpha*color[3] + one_minus_alpha*pixel[3]) / (1<<15);
    /* A */ pixel[4] =  alpha          + one_minus_alpha*pixel[4]  / (1<<15);
}
//-

//+ dummy_readpixel
static void
dummy_readpixel(void *data, uint16_t *color)
{
    /* R */ color[0] = 0;
    /* G */ color[1] = 0;
    /* B */ color[2] = 0;
    /* A */ color[3] = 0;
}
//-
//+ argb15x_readpixel
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
//-
//+ rgba15x_readpixel
static void
rgba15x_readpixel(void *data, uint16_t *color)
{
    uint16_t *pixel = data;

    /* R */ color[0] = pixel[0];
    /* G */ color[1] = pixel[1];
    /* B */ color[2] = pixel[2];
    /* A */ color[3] = pixel[3];
}
//-

/*** Color conversion functions ***/

/* /!\ no clamping applied ! */

//+ rgb8_fromfloat
static void
rgb8_fromfloat(float from, void *to)
{
    *((uint8_t *)to) = (uint8_t)(from * 255);
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
rgb8_tofloat(void * from)
{
    return (float)(*(uint8_t *)from) / 255;
}
//-
//+ rgba15x_tofloat
static float
rgba15x_tofloat(void * from)
{
    return (float)(*(uint16_t *)from) / (1<<15);
}
//-


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

//+ argb15x_to_argb8
/* Alpha-premul is conservated */
static void
argb15x_to_argb8(uint16_t *src1, uint8_t *dst1,
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
//-
//+ argb15x_to_bgra8
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
//-
//+ argb15x_to_rgba8
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
//-
//+ argb15x_to_rgba8_noa
/* Alpha-premul is not conservated */
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
//-
//+ argb15x_to_abgr8
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
//-
//+ argb15x_to_rgb8
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
//-
//+ rgba8_noa_to_argb15x
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
                *(uint32_t *)dst = 0;

            /* Next ARGB pixel */
            src += 4;
            dst += 4;
        }
    }
}
//-
//+ argb8_to_argb15x
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
                *(uint32_t *)dst = 0;

            /* Next ARGB pixel */
            src += 4;
            dst += 4;
        }
    }
}
//-
//+ bgra8_to_argb15x
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
                *(uint32_t *)dst = 0;

            /* Next ARGB pixel */
            src += 4;
            dst += 4;
        }
    }
}
//-

/********* Others ***************************************/

//+ get_init_values
const PA_InitValue *
get_init_values(int pixfmt)
{
    switch (pixfmt)
    {
        case PyPixbuf_PIXFMT_RGB_8:         return &gInitValues[0];
        case PyPixbuf_PIXFMT_ARGB_8:        return &gInitValues[1];
        case PyPixbuf_PIXFMT_RGBA_8:        return &gInitValues[2];
        case PyPixbuf_PIXFMT_RGBA_8_NOA:    return &gInitValues[3];
        case PyPixbuf_PIXFMT_CMYK_8:        return &gInitValues[4];
        case PyPixbuf_PIXFMT_RGBA_15X:      return &gInitValues[5];
        case PyPixbuf_PIXFMT_ARGB_15X:      return &gInitValues[6];
        case PyPixbuf_PIXFMT_CMYKA_15X:     return &gInitValues[7];

        default: return NULL;
    }
}
//-
//+ get_blit_function
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
            case PyPixbuf_PIXFMT_RGBA_8:        return (blitfunc)argb15x_to_rgba8;
            case PyPixbuf_PIXFMT_RGBA_8_NOA:    return (blitfunc)argb15x_to_rgba8_noa;
            case PyPixbuf_PIXFMT_RGB_8:         return (blitfunc)argb15x_to_rgb8;
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
                case PyPixbuf_PIXFMT_ARGB_15X:  return (blitfunc)bgra8_to_argb15x;
            }
        }
#endif

        switch (dst_fmt)
        {
            case PyPixbuf_PIXFMT_ARGB_15X:      return (blitfunc)argb8_to_argb15x;
        }
    }
    else if ((src_fmt == PyPixbuf_PIXFMT_RGBA_8_NOA) && (dst_fmt == PyPixbuf_PIXFMT_ARGB_15X))
        return (blitfunc)rgba8_noa_to_argb15x;

    return NULL;
}
//-
//+ get_pixel_size
static int
get_pixel_size(int pixfmt)
{
    const PA_InitValue *pa = get_init_values(pixfmt);

    if (NULL != pa)
        return (pa->nc*pa->bpc + 7)/8;
    return -1;
}
//-


/*******************************************************************************************
** PyPixbuf_Type
*/

//+ initialize_pixbuf
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

    self->data_alloc = AllocVecTaskPooled((self->bpr*height)+32);
    if (NULL != self->data_alloc)
    {
        self->data = (void*)((((unsigned long)self->data_alloc)+31) & ~31ul);
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
        self->readpixel = init_values->readpixel;

        return 1;
    }

    return 0;
}
//-

//+ pixbuf_new
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
//-
//+ pixbuf_dealloc
static void
pixbuf_dealloc(PyPixbuf *self)
{
    if (NULL != self->data_alloc) FreeVecTaskPooled(self->data_alloc);
    self->ob_type->tp_free((PyObject *)self);
}
//-
//+ pixbuf_get_item
static PyObject *
pixbuf_get_item(PyPixbuf *self, Py_ssize_t i)
{
    Py_RETURN_NONE;
}
//-
//+ pixbuf_compare
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
//-
//+ pixbuf_set_pixel
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
//-
//+ pixbuf_get_pixel
static PyObject *
pixbuf_get_pixel(PyPixbuf *self, PyObject *args)
{
    int x, y, n;
    PyObject *py_color;
    uint8_t *pix;
    uint16_t color[MAX_CHANNELS];

    if (!PyArg_ParseTuple(args, "ii", &x, &y))
        return NULL;

    if ((x < 0) || (y < 0) || (x >= self->width) || (y >= self->height))
    {
        PyErr_SetString(PyExc_ValueError, "Invalide coordinates (out of bounds)");
        return NULL;
    }

    pix = &self->data[y*self->bpr + x*(self->bpc/8)*self->nc];
    self->readpixel(pix, color);

    n = self->nc;
    if (self->pixfmt & PyPixbuf_FLAG_HAS_ALPHA)
        n--;

    py_color = PyTuple_New(n);
    if (NULL != py_color)
    {
        int i;

        for (i=0; i<n; i++)
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
//-
//+ pixbuf_get_mem_size
static PyObject *
pixbuf_get_mem_size(PyPixbuf *self, void *closure)
{
    return PyLong_FromUnsignedLong(self->bpr * self->height);
}
//-
//+ pixbuf_get_size
static PyObject *
pixbuf_get_size(PyPixbuf *self, void *closure)
{
    return Py_BuildValue("II", self->width, self->height);
}
//-
//+ pixbuf_blit
static PyObject *
pixbuf_blit(PyPixbuf *self, PyObject *args)
{
    Py_ssize_t size;
    int dxoff=0, dyoff=0;
    int sxoff=0, syoff=0;
    unsigned int dst_stride, dst_pixfmt, dw, dh;
    uint8_t *dst;
    blitfunc blit;
    int endian_care=TRUE, dst_pix_size, src_pix_size;

    if (!PyArg_ParseTuple(args, "Iw#III|iii", &dst_pixfmt, &dst, &size, &dst_stride, &dw, &dh, &dxoff, &dyoff, &endian_care))
        return NULL;

    blit = get_blit_function(self->pixfmt, dst_pixfmt, endian_care);
    if (NULL == blit)
        return PyErr_Format(PyExc_TypeError, "Don't know how to blit from format 0x%08x to format 0x%08x",
                            self->pixfmt, dst_pixfmt);

    dst_pix_size = get_pixel_size(dst_pixfmt);
    if (dst_pix_size <= 0)
        return PyErr_Format(PyExc_TypeError, "Don't know pixel size of format 0x%08x", dst_pixfmt);

    if (dxoff < 0)
    {
        if (-dxoff >= self->width)
            Py_RETURN_NONE;

        sxoff = -dxoff;
        dxoff = 0;
        dw = MIN(dw, self->width - sxoff);
    }
    else if (dxoff >= dw)
        Py_RETURN_NONE;
    else
        dw = MIN(dw-dxoff, self->width);

    if (dyoff < 0)
    {
        if (-dyoff >= self->height)
            Py_RETURN_NONE;
            
        syoff = -dyoff;
        dyoff = 0;
        dh = MIN(dh, self->height - syoff);
    }
    else if (dyoff >= dh)
        Py_RETURN_NONE;
    else
        dh = MIN(dh-dyoff, self->height);

    src_pix_size = get_pixel_size(self->pixfmt);

    /* Rasterize pixels to the given buffer */
    blit((void *)(self->data + syoff*self->bpr + sxoff*src_pix_size),
         (void *)(dst + dyoff*dst_stride + dxoff*dst_pix_size),
         dw, dh, self->bpr, dst_stride);

    Py_RETURN_NONE;
}
//-
//+ pixbuf_from_buffer
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
//-
//+ pixbuf_clear
static PyObject *
pixbuf_clear(PyPixbuf *self, PyObject *args)
{
    bzero(self->data, self->bpr * self->height);
    Py_RETURN_NONE;
}
//-
//+ pixbuf_clear_area
static PyObject *
pixbuf_clear_area(PyPixbuf *self, PyObject *args)
{
    int xoff, yoff;
    unsigned int y, w, h, pixel_size;
    unsigned char *ptr = self->data;
    
    if (!PyArg_ParseTuple(args, "iiII", &xoff, &yoff, &w, &h))
        return NULL;
        
    /* clip */
    if (xoff < 0) xoff = 0;
    else if (xoff >= self->width) goto bye;
    
    if (yoff < 0) yoff = 0;
    else if (yoff >= self->height) goto bye;

    if ((xoff+w) > self->width) w = self->width - xoff;
    if ((yoff+h) > self->height) h = self->height - yoff;

    /* clear */
    pixel_size = (self->nc*self->bpc) >> 3;
    ptr += yoff*self->bpr + xoff*pixel_size;
    for (y=0; y < h; y++, ptr += self->bpr)
        bzero(ptr, w*pixel_size);
        
bye:
    Py_RETURN_NONE;
}
//-
//+ pixbuf_clear_white
static PyObject *
pixbuf_clear_white(PyPixbuf *self, PyObject *args)
{
    unsigned int y, x;
    void *pix = self->data;
    int pixoff = (self->bpc * self->nc) / 8;
    static uint16_t white[] = {1<<15, 1<<15, 1<<15};
   
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
//-
//+ pixbuf_empty
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
//-
//+ pixbuf_getsegcount
static Py_ssize_t
pixbuf_getsegcount(PyPixbuf *self, Py_ssize_t *lenp)
{
    if (NULL != lenp)
        *lenp = self->bpr * self->height;
    return 1;
}
//-
//+ pixbuf_getbuffer
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
//-

static struct PyMethodDef pixbuf_methods[] = {
    {"set_pixel", (PyCFunction)pixbuf_set_pixel, METH_VARARGS, NULL},
    {"get_pixel", (PyCFunction)pixbuf_get_pixel, METH_VARARGS, NULL},
    {"blit", (PyCFunction)pixbuf_blit, METH_VARARGS, NULL},
    {"from_buffer", (PyCFunction)pixbuf_from_buffer, METH_VARARGS, NULL},
    {"clear", (PyCFunction)pixbuf_clear, METH_NOARGS, NULL},
    {"clear_area", (PyCFunction)pixbuf_clear_area, METH_VARARGS, NULL},
    {"clear_white", (PyCFunction)pixbuf_clear_white, METH_NOARGS, NULL},
    {"empty", (PyCFunction)pixbuf_empty, METH_NOARGS, NULL},

    {NULL} /* sentinel */
};

static PyMemberDef pixbuf_members[] = {
    {"x", T_INT, offsetof(PyPixbuf, x), 0, NULL},
    {"y", T_INT, offsetof(PyPixbuf, y), 0, NULL},
    {"width", T_INT, offsetof(PyPixbuf, width), RO, NULL},
    {"height", T_INT, offsetof(PyPixbuf, height), RO, NULL},
    {"pixfmt", T_ULONG, offsetof(PyPixbuf, pixfmt), RO, NULL},
    {"stride", T_ULONG, offsetof(PyPixbuf, bpr), RO, NULL},
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

//+ module_format_from_colorspace
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
//-

static PyMethodDef methods[] = {
    {"format_from_colorspace", (PyCFunction)module_format_from_colorspace, METH_VARARGS, NULL},
    {NULL} /* sentinel */
};

//+ add_constants
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
    INSI(m, "FORMAT_RGBA8_NOA", PyPixbuf_PIXFMT_RGBA_8_NOA);

    return 0;
}
//-
//+ INITFUNC()
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
//-
