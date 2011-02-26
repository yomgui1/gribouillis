#!/usr/bin/env python

import glob, os
from distutils.core import setup, Extension

pb_src_root = 'src'
pb_generic_srcs = [ 'math.c']
pb_generic_srcs = [ os.path.join(pb_src_root, p) for p in pb_generic_srcs ]

if os.name == 'morphos':
    opt = [ '-Wall -Wuninitialized -Wstrict-prototypes' ]
    pb_plat_srcs = [ 'src/platform-morphos.c' ]
elif os.name == 'posix':
    opt = None
    pb_plat_srcs = [ 'src/platform-posix.c' ]

pb_srcs = pb_generic_srcs + pb_plat_srcs

setup(name='Gribouillis',
      version='2.7',
      author='Guillaume Roguez',
      platforms=['unix', 'morphos'],
      ext_modules = [ Extension('model/_pixbuf', [ 'src/_pixbufmodule.c' ] + pb_srcs,
                                extra_compile_args = opt),
                      Extension('model/_tilemgr', [ 'src/_tilemgrmodule.c' ] + pb_srcs,
                                extra_compile_args = opt),
                      Extension('model/_brush', [ 'src/_brushmodule.c' ] + pb_srcs,
                                extra_compile_args = opt),
                      ],
      )
