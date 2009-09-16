#!/usr/bin/env python

from distutils.core import setup, Extension

opt = ['-Wall -Wuninitialized -Wstrict-prototypes']

setup(author='Guillaume Roguez',
      platforms=['morphos'],
      ext_modules = [Extension('_raster', ['_rastermodule.c'], extra_compile_args = opt)],
      )
