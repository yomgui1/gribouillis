/******************************************************************************
Copyright (c) 2009 Guillaume Roguez

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

#include <proto/littlecms.h>

#ifndef INITFUNC
#define INITFUNC initlcms
#endif

typedef struct PyLCMS_TransformHandler_STRUCT {
    PyObject_HEAD

    cmsHPROFILE     th_hInProfile;
    cmsHPROFILE     th_hOutProfile;
    cmsHTRANSFORM   th_hTransform;
} PyLCMS_TransformHandler;

static struct Library *LittleCMSBase;
static PyTypeObject PyLCMS_TransformHandler_Type;


/*******************************************************************************************
** Private routines
*/


/*******************************************************************************************
** PyLCMS_TransformHandler_Type
*/

//+ lcms_th_new
static PyObject *
lcms_th_new(PyTypeObject *type, PyObject *args)
{
    PyLCMS_TransformHandler *self;
    STRPTR ip_name, op_name;
    ULONG ib_type, ob_type, intent, flags=0;

    if (!PyArg_ParseTuple(args, "sIsII|I:__new__", &ip_name, &ib_type, &op_name, &ob_type, &intent, &flags)) /* BR */
        return NULL;

    //dprintf("ip: '%s', op='%s'\n", ip_name, op_name);

    if ((strlen(ip_name) == 0) || (strlen(op_name) == 0))
        return PyErr_Format(PyExc_TypeError, "Empty profile name given");

    self = (PyLCMS_TransformHandler *)type->tp_alloc(type, 0); /* NR */
    if (NULL != self) {
        self->th_hInProfile = cmsOpenProfileFromFile(ip_name, "r");
        //dprintf("inprofile = %p\n", self->th_hInProfile);
        if (NULL != self->th_hInProfile) {
            self->th_hOutProfile = cmsOpenProfileFromFile(op_name, "r");
            //dprintf("outprofile = %p\n", self->th_hOutProfile);
            if (NULL != self->th_hOutProfile) {
                self->th_hTransform = cmsCreateTransform(self->th_hInProfile, ib_type,
                                                         self->th_hOutProfile, ob_type,
                                                         intent, flags);
                //dprintf("transfom = %p\n", self->th_hTransform);
                if (NULL != self->th_hTransform)
                    return (PyObject *)self;
                else
                    PyErr_SetString(PyExc_SystemError, "Failed to obtain a CMS tranform handler");
            } else
                PyErr_Format(PyExc_SystemError, "Failed to open the output profile %s", op_name);
        } else
            PyErr_Format(PyExc_SystemError, "Failed to open the input profile %s", ip_name);

        Py_DECREF((PyObject *)self);
    }

    return NULL;
}
//-
//+ lcms_th_dealloc
static void
lcms_th_dealloc(PyLCMS_TransformHandler *self)
{
    if (NULL != self->th_hTransform) cmsDeleteTransform(self->th_hTransform);
    if (NULL != self->th_hOutProfile) cmsCloseProfile(self->th_hOutProfile);
    if (NULL != self->th_hInProfile) cmsCloseProfile(self->th_hInProfile);
    self->ob_type->tp_free((PyObject *)self);
}
//-
//+ lcms_th_apply
static PyObject *
lcms_th_apply(PyLCMS_TransformHandler *self, PyObject *args)
{
    Py_ssize_t in_len, out_len, pixcnt;
    APTR in_buf, out_buf;

    if (!PyArg_ParseTuple(args, "s#s#n", &in_buf, &in_len, &out_buf, &out_len, &pixcnt))
        return NULL;

    /* XXX: I don't care about length here, should I do ? */

    //dprintf("apply: src=%p, dst=%p (pixcnt=%lu)\n", in_buf, out_buf, out_len);
    cmsDoTransform(self->th_hTransform, in_buf, out_buf, pixcnt);

    Py_RETURN_NONE;
}
//-

static struct PyMethodDef lcms_th_methods[] = {
    {"apply", (PyCFunction)lcms_th_apply, METH_VARARGS, NULL},
    {NULL} /* sentinel */
};

static PyTypeObject PyLCMS_TransformHandler_Type = {
    PyObject_HEAD_INIT(NULL)

    tp_name         : "lcms.TransformHandler",
    tp_basicsize    : sizeof(PyLCMS_TransformHandler),
    tp_flags        : Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    tp_doc          : "LittleCMS TransformHandler Objects",

    tp_new          : (newfunc)lcms_th_new,
    tp_dealloc      : (destructor)lcms_th_dealloc,
    tp_methods      : lcms_th_methods,
};


/*******************************************************************************************
** Module
*/

static PyMethodDef methods[] = {
    {0}
};

//+ add_constants
static int add_constants(PyObject *m)
{
    INSL(m, "TYPE_RGB_8", TYPE_RGB_8);
    INSL(m, "TYPE_ARGB_8", TYPE_ARGB_8);
    INSI(m, "INTENT_PERCEPTUAL", INTENT_PERCEPTUAL);
    INSI(m, "INTENT_RELATIVE_COLORIMETRIC", INTENT_RELATIVE_COLORIMETRIC);
    INSI(m, "INTENT_SATURATION", INTENT_SATURATION);
    INSI(m, "INTENT_ABSOLUTE_COLORIMETRIC", INTENT_ABSOLUTE_COLORIMETRIC);

    return 0;
}
//-
//+ PyMorphOS_CloseModule
void
PyMorphOS_CloseModule(void)
{
    if (NULL != LittleCMSBase) {
        CloseLibrary(LittleCMSBase);
        LittleCMSBase = NULL;
    }
}
//- PyMorphOS_CloseModule
//+ INITFUNC()
PyMODINIT_FUNC
INITFUNC(void)
{
    PyObject *m;

    LittleCMSBase = OpenLibrary("littlecms.library", 3);
    if (NULL == LittleCMSBase)
        return;

    if (PyType_Ready(&PyLCMS_TransformHandler_Type) < 0) return;

    m = Py_InitModule("lcms", methods);
    if (NULL == m)
        return;

    add_constants(m);

    ADD_TYPE(m, "TransformHandler", &PyLCMS_TransformHandler_Type);
}
//-
