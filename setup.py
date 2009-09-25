#!/usr/bin/env python

import glob, os
from distutils.core import setup, Extension

opt = ['-Wall -Wuninitialized -Wstrict-prototypes']

modules = [os.path.splitext(x)[0] for x in glob.glob('*.py')]
modules.remove('setup')

setup(name='Gribouillis',
      version='0.1',
      author='Guillaume Roguez',
      platforms=['morphos'],
      ext_modules = [ Extension('_pixarray', ['_pixarraymodule.c'], extra_compile_args = opt),
                      Extension('_brush', ['_brushmodule.c'], extra_compile_args = opt),
                      Extension('lcms', ['lcmsmodule.c'], extra_compile_args = opt),
                      ],
      py_modules=modules,
      scripts=['Gribouillis'],
      data_files=[('brushes', glob.glob('brushes/*.mpb')
                   + glob.glob('brushes/*.png')
                   + glob.glob('brushes/*.conf'))],
      )
