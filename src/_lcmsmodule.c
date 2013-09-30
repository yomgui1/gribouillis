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

#include <lcms2.h>
#include <wchar.h>

#ifndef INITFUNC
#define INITFUNC init_lcms
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

struct Library *LittleCMSBase;
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
    char *p_name;
    char *mode = "r";

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
#if 0
//+ profile_get_productname
static PyObject *
profile_get_productname(PyLCMS_Profile *self, void *closure)
{
    return Py_BuildValue("z", cmsTakeProductName(self->handle));
}
//-
//+ profile_get_productdesc
static PyObject *
profile_get_productdesc(PyLCMS_Profile *self, void *closure)
{
    wchar_t s[LCMS_DESC_MAX/sizeof(wchar_t)];
    int l;

    l = cmsReadICCTextEx(self->handle, icSigDescription, (char *)s, sizeof(s));
    if (l > 0)
        return PyString_FromStringAndSize((Py_UNICODE *)s, l);
    Py_RETURN_NONE;
}
//-
//+ profile_get_productinfo
static PyObject *
profile_get_productinfo(PyLCMS_Profile *self, void *closure)
{
    return Py_BuildValue("z", cmsTakeProductInfo(self->handle));
}
//-
#else
//+ profile_get_desc
static PyObject *
profile_get_desc(PyLCMS_Profile *self, void *closure)
{
    wchar_t buf[512];
    int l;

    bzero(buf, 512);
    l = cmsGetProfileInfo(self->handle, cmsInfoDescription,
                          "EN", "US",
                          buf, sizeof(buf));
    if (l > 0)
        return Py_BuildValue("u", buf);

    Py_RETURN_NONE;
}
//-
#endif

static struct PyMethodDef profile_methods[] = {
    {NULL} /* sentinel */
};

static PyGetSetDef profile_getsetters[] = {
    //{"ProductName", (getter)profile_get_productname, NULL, "Product Name", NULL},
    {"Description", (getter)profile_get_desc, NULL, "Description", NULL},
    //{"ProductInfo", (getter)profile_get_productinfo, NULL, "Product Info", NULL},

    {NULL} /* sentinel */
};

static PyTypeObject PyLCMS_Profile_Type = {
    PyObject_HEAD_INIT(NULL)

    tp_name         : "_lcms.Profile",
    tp_basicsize    : sizeof(PyLCMS_Profile),
    tp_flags        : Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    tp_doc          : "LittleCMS Profile Handle Objects",

    tp_new          : (newfunc)profile_new,
    tp_dealloc      : (destructor)profile_dealloc,
    tp_methods      : profile_methods,
    tp_getset       : profile_getsetters,
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
    uint32_t ib_type, ob_type, intent, flags=0;

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
    Py_ssize_t in_len, out_len, pixcnt;
    const void *in_buf;
    void *out_buf;

    if (!PyArg_ParseTuple(args, "s#w#n", &in_buf, &in_len, &out_buf, &out_len, &pixcnt)) /* BR */
        return NULL;

    cmsDoTransform(self->th_hTransform, (void *)in_buf, out_buf, pixcnt);

    Py_RETURN_NONE;
}
//-

static struct PyMethodDef lcms_th_methods[] = {
    {NULL} /* sentinel */
};

static PyTypeObject PyLCMS_Transform_Type = {
    PyObject_HEAD_INIT(NULL)

    tp_name         : "_lcms.Transform",
    tp_basicsize    : sizeof(PyLCMS_Transform),
    tp_flags        : Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
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
    char *type;
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

//+ INITFUNC()
PyMODINIT_FUNC
INITFUNC(void)
{
    PyObject *m;

    if (PyType_Ready(&PyLCMS_Profile_Type) < 0) return;
    if (PyType_Ready(&PyLCMS_Transform_Type) < 0) return;

    m = Py_InitModule("_lcms", methods);
    if (NULL == m)
        return;

    add_constants(m);

    ADD_TYPE(m, "Profile", &PyLCMS_Profile_Type);
    ADD_TYPE(m, "Transform", &PyLCMS_Transform_Type);
}
//-
