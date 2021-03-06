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

#ifndef MATH_H
#define MATH_H

#include <Python.h>
#include <math.h>

#define FASTFLOOR(x) ( ((x)>0) ? ((int)x) : (((int)x)-1) )

#ifndef M_TWOPI
#define M_TWOPI 6.28318530717958647692
#endif

extern float noise_2d(float x, float y);
extern float myrand1(void);
extern float myrand2(void);
extern void rgb_to_hsv(float *rgb, float *hsv);
extern void hsv_to_rgb(float *hsv, float *rgb);
extern void my_Py_DECREF(PyObject *o);

#endif
