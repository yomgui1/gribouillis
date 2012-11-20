/******************************************************************************
Copyright (c) 2009-2012 Guillaume Roguez

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

#include <proto/tinygl.h>
#include <graphics/rastport.h>

#ifndef INITFUNC
#define INITFUNC init_glbackend
#endif

#ifndef MODNAME
#define MODNAME "_glbackend"
#endif

#define	checkImageWidth 64
#define	checkImageHeight 64

GLContext *tgl_context=NULL;
struct BitMap *gBitMap=NULL;
static UWORD gWidth, gHeight;
static GLuint gTexID = -1;
static GLint gMaxTexWidth = 0;

static void draw_rect_tex(GLuint texid,
    GLfloat x, GLfloat y, GLfloat w, GLfloat h,
    GLfloat tx, GLfloat ty, GLfloat tw, GLfloat th)
{
    glBegin(GL_QUADS);
    glTexCoord2f(tx,    ty+th); glVertex2f(x,     y    );
    glTexCoord2f(tx+tw, ty+th); glVertex2f(x+w-1, y    );
    glTexCoord2f(tx+tw, ty   ); glVertex2f(x+w-1, y+h-1);
    glTexCoord2f(tx,    ty   ); glVertex2f(x,     y+h-1);
    glEnd();
}

static PyObject* mod_initglcontext(PyObject *self, PyObject *args)
{
    struct RastPort *rp;
    UWORD width, height;
    
    if (!PyArg_ParseTuple(args, "kHH", &rp, &width, &height))
        return NULL;
     
    if (!GLAInitializeContextBitMap(tgl_context, rp->BitMap))
    {
        PyErr_SetString(PyExc_SystemError, "GLAInitializeContextBitMap() failed");
        return NULL;
    }
    
    glGetIntegerv(GL_MAX_TEXTURE_SIZE, &gMaxTexWidth);
    dprintf("max tex width=%u\n", gMaxTexWidth);
    //gMaxTexWidth = 1024;
    
    gBitMap = rp->BitMap;
    
    if (gTexID != -1)
        glDeleteTextures(1, &gTexID);

    glGenTextures(1, &gTexID);
    
    gWidth = width;
    gHeight = height;
    
    /* 2D setup */
    glViewport(0, 0, width, height);
    glMatrixMode(GL_PROJECTION);
    glLoadIdentity();
    glOrtho(0.0, width-1, 0.0, height-1, -1, 1);
    glMatrixMode(GL_MODELVIEW);
    glLoadIdentity();
    glTranslatef(0.375, 0.375, 0.0);
    
    glDisable(GL_BLEND);
    glDisable(GL_DEPTH_TEST);
    glEnable(GL_CULL_FACE);
    glShadeModel(GL_FLAT);
    
    glEnable(GL_TEXTURE_2D);
    glBindTexture(GL_TEXTURE_2D, gTexID);

    glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
    glTexEnvf(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_REPLACE);

    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, gMaxTexWidth, gMaxTexWidth, 0, GL_RGBA, GL_UNSIGNED_BYTE, NULL);
    
    glClearColor(.66, .66, .66, 1.0);
    glClear(GL_COLOR_BUFFER_BIT);

    Py_RETURN_NONE;
}

static PyObject* mod_termglcontext(PyObject *self, PyObject *args)
{
    if (tgl_context && gBitMap)
    {
        GLADestroyContextBitMap(tgl_context);
        gBitMap = NULL;
    }

    if (gTexID != -1)
    {
        glDeleteTextures(1, &gTexID);
        gTexID = -1;
    }

    Py_RETURN_NONE;
}

static PyObject* mod_blit_pixbuf(PyObject *self, PyObject *args)
{
    GLuint x, y, width, height;
    char *data;
    Py_ssize_t length;
    
    if (!PyArg_ParseTuple(args, "s#IIII", &data, &length, &x, &y, &width, &height))
        return NULL;
    
    if (gTexID == -1)
    {
        PyErr_SetString(PyExc_SystemError, "Texture is not initialized yet");
        return NULL;
    }
    
    glPixelStorei(GL_UNPACK_ROW_LENGTH, gWidth);
    glTexSubImage2D(GL_TEXTURE_2D, 0, x, y, width, height, GL_RGBA, GL_UNSIGNED_BYTE, data + y*gWidth*4 + x*4);
    draw_rect_tex(gTexID, 0, 0, gWidth/2, gHeight/2, 0.0, 0.0, gWidth/(float)gMaxTexWidth, gHeight/(float)gMaxTexWidth);

    Py_RETURN_NONE;
}

static PyMethodDef methods[] = {
    {"init_gl_context", (PyCFunction)mod_initglcontext, METH_VARARGS, NULL},
    {"term_gl_context", (PyCFunction)mod_termglcontext, METH_NOARGS, NULL},
    {"blit_pixbuf", (PyCFunction)mod_blit_pixbuf, METH_VARARGS, NULL},
    {NULL} /* sentinel */
};

static int add_constants(PyObject *m)
{
    //INSI(m, "FLAG_RGB", PyPixbuf_FLAG_RGB);

    return 0;
}

void
PyMorphOS_TermModule(void)
{
    if (tgl_context)
    {
        if (gTexID != -1)
            glDeleteTextures(1, &gTexID);
        GLClose(tgl_context);
        tgl_context = __tglContext = NULL;
    }
    
    if (TinyGLBase) {
        CloseLibrary(TinyGLBase);
        TinyGLBase = NULL;
    }
}

PyMODINIT_FUNC
INITFUNC(void)
{
    PyObject *m;

    TinyGLBase = OpenLibrary("tinygl.library", 50);
    if (TinyGLBase)
    {
        tgl_context = __tglContext = GLInit();
        if (tgl_context)
        {
            m = Py_InitModule(MODNAME, methods);
            if (m)
            {
                add_constants(m);
                return;
            }
            
            GLClose(tgl_context);
        }

        CloseLibrary(TinyGLBase);
    }
}
