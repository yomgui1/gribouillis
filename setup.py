#!/usr/bin/env python

import glob, os
from distutils.core import setup, Extension

opt = ['-Wall -Wuninitialized -Wstrict-prototypes']

modules = [os.path.splitext(x)[0] for x in glob.glob('*.py')]
modules.remove('setup')

extra_data = []
for root, dirs, files in os.walk('Libs'):
    extra_data.append((root, [os.path.join(root, n) for n in files]))

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
      data_files=['LICENSE', 'HISTORY',
				  ('brushes', glob.glob('brushes/*.myb')
                   + glob.glob('brushes/*.png')
                   + glob.glob('brushes/*.conf')),
                  ('backgrounds', glob.glob('backgrounds/*.conf')
                   + glob.glob('backgrounds/*.png')),
                  ] + extra_data,
      )
