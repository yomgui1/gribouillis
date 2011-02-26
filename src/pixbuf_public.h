#ifndef PIXBUF_PUBLIC_H
#define PIXBUF_PUBLIC_H 1

/******************************************************************************
Copyright (c) 2011 Guillaume Roguez

<license to provide>

******************************************************************************/

/*
 * PixelBuffer, a pixel formats manipulation library at bit granularity.
 */

/* Platforms stuffs */
#include "pixbuf_platform.h"

/* ANSI-C includes */
#include <sys/types.h>
#include <stdint.h>
#include <math.h>

/* PixelBuffer Types */
typedef enum PBError {
    PBERR_NONE        = 0,
    PBERR_NOMEM       = 1,
    PBERR_BADARGS     = 2,
    PBERR_BADOBJ      = 3,
    PBERR_NOTINITATTR = 4,
    PBERR_NOTSETATTR  = 5,
    PBERR_NOTGETATTR  = 6,
    PBERR_BADCTX      = 7,
} PBError;

typedef enum PBObjectType {
    PBOT_RESERVED   = 0,

    PBOT_CONTEXT    = 1, /* An objects constructor/destructor */
    PBOT_COMPONENT  = 2, /* An unbounded channel of an image */
    PBOT_MODEL      = 3, /* An unordered list of bounded components */
    PBOT_FORMAT     = 4, /* An orderered model */
    PBOT_IMAGE      = 5, /* A bounded array of pixels described by a format */
    PBOT_TRANSLATOR = 6, /* A engine to convert an object into another one (of same type) */

    /* Pre-defined components (1000 <= id < 2000) */
    PBOT_CMP_RED        = 1000,
    PBOT_CMP_GREEN      = 1001,
    PBOT_CMP_BLUE       = 1002,
    PBOT_CMP_ALPHA      = 1003,
    PBOT_CMP_Y          = 1004,
    PBOT_CMP_U          = 1005,
    PBOT_CMP_V          = 1006,
    PBOT_CMP_CYAN       = 1007,
    PBOT_CMP_YELLOW     = 1008,
    PBOT_CMP_MAGENTA    = 1009,
    PBOT_CMP_KEY        = 1010,
    PBOT_CMP_BLACK      = 1010, /* SAME AS PBOT_CMP_KEY */
    PBOT_CMP_CIE_L      = 1011,
    PBOT_CMP_CIE_A      = 1012,
    PBOT_CMP_CIE_B      = 1013,
    PBOT_CMP_CIE_X      = 1014,
    PBOT_CMP_CIE_Y      = 1015,
    PBOT_CMP_CIE_Z      = 1016,
    PBOT_CMP_CR         = 1017,
    PBOT_CMP_CB         = 1018,
    PBOT_CMP_HUE        = 1019,
    PBOT_CMP_SATURATION = 1020,
    PBOT_CMP_LUMINANCE  = 1021,
    
    /* Pre-defined models (2000 <= id < 3000) */
    PBOT_MODEL_RGB      = 2000, /* 3x double */
    PBOT_MODEL_RGB8     = 2001, /* 3x uint8 */
    PBOT_MODEL_RGBA     = 2002, /* 4x double */
    PBOT_MODEL_RGBA8    = 2003, /* 4x uint8 */
    PBOT_MODEL_CYMK     = 2004, /* 4x double */
    PBOT_MODEL_CYMK8    = 2005, /* 4x uint8 */
    PBOT_MODEL_CYMKA    = 2006, /* 5x double */
    PBOT_MODEL_CYMKA8   = 2007, /* 5x uint8 */
    PBOT_MODEL_YUV      = 2008, /* 3x double */
    PBOT_MODEL_YUV8     = 2009, /* 3x uint8 */
} PBObjectType;

/* PBPhysicalType: physical representation of components */
typedef enum {
    PBCT_UNKNOWN    = 0,
    PBCT_LUMINANCE  = 1,
    PBCT_CHROMATICY = 2,
    PBCT_OPACITY    = 3,
} PBPhysicalType;

/* PBValueType: mathematical definition of components values */
typedef enum {
    PBVID_SIGNED_INTEGER   = 0,
    PBVID_UNSIGNED_INTEGER = 1,
    PBVID_FLOATING         = 2,
} PBValueTypeID;

/* PBTopology: how components are structured */
typedef enum {
    PBTT_CHUNKY = 0,
    PBTT_PLANAR = 1,
} PBTopologyType;

typedef enum PBAccessorID {
    /*--- V1.0 ---*/
    PBACC_GETPIXEL     = 0,
    PBACC_SETPIXEL     = 1,
    PBACC_GETNORMPIXEL = 2,
    PBACC_SETNORMPIXEL = 3,
} PBAccessorID;

typedef struct PBAttribute {
    uint32_t id;        /* attribute id */
    void *   value_ptr; /* pointer on attribute value */
} PBAttribute;

typedef void PBObject;

typedef void *(*PBUserMallocProto)(size_t n);
typedef void (*PBUserFreeProto)(void *p);

/*=== Attributes ID ===*/

/* Attributes ID are 32bit values, with following bit meaning:
 *
 * (MSB)
 * 1 bit to indicate it's a user attribute
 * 7 bits reserved (shall be filled with zero's)
 * 24 bits to encode uniquely all attributes
 * (LSB)
 *
 * Note: ID= 0x0 to 0xf are reserved.
 *
 * Notes on ISG flags bellow:
 * I : can be given at creation
 * S : can be set after creation
 * G : can be get after creation
 */

#define PBATTR_END  0
#define PBATTR_MORE 1

#define PBATTR_CTX_MALLOC        (0x0010) /* I.G (PBUserMallocProto) */
#define PBATTR_CTX_FREE          (0x0011) /* I.G (PBUserFreeProto)) */
#define PBATTR_CONTEXT           (0x0012) /* I.G (PBObject *) */

#define PBATTR_CMP_PHYTYPE       (0x0013) /* I.G (PBPhysicalType) */
#define PBATTR_CMP_VALUETYPEID   (0x0014) /* I.G (PBValueTypeID) */
#define PBATTR_CMP_BITS          (0x0015) /* I.G (int) */
#define PBATTR_CMP_MIN           (0x0016) /* I.G (depends on CMP_VALUETYPEID and CMP_BITS) */
#define PBATTR_CMP_MAX           (0x0017) /* I.G (depends on CMP_VALUETYPEID and CMP_BITS) */

/*=== General Public API ===*/

extern PBAPI int PBEXPORT pb_NextAttribute(PBAttribute **attr_array, PBAttribute **attr);
extern PBAPI int PBEXPORT pb_FindAttribute(PBAttribute *attr_array, uint32_t id, size_t value_len, void *value);

extern PBAPI int PBEXPORT pb_NewObject(PBObject *ctx, PBObject **obj, int type, PBAttribute *attrs);
extern PBAPI int PBEXPORT pb_DestroyObject(PBObject *obj);

extern PBAPI int PBEXPORT pb_SetAttributes(PBObject *obj, PBAttribute *attrs);
extern PBAPI int PBEXPORT pb_SetAttr(PBObject *obj, uint32_t id, void *value_ptr);
extern PBAPI int PBEXPORT pb_GetAttr(PBObject *obj, uint32_t id, void *value_ptr);

/*=== methods ===*/

/*--- V1.0 ---*/
typedef int (*PBSetGetPixelProto)(PBObject *im, int x, int y, void *color);
typedef int (*PBSetGetNormPixelProto)(PBObject *im, int x, int y, double_t *color);

extern PBAPI PBSetGetPixelProto     PBEXPORT pbm_GetPixel;
extern PBAPI PBSetGetPixelProto     PBEXPORT pbm_SetPixel;
extern PBAPI PBSetGetNormPixelProto PBEXPORT pbm_GetNormalizedPixel;
extern PBAPI PBSetGetNormPixelProto PBEXPORT pbm_SetNormalizedPixel;

#endif /* PIXBUF_PUBLIC_H */

/* EOF */
