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

#include "common.h"
#include "_pixbufmodule.h"

#ifndef INITFUNC
#define INITFUNC init_tilemgr
#endif

#ifndef MODNAME
#define MODNAME "_tilemgr"
#endif

#define PyUnboundedTileMgr_Check(op) PyObject_TypeCheck(op, &PyUnboundedTileMgr_Type)
#define PyUnboundedTileMgr_CheckExact(op) ((op)->ob_type == &PyUnboundedTileMgr_Type)

#define PBF_WRITABLE (1<<0)

#define TILE_DEFAULT_SIZE 64

typedef struct PyUnboundedTileMgr_STRUCT {
    PyObject_HEAD

    RWLock *        lock;
    PyObject *      tile_class;
    int             tile_size;
    int             pixfmt;
    u_int           flags;
    PyObject *      tiles; /* dictionnary of tiles, key = tile spacial position */
} PyUnboundedTileMgr;


static PyTypeObject PyUnboundedTileMgr_Type;


/*******************************************************************************************
** Private routines
*/

//+ device_to_tile
static void
device_to_tile(int *x, int *y, int w)
{
    register float tx=*x, ty=*y;

    *x = floorf(tx / w);
    *y = floorf(ty / w);
}
//-
//+ get_tile
static int
get_tile(PyUnboundedTileMgr *self, int tx, int ty, int create, PyObject **tile)
{
    PyObject *key;

    key = PyTuple_New(2);
    if (NULL == key)
        return -1;

    PyTuple_SetItem(key, 0, PyInt_FromLong(tx));
    PyTuple_SetItem(key, 1, PyInt_FromLong(ty));

    if (NULL != PyErr_Occurred())
    {
        Py_DECREF(key);
        return -1;
    }

    *tile = PyDict_GetItem(self->tiles, key); /* BR */
    if (PyErr_Occurred())
    {
        Py_DECREF(key);
        return -1;
    }

    if (NULL == *tile)
    {
        if (create)
        {
            *tile = PyObject_CallFunction(self->tile_class, "IiiI",
                                          self->pixfmt,
                                          tx*self->tile_size,
                                          ty*self->tile_size,
                                          self->tile_size); /* NR */
            if (NULL != *tile)
            {
                if (PyDict_SetItem(self->tiles, key, *tile))
                {
                    Py_DECREF(key);
                    Py_DECREF(*tile);
                    return -1;
                }
            }
            else
            {
                Py_DECREF(key);
                return -1;
            }
        }
    }
    else
        Py_INCREF(*tile);

    Py_DECREF(key);
    return 0;
}
//-


/*******************************************************************************************
** PyUnboundedTileMgr_Type
*/

//+ ubtilemgr_new
static PyObject *
ubtilemgr_new(PyTypeObject *type, PyObject *args)
{
    PyUnboundedTileMgr *self;
    int pixfmt;
    int writable;
    PyObject *tile_class;

    if (!PyArg_ParseTuple(args, "OII:UnboundedTileManager", &tile_class, &pixfmt, &writable)) /* BR */
        return NULL;

    self = (PyUnboundedTileMgr*)type->tp_alloc(type, 0); /* NR */
    if (NULL != self)
    {
        self->tile_size = TILE_DEFAULT_SIZE;
        self->pixfmt = pixfmt;
        self->flags = 0;
        if (writable)
            self->flags |= PBF_WRITABLE;

        self->lock = rwlock_create();
        if (NULL != self->lock)
        {
            self->tiles = PyDict_New();
            if (NULL != self->tiles)
            {
                self->tile_class = tile_class;
                Py_INCREF(tile_class);

                return (PyObject *)self;
            }
            else
                rwlock_destroy(self->lock);
        }
    }

    Py_CLEAR(self);
    return NULL;
}
//-
//+ ubtilemgr_traverse
static int
ubtilemgr_traverse(PyUnboundedTileMgr *self, visitproc visit, void *arg)
{
    Py_VISIT(self->tile_class);
    return 0;
}
//-
//+ ubtilemgr_clear
static int
ubtilemgr_clear(PyUnboundedTileMgr *self)
{
    Py_CLEAR(self->tile_class);
    return 0;
}
//-
//+ ubtilemgr_dealloc
static void
ubtilemgr_dealloc(PyUnboundedTileMgr *self)
{
    ubtilemgr_clear(self);
    rwlock_destroy(self->lock);
    self->ob_type->tp_free((PyObject *)self);
}
//-
//+ ubtilemgr_get_tile
static PyObject *
ubtilemgr_get_tile(PyUnboundedTileMgr *self, PyObject *args)
{
    int tx, ty, create=TRUE;
    PyObject *tile;

    if (!PyArg_ParseTuple(args, "ii|i", &tx, &ty, &create))
        return NULL;

    device_to_tile(&tx, &ty, self->tile_size);

    if (get_tile(self, tx, ty, create, &tile) < 0) /* NR */
        return NULL;

    if (NULL == tile)
        Py_RETURN_NONE;

    return tile;
}
//-
//+ ubtilemgr_set_tile
static PyObject *
ubtilemgr_set_tile(PyUnboundedTileMgr *self, PyObject *args)
{
    int tx, ty, err;
    PyObject *tile, *key;

    if (!PyArg_ParseTuple(args, "Oii", &tile, &tx, &ty))
        return NULL;

    device_to_tile(&tx, &ty, self->tile_size);

    key = PyTuple_New(2);
    if (NULL == key)
        return NULL;

    PyTuple_SetItem(key, 0, PyInt_FromLong(tx));
    PyTuple_SetItem(key, 1, PyInt_FromLong(ty));

    if (NULL != PyErr_Occurred())
    {
        Py_DECREF(key);
        PyErr_SetString(PyExc_RuntimeError, "Failed to create tile key");
        return NULL;
    }

    err = PyDict_SetItem(self->tiles, key, tile);
    Py_DECREF(key);

    if (err)
        return NULL;

    Py_RETURN_NONE;
}
//-
//+ ubtilemgr_get_tiles
static PyObject *
ubtilemgr_get_tiles(PyUnboundedTileMgr *self, PyObject *args)
{
    float fx,fy,fw,fh;
    PyObject *tiles;

    if (!PyArg_ParseTuple(args, "(ffff)", &fx, &fy, &fw, &fh))
        return NULL;

    tiles = PyList_New(0);
    if (NULL != tiles)
    {
        int x, y, w, h;
        register int tx, ty;

        x = floor(fx);
        y = floor(fy);
        w = ceil(fw);
        h = ceil(fh);

        w = x+w-1;
        h = y+h-1;

        device_to_tile(&x, &y, self->tile_size);
        device_to_tile(&w, &h, self->tile_size);

        for (ty=y; ty <= h; ty++)
        {
            for (tx=x; tx <= w; tx++)
            {
                PyObject *tile;
                int res = get_tile(self, tx, ty, FALSE, &tile); /* NR */

                if (res || ((NULL != tile) && PyList_Append(tiles, tile)))
                {
                    Py_DECREF(tiles);
                    return NULL;
                }

                Py_DECREF(tiles);
            }
        }
    }

    return tiles;
}
//-
//+ ubtilemgr_rasterize
static PyObject *
ubtilemgr_rasterize(PyUnboundedTileMgr *self, PyObject *args)
{
    int txmin,txmax,tymin,tymax,tx,ty;
    PyObject *foreach_tile_cb, *options;
    PyObject *ret = NULL;

    if (!PyArg_ParseTuple(args, "(iiii)O!", &txmin, &tymin, &txmax, &tymax, &PyTuple_Type, &options))
        return NULL;

    if (PyTuple_GET_SIZE(options) < 1)
        return PyErr_Format(PyExc_TypeError, "options should have tile callback as first item");

    foreach_tile_cb = PyTuple_GET_ITEM(options, 0); /* BR */

    /* Convert given rectangle from model space to tiles space */
    txmax += txmin-1;
    tymax += tymin-1;
    device_to_tile(&txmin, &tymin, self->tile_size);
    device_to_tile(&txmax, &tymax, self->tile_size);

    /* For each tile in the rastering area */
    for (ty=tymin; ty <= tymax; ty++)
    {
        for (tx=txmin; tx <= txmax; tx++)
        {
            PyObject *result, *tile;

            if (get_tile(self, tx, ty, FALSE, &tile)) /* NR */
                goto bye;

            if (NULL == tile)
                continue;

            /* Trick: replace the cb item by the tile */
            PyTuple_SET_ITEM(options, 0, tile);
            result = PyObject_CallObject(foreach_tile_cb, options); /* NR */
            Py_DECREF(tile);

            if (NULL != result)
                Py_DECREF(result);
            else
                goto bye;
        }
    }

    Py_INCREF(Py_None);
    ret = Py_None;

bye:
    PyTuple_SET_ITEM(options, 0, foreach_tile_cb);
    return ret;
}
//-
//+ ubtilemgr_from_buffer
static PyObject *
ubtilemgr_from_buffer(PyUnboundedTileMgr *self, PyObject *args)
{
    Py_ssize_t size, stride;
    int w,h,txmin,tymin,txmax,tymax,tx,ty;
    int pixfmt;
    char *data;

    if (!PyArg_ParseTuple(args, "Is#IiiII", &pixfmt, &data, &size, &stride, &txmin, &tymin, &w, &h))
        return NULL;

    /* Removes previous data */
    PyDict_Clear(self->tiles);

    /* Convert draw area into touched tiles range */
    txmax = txmin+w-1; tymax = tymin+h-1;
    device_to_tile(&txmin, &tymin, self->tile_size);
    device_to_tile(&txmax, &tymax, self->tile_size);

    for (ty=tymin; ty <= tymax; ty++)
    {
        for (tx=txmin; tx <= txmax; tx++)
        {
            PyObject *result, *tile, *callable;

            /* A tile is created if not exist */
            if (get_tile(self, tx, ty, TRUE, &tile)) /* BR */
                return NULL;

            if (NULL == tile)
                continue;

            Py_INCREF(tile);

            callable = PyObject_GetAttrString(tile, "from_buffer"); /* NR */
            if (NULL == callable)
            {
                Py_DECREF(tile);
                return NULL;
            }

            result = PyObject_Call(callable, args, NULL); /* NR */

            Py_DECREF(tile);
            Py_DECREF(callable);

            if (NULL != result)
                Py_DECREF(result);
            else
                return NULL;
        }
    }

    Py_RETURN_NONE;
}
//-

//+ ubtilemgr_get_bbox
static PyObject *
ubtilemgr_get_bbox(PyUnboundedTileMgr *self, void* closure)
{
    PyObject *key, *tile;
    Py_ssize_t pos;
    int txmin, txmax, tymin, tymax;

    if (0 == PyDict_Size(self->tiles))
        Py_RETURN_NONE;

    txmin = tymin = (-1UL)/2;
    txmax = tymax = -((-1UL)/2 - 1);
    pos = 0;
    while (PyDict_Next(self->tiles, &pos, &key, &tile)) /* BR */
    {
        int tx, ty;

        tx = PyInt_AS_LONG(PyTuple_GET_ITEM(key, 0));
        ty = PyInt_AS_LONG(PyTuple_GET_ITEM(key, 1));

        if (tx < txmin)
            txmin = tx;
        if (tx > txmax)
            txmax = tx;

        if (ty < tymin)
            tymin = ty;
        if (ty > tymax)
            tymax = ty;
    }

    return Py_BuildValue("iiii",
        txmin * self->tile_size,
        tymin * self->tile_size,
        (txmax + 1) * self->tile_size - 1,
        (tymax + 1) * self->tile_size - 1);
}
//-


static struct PyMethodDef ubtilemgr_methods[] = {
    {"get_tile", (PyCFunction)ubtilemgr_get_tile, METH_VARARGS, NULL},
    {"set_tile", (PyCFunction)ubtilemgr_set_tile, METH_VARARGS, NULL},
    {"get_tiles", (PyCFunction)ubtilemgr_get_tiles, METH_VARARGS, NULL},
    {"rasterize", (PyCFunction)ubtilemgr_rasterize, METH_VARARGS, NULL},
    {"from_buffer", (PyCFunction)ubtilemgr_from_buffer, METH_VARARGS, NULL},
    {NULL} /* sentinel */
};

static PyMemberDef ubtilemgr_members[] = {
    {"tiles", T_OBJECT, offsetof(PyUnboundedTileMgr, tiles), 0, NULL},
    {"tile_size", T_INT, offsetof(PyUnboundedTileMgr, tile_size), 0, NULL},
    {NULL} /* sentinel */
};

static PyGetSetDef ubtilemgr_getseters[] = {
    {"bbox", (getter)ubtilemgr_get_bbox, NULL, "Overall bounding box", (void *)0},
    {NULL} /* sentinel */
};

static PyTypeObject PyUnboundedTileMgr_Type = {
    PyObject_HEAD_INIT(NULL)

    tp_name         : "_tilemgr.UnboundedTileManager",
    tp_basicsize    : sizeof(PyUnboundedTileMgr),
    tp_flags        : Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC |  Py_TPFLAGS_BASETYPE,
    tp_doc          : "UnboundedTileManager Objects",

    tp_new          : (newfunc)ubtilemgr_new,
    tp_dealloc      : (destructor)ubtilemgr_dealloc,
    tp_traverse     : (traverseproc)ubtilemgr_traverse,
    tp_clear        : (inquiry)ubtilemgr_clear,
    tp_methods      : ubtilemgr_methods,
    tp_members      : ubtilemgr_members,
    tp_getset       : ubtilemgr_getseters,
};


/*******************************************************************************************
** Module
*/

static PyMethodDef methods[] = {
    {NULL} /* sentinel */
};

//+ add_constants
static int add_constants(PyObject *m)
{
    return 0;
}
//-
//+ INITFUNC()
PyMODINIT_FUNC
INITFUNC(void)
{
    PyObject *m;

    if (PyType_Ready(&PyUnboundedTileMgr_Type) < 0) return;

    m = Py_InitModule(MODNAME, methods);
    if (NULL == m)
        return;

    add_constants(m);

    ADD_TYPE(m, "UnboundedTileManager", &PyUnboundedTileMgr_Type);
}
//-
