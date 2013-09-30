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

#include "common.h"
#include "math.h"

/* After time testing, with GCC 4.4.x & -O2, using int or char
 * doesn't make any differences in term of speed, but int array takes 1.5kB more.
 */
static const unsigned char const perm[512] = {
151,160,137,91,90,15,
131,13,201,95,96,53,194,233,7,225,140,36,103,30,69,142,8,99,37,240,21,10,23,
190,6,148,247,120,234,75,0,26,197,62,94,252,219,203,117,35,11,32,57,177,33,
88,237,149,56,87,174,20,125,136,171,168,68,175,74,165,71,134,139,48,27,166,
77,146,158,231,83,111,229,122,60,211,133,230,220,105,92,41,55,46,245,40,244,
102,143,54,65,25,63,161,1,216,80,73,209,76,132,187,208,89,18,169,200,196,
135,130,116,188,159,86,164,100,109,198,173,186,3,64,52,217,226,250,124,123,
5,202,38,147,118,126,255,82,85,212,207,206,59,227,47,16,58,17,182,189,28,42,
223,183,170,213,119,248,152,2,44,154,163,70,221,153,101,155,167,43,172,9,
129,22,39,253,19,98,108,110,79,113,224,232,178,185,112,104,218,246,97,228,
251,34,242,193,238,210,144,12,191,179,162,241,81,51,145,235,249,14,239,107,
49,192,214,31,181,199,106,157,184,84,204,176,115,121,50,45,127,4,150,254,
138,236,205,93,222,114,67,29,24,72,243,141,128,195,78,66,215,61,156,180,

151,160,137,91,90,15,
131,13,201,95,96,53,194,233,7,225,140,36,103,30,69,142,8,99,37,240,21,10,23,
190,6,148,247,120,234,75,0,26,197,62,94,252,219,203,117,35,11,32,57,177,33,
88,237,149,56,87,174,20,125,136,171,168,68,175,74,165,71,134,139,48,27,166,
77,146,158,231,83,111,229,122,60,211,133,230,220,105,92,41,55,46,245,40,244,
102,143,54,65,25,63,161,1,216,80,73,209,76,132,187,208,89,18,169,200,196,
135,130,116,188,159,86,164,100,109,198,173,186,3,64,52,217,226,250,124,123,
5,202,38,147,118,126,255,82,85,212,207,206,59,227,47,16,58,17,182,189,28,42,
223,183,170,213,119,248,152,2,44,154,163,70,221,153,101,155,167,43,172,9,
129,22,39,253,19,98,108,110,79,113,224,232,178,185,112,104,218,246,97,228,
251,34,242,193,238,210,144,12,191,179,162,241,81,51,145,235,249,14,239,107,
49,192,214,31,181,199,106,157,184,84,204,176,115,121,50,45,127,4,150,254,
138,236,205,93,222,114,67,29,24,72,243,141,128,195,78,66,215,61,156,180
};

static const int const grad3[12][3] = {
    {1,1,0},{-1,1,0},{1,-1,0},{-1,-1,0},
    {1,0,1},{-1,0,1},{1,0,-1},{-1,0,-1},
    {0,1,1},{0,-1,1},{0,1,-1},{0,-1,-1}
};

#define F2 0.366025403f // 0.5*(sqrt(3.0)-1.0)
#define G2 0.211324865f // (3.0-sqrt(3.0))/6.0

float dot2(const int *g, float x, float y)
{
    return g[0]*x + g[1]*y;
}

// 2D simplex noise
float noise_2d(float x, float y)
{
    float n0, n1, n2;

    float s = (x+y)*F2;
    float xs = x + s;
    float ys = y + s;
    int i = FASTFLOOR(xs);
    int j = FASTFLOOR(ys);

    float t = (i+j)*G2;
    float X0 = i-t;
    float Y0 = j-t;
    float x0 = x-X0;
    float y0 = y-Y0;

    int i1, j1;
    if(x0>y0) {i1=1; j1=0;}
    else {i1=0; j1=1;}

    float x1 = x0 - i1 + G2;
    float y1 = y0 - j1 + G2;
    float x2 = x0 - 1.0f + 2.0f * G2;
    float y2 = y0 - 1.0f + 2.0f * G2;

    int ii = i & 0xff;
    int jj = j & 0xff;

    float t0 = 0.5f - x0*x0 - y0*y0;
    if(t0 < 0.0f)
        n0 = 0.0f;
    else
    {
        int gi0 = perm[ii+perm[jj]] % 12;
        t0 *= t0;
        n0 = t0 * t0 * dot2(grad3[gi0], x0, y0);
    }

    float t1 = 0.5f - x1*x1 - y1*y1;
    if(t1 < 0.0f)
        n1 = 0.0f;
    else
    {
        int gi1 = perm[ii+i1+perm[jj+j1]] % 12;
        t1 *= t1;
        n1 = t1 * t1 * dot2(grad3[gi1], x1, y1);
    }

    float t2 = 0.5f - x2*x2 - y2*y2;
    if(t2 < 0.0f)
        n2 = 0.0f;
    else
    {
        int gi2 = perm[ii+1+perm[jj+1]] % 12;
        t2 *= t2;
        n2 = t2 * t2 * dot2(grad3[gi2], x2, y2);
    }

    return 40.0f * (n0 + n1 + n2);
}

#ifdef __MORPHOS__
#include <exec/system.h>
//+ myrand1
float myrand1(void)
{
    static unsigned int seed=0;

    seed = FastRand(seed);
    return (float)seed / 0xffffffff;
}
//-
//+ myrand2
float myrand2(void)
{
    static unsigned int seed=0x1fa9b36;

    seed = FastRand(seed);
    return (float)seed / 0xffffffff;
}
//-
#else
//+ myrand1
float myrand1(void)
{
    static unsigned int seed=0;
    int v;

    v = rand_r(&seed);
    return (float)v / RAND_MAX;
}
//-
//+ myrand2
float myrand2(void)
{
    static unsigned int seed=0x1fa9b36;
    int v;

    v = rand_r(&seed);
    return (float)v / RAND_MAX;
}
//-
#endif

//+ rgb_to_hsv
void
rgb_to_hsv(float *rgb, float *hsv)
{
    float rc, gc, bc;
    float maxc = MAX(MAX(rgb[0], rgb[1]), rgb[2]);
    float minc = MIN(MIN(rgb[0], rgb[1]), rgb[2]);
    float delta, h;

    hsv[2] = maxc;

    if (minc == maxc)
    {
        hsv[0] = hsv[1] = 0.0;
        return;
    }

    delta = maxc - minc;
    hsv[1] = delta / maxc;

    rc = (maxc-rgb[0]) / delta + 3.0;
    gc = (maxc-rgb[1]) / delta + 3.0;
    bc = (maxc-rgb[2]) / delta + 3.0;

    if (rgb[0] == maxc) h = bc-gc;
    else if (rgb[1] == maxc) h = 2.0+rc-bc;
    else h = 4.0+gc-rc;

    h /= 6.0;

    if (h < 0) h += 1.0;
    if (h > 1) h -= 1.0;

    hsv[0] = h;
}
//-
//+
void
hsv_to_rgb(float *hsv, float *rgb)
{
    int i;
    float f,p,q,t,h,s,v;

    h = hsv[0];
    h = h - floorf(h);
    s = CLAMP(hsv[1], 0.0, 1.0);
    v = CLAMP(hsv[2], 0.0, 1.0);

    if (s == 0.0)
    {
        rgb[0] = rgb[1] = rgb[2] = v;
        return;
    }

    f = h * 6.0;
    // Uneeded due to the modf() below: if (f == 6.0) f = 0.0;
    i = floorf(f);
    f -= i;
    p = v*(1.0 - s);
    q = v*(1.0 - s*f);
    t = v*(1.0 - s*(1.0-f));

    if (i%6 == 0) {rgb[0]=v; rgb[1]=t; rgb[2]=p; return;}
    if (i == 1) {rgb[0]=q; rgb[1]=v; rgb[2]=p; return;}
    if (i == 2) {rgb[0]=p; rgb[1]=v; rgb[2]=t; return;}
    if (i == 3) {rgb[0]=p; rgb[1]=q; rgb[2]=v; return;}
    if (i == 4) {rgb[0]=t; rgb[1]=p; rgb[2]=v; return;}

    rgb[0]=v; rgb[1]=p; rgb[2]=q; return;
}
//-

void my_Py_DECREF(PyObject *o)
{
    Py_DECREF(o);
}
