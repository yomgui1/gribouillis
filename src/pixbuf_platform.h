#ifndef PIXBUF_PLATFORM_H
#define PIXBUF_PLATFORM_H 1

/******************************************************************************
Copyright (c) 2011 Guillaume Roguez

<license to provide>

******************************************************************************/

/* Let platforms defines theirs needs first */

#ifdef __MORPHOS__
#include "pixbuf_morphos.h"
#endif

#ifdef __linux__
#include "pixbuf_linux.h"
#endif

/* !!! INSERT YOUR PLAFTORM HEADER INCLUSION HERE !!! */

/* Then set defaults */

#ifndef PBEXPORT
#  define PBEXPORT
#endif

#ifndef PBAPI
#  define PBAPI
#endif

#endif /* PIXBUF_PLATFORM_H */
