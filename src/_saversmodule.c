/*******************************************************************************
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
*******************************************************************************/

#include "common.h"
#include "_pixbufmodule.h"

#ifdef __MORPHOS__
  #include <libraries/png.h>
  #include <proto/png.h>
#endif

#ifndef __MORPHOS__
  #include <png.h>
  #include <zlib.h>
#endif

#include <stdio.h>
#include <stdlib.h>

#ifndef INITFUNC
#define INITFUNC init_savers
#endif

#ifndef MODNAME
#define MODNAME "_savers"
#endif

static jmp_buf gPNG_JmpBuf;
static png_structp gPNG_png_ptr;
static png_infop gPNG_info_ptr;

static char *gOutputBuffer = NULL;
static Py_ssize_t gOutputAllocLength;
static Py_ssize_t gOutputWriteLength;
static Py_ssize_t gOutputRowIndex;
static Py_ssize_t gOutputRowIndexMax;


/******************************************************************************/

static void
writepng_cleanup(void)
{
	png_destroy_write_struct(&gPNG_png_ptr, &gPNG_info_ptr);
}

static void
writepng_error_handler(png_structp png_ptr, png_const_charp msg)
{
    PyErr_Format(PyExc_SystemError, "[libpng error] %s\n", msg);
	writepng_cleanup();
    longjmp(gPNG_JmpBuf, 1);
}

static int
writepng_encode_finish(void)
{
    if (setjmp(gPNG_JmpBuf))
        return 2;

    png_write_end(gPNG_png_ptr, NULL);
    return 0;
}

static void
mypngwrite(png_structp png_ptr, png_bytep data, png_size_t length)
{
    if (gOutputBuffer)
    {
        if (gOutputWriteLength+length > gOutputAllocLength)
        {
            Py_ssize_t new_length = gOutputAllocLength + MAX(length, 1024);
            char *ptr = malloc(new_length);

            if (ptr)
            {
                gOutputAllocLength = new_length;
                memcpy(ptr, gOutputBuffer, gOutputWriteLength);
            }
            else
                PyErr_NoMemory();

            free(gOutputBuffer);
            gOutputBuffer = ptr;

            if (!gOutputBuffer)
                return;
        }

        memcpy(gOutputBuffer + gOutputWriteLength, data, length);
        gOutputWriteLength += length;
    }
}

static void
mypngflush(png_structp png_ptr)
{
	/* nothing */
}

static int
writepng_init(uint32_t width, uint32_t height)
{
    static struct png_text_struct software = {
        compression:        PNG_TEXT_COMPRESSION_NONE,
        key:                "Software",
        text:               "Made with Gribouillis v3 - MorphOS paint program by Guillaume Roguez",
        text_length:        66,
        itxt_length:        0,
        lang:               NULL,
    };
    int color_type, interlace_type;

    gPNG_png_ptr = png_create_write_struct(PNG_LIBPNG_VER_STRING, gPNG_JmpBuf,
										   writepng_error_handler, NULL);
    if (!gPNG_png_ptr) {
		PyErr_Format(PyExc_MemoryError, "can't allocate the png structure");
        return -1;
	}

	if (setjmp(gPNG_JmpBuf))
        return -1;

    gPNG_info_ptr = png_create_info_struct(gPNG_png_ptr);

    png_set_write_fn(gPNG_png_ptr, NULL, mypngwrite, mypngflush);
    png_set_compression_level(gPNG_png_ptr, Z_DEFAULT_COMPRESSION);

    color_type = PNG_COLOR_TYPE_RGBA;
    interlace_type = PNG_INTERLACE_NONE;

    png_set_IHDR(gPNG_png_ptr, gPNG_info_ptr,
				 width, height, 8, color_type, interlace_type,
				 PNG_COMPRESSION_TYPE_DEFAULT, PNG_FILTER_TYPE_DEFAULT);

    png_set_gAMA(gPNG_png_ptr, gPNG_info_ptr, 2.2); /* FIXME: obtain gamma from system */
    png_set_text(gPNG_png_ptr, gPNG_info_ptr, &software, 1);

    png_write_info(gPNG_png_ptr, gPNG_info_ptr);

    png_set_packing(gPNG_png_ptr);

    return 0;
}

/*************************************************************************************************************/

static PyObject *
mod_png_init(PyObject *self, PyObject *args)
{
	int width, height;

	if (gOutputBuffer)
		return PyErr_Format(PyExc_SystemError, "PNG saver is busy");

    if (!PyArg_ParseTuple(args, "II", &width, &height))
        return NULL;

	gOutputBuffer = calloc(1024, 1);
    if (gOutputBuffer)
    {
        gOutputWriteLength = 0;
        gOutputAllocLength = 1024;
		gOutputRowIndex = 0;
		gOutputRowIndexMax = height;

		if (!writepng_init(width, height)) {
			Py_RETURN_NONE;
		} else
			free(gOutputBuffer);
	} else
        return PyErr_Format(PyExc_IOError, "Can't allocate the output string");

	gOutputBuffer = NULL;
	return NULL;
}

static PyObject *
mod_png_fini(PyObject *self)
{
	PyObject *output = NULL;

	if (!gOutputBuffer)
		return PyErr_Format(PyExc_SystemError, "PNG saver not initialized yet");

	if (!writepng_encode_finish())
		output = PyString_FromStringAndSize(gOutputBuffer, gOutputWriteLength); /* NR */

	free(gOutputBuffer);
	gOutputBuffer = NULL;

	return output;
}

static PyObject *
mod_png_write_row(PyObject *self, PyObject *args)
{
	char *row_pointer;
	int length;

	if (!gOutputBuffer)
		return PyErr_Format(PyExc_SystemError, "PNG saver not initialized yet");

	if (!gOutputRowIndex >= gOutputRowIndexMax)
		return PyErr_Format(PyExc_SystemError, "max row count reached, please call png_fini");

	if (!PyArg_ParseTuple(args, "t#", &row_pointer, &length))
        return NULL;

	if (setjmp(gPNG_JmpBuf)) {
		free(gOutputBuffer);
		gOutputBuffer = NULL;
		return NULL;
	}

	png_write_row(gPNG_png_ptr, row_pointer);
	return PyInt_FromLong(gOutputRowIndex++);
}

static PyObject *
mod_save_pixbuf_as_png_buffer(PyObject *self, PyObject *args)
{
    PyPixbuf *pixbuf;
	PyObject *output = NULL;

	if (gOutputBuffer)
		return PyErr_Format(PyExc_SystemError, "PNG saver is busy with a pixbuf");

    if (!PyArg_ParseTuple(args, "O!", PyPixbuf_Type, &pixbuf))
        return NULL;

    gOutputBuffer = calloc(1024, 1);
    if (NULL != gOutputBuffer)
    {
        gOutputWriteLength = 0;
        gOutputAllocLength = 1024;

        if (!writepng_init(pixbuf->width, pixbuf->height))
        {
            uint32_t y;

			if (setjmp(gPNG_JmpBuf))
				goto out;

            for (y=0; y < pixbuf->height; y++)
                png_write_row(gPNG_png_ptr, &pixbuf->data[y*pixbuf->bpr]);

            if (writepng_encode_finish())
				goto out;

            writepng_cleanup();
			output = PyString_FromStringAndSize(gOutputBuffer, gOutputWriteLength); /* NR */
        }
    }
    else
        PyErr_Format(PyExc_MemoryError, "Can't allocate the output string");

out:
	free(gOutputBuffer);
	gOutputBuffer = NULL;
	return output;
}

static PyMethodDef methods[] = {
	{"png_init", (PyCFunction)mod_png_init, METH_VARARGS, NULL},
	{"png_fini", (PyCFunction)mod_png_fini, METH_NOARGS, NULL},
	{"png_write_row", (PyCFunction)mod_png_write_row, METH_VARARGS, NULL},
    {"save_pixbuf_as_png_buffer", (PyCFunction)mod_save_pixbuf_as_png_buffer, METH_VARARGS, NULL},
    {NULL} /* sentinel */
};

PyMODINIT_FUNC
INITFUNC(void)
{
    PyObject *m;

    m = Py_InitModule(MODNAME, methods);
    if (NULL == m)
        return;

    if (!import_pixbuf())
        return;
}

