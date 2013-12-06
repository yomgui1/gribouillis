#!/usr/bin/env python

import glob, os
from distutils.core import setup, Extension

pb_src_root = 'src'
pb_generic_srcs = [ 'math.c']
pb_generic_srcs = [ os.path.join(pb_src_root, p) for p in pb_generic_srcs ]

ext_extra = []

if os.name == 'morphos':
    opt = [ '-Wall -Wuninitialized -Wstrict-prototypes' ]
    pb_plat_srcs = [ 'src/platform-morphos.c' ]
    defines = [ ('NDEBUG', None),
                ('__MORPHOS_SHAREDLIBS', None) ]
    link_opt = [ '-llcms2', '-lGL', '-lGLU', '-lGLUT', '-lm' ]

elif os.name == 'posix':
    opt = [ '-I/usr/include/gdk-pixbuf-2.0', '-I/usr/include/libpng15',
            '-I/usr/include/glib-2.0', '-I/usr/lib64/glib-2.0/include' ]
    pb_plat_srcs = [ 'src/platform-posix.c' ]
    defines = [ ('HAVE_GDK', True) ]
    link_opt = [ '-llcms2', '-lgdk_pixbuf-2.0', '-lgobject-2.0', '-lglib-2.0' ]

link_opt += ['-lpng']
pb_srcs = pb_generic_srcs + pb_plat_srcs

ext_savers = Extension('model/_savers', [ 'src/_saversmodule.c' ] + pb_srcs,
                       define_macros=defines,
                       extra_compile_args=opt,
                       extra_link_args=link_opt)

ext_render_gl = Extension('view/pymui/_glbackend', [ 'src/_glbackend.c' ] + pb_srcs,
                          define_macros=defines,
                          extra_compile_args=opt,
                          extra_link_args=link_opt)

if os.name == 'morphos':
    ext_extra = [ ext_savers, ext_render_gl ]
else:
    ext_extra = [ ext_savers ]

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
                      Extension('model/_cutils', [ 'src/_cutilsmodule.c' ],
                                define_macros=defines,
                                extra_compile_args=opt,
                                extra_link_args=link_opt),
                      ] + ext_extra)
