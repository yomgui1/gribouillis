#include "common.h"

#include <cybergraphx/cybergraphics.h>

#include <proto/graphics.h>
#include <proto/cybergraphics.h>

#define PyPixelArray_Check(op) PyObject_TypeCheck(op, &PyPixelArray_Type)
#define PyPixelArray_CheckExact(op) ((op)->ob_type == &PyPixelArray_Type)

#define CACHE_SIZE 16

typedef struct PyPixelArray_STRUCT {
    PyObject_HEAD

    UWORD width, height; /* Pixels array size */
    UBYTE nc;            /* Number of components per pixels */
    UBYTE bpc;           /* Number of bits for each components */
    ULONG bpr;           /* Number of bytes per row */
    APTR  data;         /* Pixels data */
} PyPixelArray;

static struct Library *MUIMasterBase;
static struct Library *CyberGfxBase;
static PyTypeObject PyPixelArray_Type;

/*******************************************************************************************
** Private routines
*/

/* About color format in buffers.
 *
 * Pixels colors are stored as 4 componants (RGBA or YUVA) using fixed point encoding.
 * So the floating point range [0.0, 1.0] is converted into integer range [0, 2**15].
 * Using 2**15 than a more natural 2**16 value gives the way to store the 1.0 value
 * into a short integer (16bits) and permit to use a logical shift operation of 15 bits,
 * when we need to multiply/divide values in fixed-point arithmetic computations.
 *
 * In all the application I'll note rgba15x a RGBA pixel buffer using this convention.
 */

//+ rgba15x_to_rgba8
static void
rgba15x_to_rgba8(USHORT *src, UBYTE *dst, UWORD w, UWORD h)
{
    ULONG i, n = w * h;

    for (i=0; i < n; i++) {
        dst[0] = (ULONG)src[0] * 255 >> 15;
        dst[1] = (ULONG)src[1] * 255 >> 15;
        dst[2] = (ULONG)src[2] * 255 >> 15;
        dst[3] = (ULONG)src[3] * 255 >> 15;
        
        src += 4;
        dst += 4;
    }
}
//-
//+ rgba15x_to_rgb8
static void
rgba15x_to_rgb8(USHORT *src, UBYTE *dst, UWORD w, UWORD h)
{
    ULONG i, n = w * h;

    for (i=0; i < n; i++) {
        ULONG alpha = src[3];

        dst[0] = (ULONG)src[0] * 255 / alpha;
        dst[1] = (ULONG)src[1] * 255 / alpha;
        dst[2] = (ULONG)src[2] * 255 / alpha;
        
        dst += 3;
        src += 4;
    }
}
//-
//+ rgba8_to_rgba15x
static void
rgba8_to_rgba15x(UBYTE *src, USHORT *dst, UWORD w, UWORD h)
{
    ULONG i, n = w * h;

    for (i=0; i < n; i++) {
        USHORT alpha = ((ULONG)src[3] << 15) / 255;
        
        dst[0] = (ULONG)src[0] * alpha / 255;
        dst[1] = (ULONG)src[1] * alpha / 255;
        dst[2] = (ULONG)src[2] * alpha / 255;
        dst[3] = alpha;

        src += 4;
        dst += 4;
    }
}
//-
//+ blit_overalpha_rgba15x_to_rgb8
static void
blit_overalpha_rgba15x_to_rgb8(USHORT *src, UBYTE *dst, UWORD w, UWORD h)
{
    ULONG i, n = w * h;

    // src is a rgba15x with alpha pre-multiplied rgb values.
    // dst is not alpha premul.

    for (i=0; i < n; i++) {
        // DestAlpha = 1.0 (full opaque surface)
        // Dest[x] = Src[x] + (1.0 - SrcAlpha) * Dst[x]
        ULONG alpha = src[4];
        ULONG one_minus_alpha = (1 << 15) - alpha;

        dst[0] = (ULONG)src[0] * 255 / alpha + (one_minus_alpha * dst[0] >> 15);
        dst[1] = (ULONG)src[1] * 255 / alpha + (one_minus_alpha * dst[1] >> 15);
        dst[2] = (ULONG)src[2] * 255 / alpha + (one_minus_alpha * dst[2] >> 15);

        src += 4;
        dst += 3;
    }
}
//-


/*******************************************************************************************
** PyPixelArray_Type
*/

//+ pixarray_new
static PyObject *
pixarray_new(PyTypeObject *type, PyObject *args)
{
    PyPixelArray *self;
    UWORD w, h;
    UBYTE nc, bpc;

    if (!PyArg_ParseTuple(args, "HHBB:__new__", &w, &h, &nc, &bpc)) /* BR */
        return NULL;

    if (nc > 4)
        return PyErr_Format(PyExc_ValueError, "PixelArray support 4 composants at maximum, not %u", nc);

    if (bpc > 32)
        return PyErr_Format(PyExc_ValueError, "PixelArray support 32 bits per composant at maximum, not %u", bpc);

    if ((nc * bpc) % 8)
        return PyErr_Format(PyExc_ValueError, "PixelArray needs the number of components by the number of bit per component aligned on byte size");
 

    self = (PyPixelArray *)type->tp_alloc(type, 0); /* NR */
    if (NULL != self) {
        self->bpr = w * ((bpc * nc) >> 3); 
        self->data = PyMem_Malloc(self->bpr * h);
        if (NULL != self->data) {
            self->width = w;
            self->height = h;
            self->nc  = nc;
            self->bpc = bpc;
            return (PyObject *)self;
        }

        Py_DECREF((PyObject *)self);
    }

    return NULL;
}
//-
//+ pixarray_dealloc
static void
pixarray_dealloc(PyPixelArray *self)
{
    PyMem_Free(self->data);
    self->ob_type->tp_free((PyObject *)self);
}
//-
//+ pixarray_getsegcount
static Py_ssize_t
pixarray_getsegcount(PyPixelArray *self, Py_ssize_t *lenp)
{
    if (NULL != lenp)
        *lenp = self->bpr * self->height;
    return 1;
}
//-
//+ pixarray_getbuffer
static Py_ssize_t
pixarray_getbuffer(PyPixelArray *self, Py_ssize_t segment, void **ptrptr)
{
    if (segment != 0) {
        PyErr_SetString(PyExc_TypeError, "Only segment 0 is allowed");
        return -1;
    }

    *ptrptr = self->data;
    return self->bpr * self->height;
}
//-
//+ pixarray_zero
static PyObject *
pixarray_zero(PyPixelArray *self)
{
    memset(self->data, 0, self->bpr * self->height);
    Py_RETURN_NONE;
}
//-
//+ pixarray_fromstring
static PyObject *
pixarray_fromstring(PyPixelArray *self, PyObject *string)
{
    Py_ssize_t len;

    if (!PyString_CheckExact(string))
        return PyErr_Format(PyExc_TypeError, "str object needed as first argument, not %s", OBJ_TNAME(string));

    len = MIN(PyString_GET_SIZE(string), self->bpr * self->height);
    CopyMem(PyString_AS_STRING(string), self->data, len);
    
    Py_RETURN_NONE;
}
//-
//+ pixarray_rgba8torgba15x
/* XXX: should be a module method! */
static PyObject *
pixarray_rgba8torgba15x(PyPixelArray *self, PyPixelArray *rgba8)
{
    if (!PyPixelArray_Check(rgba8))
        return PyErr_Format(PyExc_TypeError, "Instance of PixelArray type needed as first argument, not %s", OBJ_TNAME(rgba8));

    if ((self->nc != 4) || (self->bpc != 16))
        return PyErr_Format(PyExc_TypeError, "Incompatible source PixelArray object");
    
    if ((rgba8->nc != 4) || (rgba8->bpc != 8))
        return PyErr_Format(PyExc_TypeError, "Incompatible destination PixelArray object");

    if ((self->width != rgba8->width) || (self->height != rgba8->height))
        return PyErr_Format(PyExc_TypeError, "Incompatible dimensions between given PixelArray objects");

    rgba8_to_rgba15x(rgba8->data, self->data, self->width, self->height);
    
    Py_RETURN_NONE;
}
//-
#if 0
//+ pixarray_set_component
static PyObject *
pixarray_set_component(PyPixelArray *self, PyObject *args)
{
    ULONGLONG *ptr, *end, v2, mask2;
    UBYTE n;
    ULONG v, mask, add;
    int shift;

    if (!PyArg_ParseTuple(args, "BI", &n, &v))
        return NULL;

    if (n >= self->nc)
        return PyErr_Format(PyExc_ValueError, "component number shall be less than %u", self->nc);


    Py_RETURN_NONE;
}
//-
#endif

static struct PyMethodDef pixarray_methods[] = {
    {"zero", (PyCFunction)pixarray_zero, METH_VARARGS, NULL},
    {"from_string", (PyCFunction)pixarray_fromstring, METH_O, NULL},
    {"rgba8_to_rgba15x", (PyCFunction)pixarray_rgba8torgba15x, METH_O, NULL},
    //{"set_component", (PyCFunction)pixarray_set_component, METH_VARARGS, NULL},
    {NULL} /* sentinel */
};

static PyMemberDef pixarray_members[] = {
    {"Width", T_USHORT, offsetof(PyPixelArray, width), RO, NULL},
    {"Height", T_USHORT, offsetof(PyPixelArray, height), RO, NULL},
    {"BytesPerRow", T_ULONG, offsetof(PyPixelArray, bpr), RO, NULL},
    {"ComponentNumber", T_UBYTE, offsetof(PyPixelArray, nc), RO, NULL},
    {"BitsPerComponent", T_UBYTE, offsetof(PyPixelArray, bpc), RO, NULL},
    {"DataAddress", T_ULONG, offsetof(PyPixelArray, data), RO, NULL},
    {NULL}
};

static PyBufferProcs pixarray_as_buffer = {
    bf_getreadbuffer  : (getreadbufferproc)pixarray_getbuffer,
    bf_getwritebuffer : (getwritebufferproc)pixarray_getbuffer,
    bf_getsegcount    : (getsegcountproc)pixarray_getsegcount,
};

static PyTypeObject PyPixelArray_Type = {
    PyObject_HEAD_INIT(NULL)

    tp_name         : "_surface.PixelArray",
    tp_basicsize    : sizeof(PyPixelArray),
    tp_flags        : Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    tp_doc          : "PixelArray Objects",

    tp_new          : (newfunc)pixarray_new,
    tp_dealloc      : (destructor)pixarray_dealloc,
    tp_methods      : pixarray_methods,
    tp_members      : pixarray_members,
    tp_as_buffer    : &pixarray_as_buffer,
};


/*******************************************************************************************
** Module
*/

//+ mod_renderfull
static PyObject *mod_renderfull(PyObject *self, PyObject *args)
{
    PyObject *meth_getbuf;
    Object *mo;
    ULONG size;
    DOUBLE sx, sy, scale;
    struct RastPort rp;
    register ULONG i, j, rw;
    APTR tmp_buf8;
    struct BitMap *bm = NULL;

    if (!PyArg_ParseTuple(args, "IOIddd:render", &mo, &meth_getbuf, &size, &scale, &sx, &sy)) /* BR */
        return NULL;

    if (NULL == mo) {
        PyErr_SetString(PyExc_ValueError, "NULL Object address given");
        return NULL;
    }

    if (NULL == _rp(mo)) {
        PyErr_SetString(PyExc_TypeError, "NULL RastPort");
        return NULL;
    }

    tmp_buf8 = PyMem_Malloc(3*size*size);
    if (NULL == tmp_buf8)
        return PyErr_Format(PyExc_MemoryError, "No enough memory to allocated destination buffer");

    bm = AllocBitMap(_mwidth(mo), _mheight(mo), 24, BMF_CLEAR|BMF_DISPLAYABLE, NULL);
    if (NULL == bm) {
        PyErr_SetString(PyExc_SystemError, "AllocBitMap() failed");
        goto err;
    }

    InitRastPort(&rp);
    rp.BitMap = bm;

    rw = (_mwidth(mo) + scale) / scale;
    for (j=0; j < (ULONG)((_mheight(mo) + scale) / scale); j += size) {
        for (i=0; i < rw; i += size) {
            PyPixelArray *bufobj = (APTR)PyObject_CallFunction(meth_getbuf, "dd", sx + i, sy + j); /* NR */
            FLOAT tx, ty;

            if (NULL == bufobj)
                goto err;
            if (Py_None == (APTR)bufobj)
                continue;
            if ((bufobj->width != size) || (bufobj->width != size)) {
                Py_DECREF(bufobj);
                PyErr_SetString(PyExc_TypeError, "Incompatible PixelArray");
                goto err;
            }

            //blit_overalpha_rgba15x_to_rgb8(bufobj->data, tmp_rgba8, size, size);
            rgba15x_to_rgb8(bufobj->data, tmp_buf8, size, size);

            tx = (i - sx) * scale;
            ty = (j - sy) * scale;
            ScalePixelArray(tmp_buf8, size, size, 3*size, &rp, _mleft(mo)+(ULONG)tx, _mtop(mo)+(ULONG)ty, (ULONG)(size*scale), (ULONG)(size*scale), RECTFMT_RGB);

            Py_DECREF(bufobj);
        }
    }

    BltBitMapRastPort(bm, 0, 0, _rp(mo), _mleft(mo), _mtop(mo), _mwidth(mo), _mheight(mo), ABC);

    FreeBitMap(bm);
    PyMem_Free(tmp_buf8);
    Py_RETURN_NONE;  

err:
    if (NULL != bm) FreeBitMap(bm);
    if (NULL != tmp_buf8) PyMem_Free(tmp_buf8);
    return NULL;
}
//-
//+ mod_rgba8_to_rgba15
static PyObject *
mod_rgba8_to_rgba15(PyObject *self, PyObject *args)
{
    //if (!PyArg_ParseTuple())
    //    return NULL;

    Py_RETURN_NONE;
}
//-

//+ methods
static PyMethodDef methods[] = {
    {"renderfull", (PyCFunction)mod_renderfull, METH_VARARGS, NULL},
    {0}
};
//-

//+ add_constants
static int add_constants(PyObject *m)
{
    return 0;
}
//-
//+ PyMorphOS_CloseModule
void
PyMorphOS_CloseModule(void) {

    if (NULL != CyberGfxBase) {
        CloseLibrary(CyberGfxBase);
        CyberGfxBase = NULL;
    }

    if (NULL != MUIMasterBase) {
        CloseLibrary(MUIMasterBase);
        MUIMasterBase = NULL;
    }
}
//- PyMorphOS_CloseModule
//+ init_surface
void init_surface(void)
{
    PyObject *m;

    MUIMasterBase = OpenLibrary(MUIMASTER_NAME, MUIMASTER_VLATEST);
    if (NULL == MUIMasterBase)
        return;

    CyberGfxBase = OpenLibrary("cybergraphics.library", 50);
    if (NULL == CyberGfxBase)
        return;

    if (PyType_Ready(&PyPixelArray_Type) < 0) return;

    m = Py_InitModule("_surface", methods);
    if (NULL == m)
        return;

    add_constants(m);

    ADD_TYPE(m, "PixelArray", &PyPixelArray_Type);
}
//-
