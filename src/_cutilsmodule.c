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

#ifndef MODNAME
#define MODNAME "_cutils"
#endif

#ifndef INITFUNC
#define INITFUNC init_cutils
#endif

/******************************************************************************
** Module
*/

static int
transform_point(PyObject *ope, float *x, float *y)
{
	PyObject *pyo = PyObject_CallFunction(ope, "ff", *x, *y); /* NR */
	if (!PyTuple_CheckExact(pyo) || PyTuple_GET_SIZE(pyo) != 2)
		goto bad_ope_return;

	PyObject *pyx = PyTuple_GET_ITEM(pyo, 0); /* BR */
	if (!PyFloat_CheckExact(pyx))
		goto bad_ope_return;

	*x = PyFloat_AS_DOUBLE(pyx);

	PyObject *pyy = PyTuple_GET_ITEM(pyo, 1); /* BR */
	if (!PyFloat_CheckExact(pyy))
		goto bad_ope_return;

	*y = PyFloat_AS_DOUBLE(pyy);

	Py_DECREF(pyo);
	return 0;

bad_ope_return:
	Py_DECREF(pyo);
	PyErr_Format(PyExc_TypeError, "transform_point() must return a 2-tuple of floats");
	return -1;
}

static int
transform_bbox(PyObject *ope, float *x1, float *y1, float *x2, float *y2)
{
	float ax[4];
	float ay[4];

	ax[0] = *x1; ay[0] = *y1;
	if (transform_point(ope, &ax[0], &ay[0]))
		return -1;
	ax[1] = *x1; ay[1] = *y2;
	if (transform_point(ope, &ax[1], &ay[1]))
		return -1;
	ax[2] = *x2; ay[2] = *y1;
	if (transform_point(ope, &ax[2], &ay[2]))
		return -1;
	ax[3] = *x2; ay[3] = *y2;
	if (transform_point(ope, &ax[3], &ay[3]))
		return -1;

#define PERM(a, b) {typeof(a) _t; _t=a; a=b; b=_t;}
	if (ax[0] > ax[1]) PERM(ax[0], ax[1]);
	if (ax[1] > ax[2]) PERM(ax[1], ax[2]);
	if (ax[2] > ax[3]) PERM(ax[2], ax[3]);
	if (ax[0] > ax[1]) PERM(ax[0], ax[1]);
	if (ax[1] > ax[2]) PERM(ax[1], ax[2]);
	if (ax[0] > ax[1]) PERM(ax[0], ax[1]);

	if (ay[0] > ay[1]) PERM(ay[0], ay[1]);
	if (ay[1] > ay[2]) PERM(ay[1], ay[2]);
	if (ay[2] > ay[3]) PERM(ay[2], ay[3]);
	if (ay[0] > ay[1]) PERM(ay[0], ay[1]);
	if (ay[1] > ay[2]) PERM(ay[1], ay[2]);
	if (ay[0] > ay[1]) PERM(ay[0], ay[1]);
#undef PERM

	*x1 = floorf(ax[0]);
	*y1 = floorf(ay[0]);
	*x2 = ceilf(ax[3]);
	*y2 = ceilf(ay[3]);

	return 0;
}

static PyObject *
mod_transform_bbox(PyObject *mod, PyObject *args)
{
	PyObject*ope;
	float x1, y1, x2, y2;

	if (!PyArg_ParseTuple(args, "Offff", &ope, &x1, &y1, &x2, &y2))
		return NULL;

	if (transform_bbox(ope, &x1, &y1, &x2, &y2))
		return NULL;

	return Py_BuildValue("llll", (long)x1, (long)y1, (long)x2, (long)y2);
}

static PyObject *
mod_transform_area(PyObject *mod, PyObject *args)
{
	PyObject *ope;
	float x, y, w, h;

	if (!PyArg_ParseTuple(args, "Offff", &ope, &x, &y, &w, &h))
		return NULL;

	float x1 = x;
	float y1 = y;
	float x2 = x + w - 1;
	float y2 = y + h - 1;

	if (transform_bbox(ope, &x1, &y1, &x2, &y2))
		return NULL;

	x = x1;
	y = y1;
	w = x2 - x1 + 1;
	h = y2 - y1 + 1;

	return Py_BuildValue("llll", (long)x, (long)y, (long)w, (long)h);
}

static PyMethodDef mod_methods[] = {
     {"transform_bbox", (PyCFunction)mod_transform_bbox, METH_VARARGS, NULL},
	 {"transform_area", (PyCFunction)mod_transform_area, METH_VARARGS, NULL},
};

PyMODINIT_FUNC
INITFUNC(void)
{
    PyObject *m;

    m = Py_InitModule(MODNAME, mod_methods);
    if (!m) return;
}
