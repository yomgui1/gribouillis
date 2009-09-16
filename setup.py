#!/usr/bin/env python

from distutils.core import setup, Extension

opt = ['-Wall -Wuninitialized -Wstrict-prototypes']

setup(author='Guillaume Roguez',
      platforms=['morphos'],
      ext_modules = [ Extension('_pixbuf', ['_pixbufmodule.c'], extra_compile_args = opt),
                      Extension('_brush', ['_brushmodule.c'], extra_compile_args = opt)
                      ],
      )
