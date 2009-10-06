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

typedef struct PyLCMS_Profile_STRUCT {
    PyObject_HEAD

    cmsHPROFILE handle;
} PyLCMS_Profile;

typedef struct PyLCMS_Transform_STRUCT {
    PyObject_HEAD

    PyLCMS_Profile * th_hInProfile;
    PyLCMS_Profile * th_hOutProfile;
    cmsHTRANSFORM    th_hTransform;
} PyLCMS_Transform;

static struct Library *LittleCMSBase;
static PyTypeObject PyLCMS_Transform_Type;
static PyTypeObject PyLCMS_Profile_Type;


/*******************************************************************************************
** Private routines
*/

/*******************************************************************************************
** PyLCMS_Profile_Type
*/

//+ lcms_th_new
static PyObject *
profile_new(PyTypeObject *type, PyObject *args)
{
    PyLCMS_Profile *self;
    STRPTR p_name;
    STRPTR mode = "r";

    if (!PyArg_ParseTuple(args, "s|s:__new__", &p_name, &mode)) /* BR */
        return NULL;

    self = (PyLCMS_Profile *)type->tp_alloc(type, 0); /* NR */
    if (NULL != self) {
        self->handle = cmsOpenProfileFromFile(p_name, mode);
        if (NULL == self->handle) {
            PyErr_Format(PyExc_IOError, "Failed to open profile %s with mode '%s'", p_name, mode);
            Py_CLEAR(self);
        }
    }
    
    return (PyObject *)self;
}
//-
//+ profile_dealloc
static void
profile_dealloc(PyLCMS_Profile *self)
{
    if (NULL != self->handle) cmsCloseProfile(self->handle);
    self->ob_type->tp_free((PyObject *)self);
}
//-

static struct PyMethodDef profile_methods[] = {
    {NULL} /* sentinel */
};

static PyTypeObject PyLCMS_Profile_Type = {
    PyObject_HEAD_INIT(NULL)

    tp_name         : "lcms.Profile",
    tp_basicsize    : sizeof(PyLCMS_Profile),
    tp_flags        : Py_TPFLAGS_DEFAULT,
    tp_doc          : "LittleCMS Profile Handle Objects",

    tp_new          : (newfunc)profile_new,
    tp_dealloc      : (destructor)profile_dealloc,
    tp_methods      : profile_methods,
};


/*******************************************************************************************
** PyLCMS_Transform_Type
*/

//+ lcms_th_new
static PyObject *
lcms_th_new(PyTypeObject *type, PyObject *args)
{
    PyLCMS_Transform *self;
    PyLCMS_Profile *ip_obj, *op_obj;
    ULONG ib_type, ob_type, intent, flags=0;

    if (!PyArg_ParseTuple(args, "O!IO!II|I:__new__",
                          &PyLCMS_Profile_Type, &ip_obj, &ib_type,
                          &PyLCMS_Profile_Type, &op_obj, &ob_type,
                          &intent, &flags)) /* BR */
        return NULL;

    self = (PyLCMS_Transform *)type->tp_alloc(type, 0); /* NR */
    if (NULL != self) {
        self->th_hTransform = cmsCreateTransform(ip_obj->handle, ib_type,
                                                 op_obj->handle, ob_type,
                                                 intent, flags);
        if (NULL != self->th_hTransform) {
            self->th_hInProfile = ip_obj; Py_INCREF(ip_obj);
            self->th_hOutProfile = op_obj; Py_INCREF(op_obj);
            return (PyObject *)self;
        } else
            PyErr_SetString(PyExc_SystemError, "Failed to obtain a CMS tranform handler");

        Py_DECREF((PyObject *)self);
    }

    return NULL;
}
//-
//+ lcms_th_dealloc
static void
lcms_th_dealloc(PyLCMS_Transform *self)
{
    Py_CLEAR(self->th_hInProfile);
    Py_CLEAR(self->th_hOutProfile);
    if (NULL != self->th_hTransform)
        cmsDeleteTransform(self->th_hTransform);
    self->ob_type->tp_free((PyObject *)self);
}
//-
//+ lcms_th_apply
static PyObject *
lcms_th_apply(PyLCMS_Transform *self, PyObject *args)
{
    PyObject *o_inbuf, *o_outbuf;
    Py_ssize_t in_len, out_len, pixcnt;
    const void *in_buf;
    void *out_buf;

    if (!PyArg_ParseTuple(args, "OOn", &o_inbuf, &o_outbuf, &pixcnt)) /* BR */
        return NULL;

    if (PyObject_AsReadBuffer(o_inbuf, &in_buf, &in_len))
        return NULL;

    if (PyObject_AsWriteBuffer(o_outbuf, &out_buf, &out_len))
        return NULL;

    /* XXX: I don't care about buffers length here, I should! */
    cmsDoTransform(self->th_hTransform, (APTR)in_buf, out_buf, pixcnt);

    Py_INCREF(o_outbuf);
    return o_outbuf;
}
//-

static struct PyMethodDef lcms_th_methods[] = {
    {NULL} /* sentinel */
};

static PyTypeObject PyLCMS_Transform_Type = {
    PyObject_HEAD_INIT(NULL)

    tp_name         : "lcms.Transform",
    tp_basicsize    : sizeof(PyLCMS_Transform),
    tp_flags        : Py_TPFLAGS_DEFAULT,
    tp_doc          : "LittleCMS Transform Objects",

    tp_new          : (newfunc)lcms_th_new,
    tp_dealloc      : (destructor)lcms_th_dealloc,
    tp_methods      : lcms_th_methods,

    tp_call         : (ternaryfunc)lcms_th_apply,
};


/*******************************************************************************************
** Module
*/

//+ lcms_createprofile
static PyObject *
lcms_createprofile(PyObject *self, PyObject *args)
{
    STRPTR type;
    PyLCMS_Profile *obj;

    if (!PyArg_ParseTuple(args, "z", &type)) /* BR */
        return NULL;

    obj = PyObject_New(PyLCMS_Profile, &PyLCMS_Profile_Type);

    if (NULL == type) {
        type = "NULL"; /* For error msg */
        obj->handle = cmsCreateNULLProfile();
    } else if (!strcmp(type, "sRGB"))
        obj->handle = cmsCreate_sRGBProfile();
    else if (!strcmp(type, "XYZ"))
        obj->handle = cmsCreateXYZProfile();
    else {
        Py_DECREF(obj);
        return PyErr_Format(PyExc_ValueError, "Unsupported profile type: '%s'", type);
    }

    if (NULL == obj->handle) {
        Py_DECREF(obj);
        return PyErr_Format(PyExc_SystemError, "Failed to create %s profile", type);
    }

    return (PyObject *)obj;
}
//-

static PyMethodDef methods[] = {
    {"CreateBuiltinProfile", (PyCFunction)lcms_createprofile, METH_VARARGS, NULL},
    {NULL} /* sentinel */
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
    INSL(m, "FLAGS_BLACKPOINTCOMPENSATION", cmsFLAGS_BLACKPOINTCOMPENSATION);

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

    if (PyType_Ready(&PyLCMS_Profile_Type) < 0) return;
    if (PyType_Ready(&PyLCMS_Transform_Type) < 0) return;

    m = Py_InitModule("lcms", methods);
    if (NULL == m)
        return;

    add_constants(m);

    ADD_TYPE(m, "Profile", &PyLCMS_Profile_Type);
    ADD_TYPE(m, "Transform", &PyLCMS_Transform_Type);
}
//-
