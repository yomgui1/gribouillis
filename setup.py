#!/usr/bin/env python

import glob, os
from distutils.core import setup, Extension

pb_src_root = 'src'
pb_generic_srcs = [ 'math.c']
pb_generic_srcs = [ os.path.join(pb_src_root, p) for p in pb_generic_srcs ]

if os.name == 'morphos':
    opt = [ '-Wall -Wuninitialized -Wstrict-prototypes' ]
    pb_plat_srcs = [ 'src/platform-morphos.c' ]
    defines = [ ('NDEBUG', None),
                ('__MORPHOS_SHAREDLIBS', None) ]
    link_opt = [ '-lsyscall', '-llcms2' ]
elif os.name == 'posix':
    opt = None
    pb_plat_srcs = [ 'src/platform-posix.c' ]
    defines = ()
    link_opt = ['-llcms2']

link_opt += ['-lpng']
pb_srcs = pb_generic_srcs + pb_plat_srcs

setup(name='Gribouillis',
      version='3.0',
      author='Guillaume Roguez',
      platforms=['unix', 'morphos'],
      ext_modules = [ Extension('model/_pixbuf', [ 'src/_pixbufmodule.c' ] + pb_srcs,
                                define_macros=defines,
                                extra_compile_args=opt,
                                extra_link_args=link_opt),
                      Extension('model/_tilemgr', [ 'src/_tilemgrmodule.c' ] + pb_srcs,
                                define_macros=defines,
                                extra_compile_args=opt,
                                extra_link_args=link_opt),
                      Extension('model/_brush', [ 'src/_brushmodule.c' ] + pb_srcs,
                                define_macros=defines,
                                extra_compile_args=opt,
                                extra_link_args=link_opt),
                      Extension('model/_lcms', [ 'src/_lcmsmodule.c' ] + pb_srcs,
                                define_macros=defines,
                                extra_compile_args=opt,
                                extra_link_args=link_opt),
                      Extension('model/_savers', [ 'src/_saversmodule.c' ] + pb_srcs,
                                define_macros=defines,
                                extra_compile_args=opt,
                                extra_link_args=link_opt),
                      ])
