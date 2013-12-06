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

typedef struct PyArea_STRUCT {
	PyObject_HEAD
	int x, y, w, h;
} PyArea;

static PyTypeObject PyArea_Type;

static PyObject *
_area_new(int x, int y, int w, int h)
{
	PyArea *area;

	area = (PyArea *)PyObject_New(PyArea, &PyArea_Type); /* NR */
	if (area)
	{
		area->x = x;
		area->y = y;
		area->w = w;
		area->h = h;
	}

	return (PyObject *)area;
}

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

/*******************************************************************************************
** PyArea_Type
*/

static PyObject*
area_new(PyTypeObject *type, PyObject *args)
{
    PyArea *self;

    self = (void *)type->tp_alloc(type, 0); /* NR */
    if (self)
    {
		self->x = 0;
		self->y = 0;
		self->w = 0;
		self->h = 0;

        if (!PyArg_ParseTuple(args, "|iiii", &self->x, &self->y, &self->w, &self->h))
            Py_CLEAR(self);
    }

    return (PyObject *)self;
}

static PyObject*
area_copy(PyArea *self)
{
	return _area_new(self->x, self->y, self->w, self->h);
}

static PyObject*
area_join_inplace(PyArea *self, PyObject *args)
{
	PyArea *other;

	if (!PyArg_ParseTuple(args, "O!", &PyArea_Type, &other))
		return NULL;

	if (!self->w || !self->h)
	{
		self->x = other->x;
		self->y = other->y;
		self->w = other->w;
		self->h = other->h;
	}
	else if (other->w && other->h)
	{
		const int x = self->x;
		const int y = self->y;
		self->x = MIN(x, other->x);
		self->y = MIN(y, other->y);
		self->w = MAX(x + self->w, other->x + other->w) - self->x;
		self->h = MAX(y + self->h, other->y + other->h) - self->y;
	}

	Py_INCREF(self);
	return (PyObject *)self;
}

static PyObject*
area_join(PyArea *self, PyObject *args)
{
	PyArea *other;

	if (!PyArg_ParseTuple(args, "O!", &PyArea_Type, &other))
		return NULL;

	if (!self->w || !self->h)
		return _area_new(other->x, other->y, other->w, other->h);

	if (!other->w && !other->h)
		return _area_new(self->x, self->y, self->w, self->h);

	const int x = self->x;
	const int y = self->y;

	return _area_new(MIN(x, other->x),
					 MIN(y, other->y),
					 MAX(x + self->w, other->x + other->w) - self->x,
					 MAX(y + self->h, other->y + other->h) - self->y);
}

static PyObject*
area_clip(PyArea *self, PyObject *args)
{
	if (!self->w || !self->h)
		return _area_new(self->x, self->y, 0, 0);

	PyArea *other;

	if (!PyArg_ParseTuple(args, "O!", &PyArea_Type, &other))
		return NULL;

	if (!other->w || !other->h)
		return _area_new(self->x, self->y, 0, 0);

	const int ax1 = self->x;
	const int ay1 = self->y;
	const int ax2 = self->x + self->w - 1;
	const int ay2 = self->y + self->h - 1;

	const int bx1 = other->x;
	const int by1 = other->y;
	const int bx2 = other->x + other->w - 1;
	const int by2 = other->y + other->h - 1;

	/* non-overlaping cases */
	if (ax2 < bx1 || bx2 < ax1)
		return _area_new(self->x, self->y, 0, 0);

	int x, y, w, h;

	/* process X-axis */
	if (ax1 <= bx1) {
		x = bx1;
		if (ax2 <= bx2)
			w = ax2 - self->x + 1;
		else
			w = bx2 - self->x + 1;
	} else {
		x = ax1;
		if (ax2 <= bx2)
			w = ax2 - self->x + 1;
		else
			w = bx2 - self->x + 1;
	}

	/* process Y-axis */
	if (ay1 <= by1) {
		y = by1;
		if (ay2 <= by2)
			h = ay2 - self->y + 1;
		else
			h = by2 - self->y + 1;
	} else {
		y = ay1;
		if (ay2 <= by2)
			h = ay2 - self->y + 1;
		else
			h = by2 - self->y + 1;
	}

	return _area_new(x, y, w, h);
}

static PyObject*
area_clip_inplace(PyArea *self, PyObject *args)
{
	if (!self->w || !self->h)
		goto return_self;

	PyArea *other;

	if (!PyArg_ParseTuple(args, "O!", &PyArea_Type, &other))
		return NULL;

	if (!other->w || !other->h) {
		self->w = 0;
		self->h = 0;
		goto return_self;
	}

	const int ax1 = self->x;
	const int ay1 = self->y;
	const int ax2 = self->x + self->w - 1;
	const int ay2 = self->y + self->h - 1;

	const int bx1 = other->x;
	const int by1 = other->y;
	const int bx2 = other->x + other->w - 1;
	const int by2 = other->y + other->h - 1;

	/* non-overlaping cases */
	if (ax2 < bx1 || bx2 < ax1) {
		self->w = 0;
		self->h = 0;
		goto return_self;
	}

	/* process X-axis */
	if (ax1 <= bx1) {
		self->x = bx1;
		if (ax2 <= bx2)
			self->w = ax2 - self->x + 1;
		else
			self->w = bx2 - self->x + 1;
	} else {
		self->x = ax1;
		if (ax2 <= bx2)
			self->w = ax2 - self->x + 1;
		else
			self->w = bx2 - self->x + 1;
	}

	/* process Y-axis */
	if (ay1 <= by1) {
		self->y = by1;
		if (ay2 <= by2)
			self->h = ay2 - self->y + 1;
		else
			self->h = by2 - self->y + 1;
	} else {
		self->y = ay1;
		if (ay2 <= by2)
			self->h = ay2 - self->y + 1;
		else
			self->h = by2 - self->y + 1;
	}

return_self:
	Py_INCREF(self);
	return (PyObject *)self;
}

static PyObject*
area_transform(PyArea *self, PyObject *args)
{
	PyObject *ope;

	if (!PyArg_ParseTuple(args, "O", &ope))
		return NULL;

	if (!self->w || !self->h)
		_area_new(self->x, self->y, 0, 0);

	float x1 = self->x;
	float y1 = self->y;
	float x2 = self->x + self->w - 1;
	float y2 = self->y + self->h - 1;

	if (transform_bbox(ope, &x1, &y1, &x2, &y2))
		return NULL;

	return _area_new(x1, y1, (int)(x2 - x1) + 1, (int)(y2 - y1) + 1);
}

static PyObject*
area_transform_inplace(PyArea *self, PyObject *args)
{
	PyObject *ope;

	if (!PyArg_ParseTuple(args, "O", &ope))
		return NULL;

	if (!self->w || !self->h)
		goto return_self;

	float x1 = self->x;
	float y1 = self->y;
	float x2 = self->x + self->w - 1;
	float y2 = self->y + self->h - 1;

	if (transform_bbox(ope, &x1, &y1, &x2, &y2))
		return NULL;

	self->x = x1;
	self->y = y1;
	self->w = (int)(x2 - x1) + 1;
	self->h = (int)(y2 - y1) + 1;

return_self:
	Py_INCREF(self);
	return (PyObject *)self;
}

static int
area_nonzero(PyArea *self, PyObject *args)
{
	return self->w && self->h;
}

static PyObject*
area_get_item(PyArea *self, Py_ssize_t i)
{
	long v;

	switch (i)
	{
	case 0: v = self->x; break;
	case 1: v = self->y; break;
	case 2: v = self->w; break;
	case 3: v = self->h; break;
	default: PyErr_SetString(PyExc_IndexError, "invalid index"); return NULL;
	}

	return PyInt_FromLong(v);
}

static Py_ssize_t
area_length(PyArea *self)
{
    return 4;
}

static struct PyMethodDef area_methods[] = {
	{"copy", (PyCFunction)area_copy, METH_NOARGS, NULL},
	{"join", (PyCFunction)area_join, METH_VARARGS, NULL},
	{"join_in", (PyCFunction)area_join_inplace, METH_VARARGS, NULL},
	{"clip", (PyCFunction)area_clip, METH_VARARGS, NULL},
	{"clip_in", (PyCFunction)area_clip_inplace, METH_VARARGS, NULL},
	{"transform", (PyCFunction)area_transform, METH_VARARGS, NULL},
	{"transform_in", (PyCFunction)area_transform_inplace, METH_VARARGS, NULL},
	{NULL} /* sentinel */
};

static PyNumberMethods area_as_number = {
    nb_nonzero : (inquiry)area_nonzero,
};

static PyMemberDef area_members[] = {
    {"x", T_INT, offsetof(PyArea, x), 0, NULL},
    {"y", T_INT, offsetof(PyArea, y), 0, NULL},
    {"width", T_INT, offsetof(PyArea, w), 0, NULL},
    {"height", T_INT, offsetof(PyArea, h), 0, NULL},
    {NULL} /* sentinel */
};

static PySequenceMethods area_as_sequence = {
    sq_length : (lenfunc)area_length,
    sq_item   : (ssizeargfunc)area_get_item,
};

lenfunc sq_length;

static PyTypeObject PyArea_Type = {
    PyObject_HEAD_INIT(NULL)

    tp_name         : "model.Area",
    tp_basicsize    : sizeof(PyArea),
    tp_flags        : Py_TPFLAGS_DEFAULT,
    tp_doc          : "Area Objects",

	tp_new			: (newfunc)area_new,
    tp_methods      : area_methods,
    tp_members      : area_members,
	tp_as_number    : &area_as_number,
	tp_as_sequence  : &area_as_sequence,
};


/******************************************************************************
** Module
*/

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

static PyObject*
mod_area_from_bbox(PyObject *mod, PyObject *args)
{
	int x1, y1, x2, y2;

	if (!PyArg_ParseTuple(args, "iiii", &x1, &y1, &x2, &y2))
		return NULL;

	return _area_new(x1, y1, x2-x1+1, y2-y1+1);
}

static PyMethodDef mod_methods[] = {
	{"area_from_bbox", (PyCFunction)mod_area_from_bbox, METH_VARARGS, NULL},
	{"transform_bbox", (PyCFunction)mod_transform_bbox, METH_VARARGS, NULL},
	{"transform_area", (PyCFunction)mod_transform_area, METH_VARARGS, NULL},
	{NULL} /* sentinel */
};

PyMODINIT_FUNC
INITFUNC(void)
{
    PyObject *m;

	if (PyType_Ready(&PyArea_Type) < 0) return;

    m = Py_InitModule(MODNAME, mod_methods);
    if (!m) return;

	ADD_TYPE(m, "Area", &PyArea_Type);
}
