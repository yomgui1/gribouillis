#ifndef PIXBUF_INTERNAL_H
#define PIXBUF_INTERNAL_H 1

/******************************************************************************
Copyright (c) 2011 Guillaume Roguez

<license to provide>

******************************************************************************/

/* Information on stuctures:
**
** Structures don't know who they are grouped.
** So there is nothing like double/single linkage pointers
** inside their definitions body.
**
** It's not the role of one structure to know how it's grouped
** in the memory or elsewhere: that's giving a good flexibility
** to handle them later.
*/

#include "pixbuf_public.h"

/* ANSI-C includes */
#include <stdlib.h>

#define _PB_OBJCHECK(o, t) ((((_PBObject *)(o))->obsig >> 24) == (t))
#define PBDT_SET(t, p, v) (*(t*)(p) = (t)(v))

typedef int (*_PBGetAttrProto)(PBObject *obj, uint32_t id, void *value_ptr);
typedef int (*_PBSetAttributesProto)(PBObject *obj, PBAttribute *attrs);
typedef int (*_PBDestroyProto)(PBObject *obj);
typedef int (*_PBNewProto)(PBObject *obj, PBAttribute *attrs);

struct _PBContext;

typedef struct _PBObject {
    uint32_t              obsig;
    struct _PBContext *   ctx;
    _PBDestroyProto       destroy;
    _PBSetAttributesProto setattrs;
    _PBGetAttrProto       getattr;
} _PBObject;

typedef struct _PBGenericValue {
    int vid;    /* PBVID_XXX */
    int bits;   /* number of bits to encode the value */

    /* others non generic fields follow */
} _PBGenericValue;

typedef struct _PBSignedIntegerValue {
    int     vid;  /* fixed to PBVID_SIGNED_INTEGER */
    int     bits; /* in [1, 64] range */
    int64_t min;
    int64_t max;
} _PBSignedIntegerValue;

typedef struct _PBUnsignedIntegerValue {
    int      vid;  /* fixed to PBVID_UNSIGNED_INTEGER */
    int      bits; /* in [1, 64] range */
    uint64_t min;
    uint64_t max;
} _PBUnsignedIntegerValue;

typedef struct _PBFloatingValue {
    int    vid;  /* fixed to PBVID_FLOATING */
    int    bits; /* currently 32 or 64 */
    double min;
    double max;
} _PBFloatingValue;

typedef union _PBValueType {
    _PBGenericValue         as_generic;
    _PBSignedIntegerValue   as_signed_integer;
    _PBUnsignedIntegerValue as_unsigned_integer;
    _PBFloatingValue        as_floating;
} _PBValueType;

typedef struct _PBComponent {
    _PBObject      base;

    PBPhysicalType physical_type;
    _PBValueType   value_type;
} _PBComponent;

typedef struct _PBFormat {
    _PBObject      base;

    int            components;       /* number of components in next array */
    _PBComponent * component_obj;    /* component array to describe each one, order does matter */
    _PBValueType * component_vtype;  /* the computational representation of each component */

    int            h_sampling;
    int            v_sampling;

    union {
        PBTopologyType     type;

        struct {
            PBTopologyType type; /* fixed to PBTT_CHUNKY */

            int            bits_per_pixels;    /* total amount of bits to encode 1 pixel */
            int *          pitch; /* first offset bit for each component per pixel */
        } as_chunky;

        struct {
            PBTopologyType type;  /* fixed to PBTT_PLANAR */

            /* nothing yet */
        } as_planar;
    } topology;

    PBSetGetPixelProto          f_getpixel;
    PBSetGetPixelProto          f_setpixel;
    PBSetGetNormPixelProto      f_getnormpixel;
    PBSetGetNormPixelProto      f_setnormpixel;

    //PBSetGetComponentValueProto f_getcomponentvalue;
    //PBSetGetComponentValueProto f_setcomponentvalue;

    //PBSetGetComponentValueProto f_getcomponentvalue;
    //PBSetGetComponentValueProto f_getcomponentvalue;
} _PBFormat;

typedef struct _PBImage {
    _PBObject   base;

    _PBFormat * format;
    int         width;
    int         height;
    char **     data;   /* one pointer for chunky, as many components for planar */
    int *       pitch;  /* give the number of bits to pass to reach first bit
                           of first pixel for each previous data pointer */
} _PBImage;

typedef struct _PBContext {
    _PBObject         base;

    PBUserMallocProto user_malloc; /* The context is also allocated with it */
    PBUserFreeProto   user_free;
} _PBContext;

/* exported Context API */
extern int _pb_Ctx_GetAttr(PBObject *obj, uint32_t id, void *value_ptr);
extern int _pb_Ctx_InitContext(_PBContext *ctx, PBAttribute *attrs);

/* exported Component API */
extern int _pb_Comp_New(PBObject *obj, PBAttribute *attrs);
extern int _pb_Comp_GetAttr(PBObject *obj, uint32_t id, void *value_ptr);

#endif /* PIXBUF_INTERNAL_H */

/* EOF */
