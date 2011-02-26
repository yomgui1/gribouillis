/******************************************************************************
Copyright (c) 2011 Guillaume Roguez

<license to provide>

******************************************************************************/

#include "pixbuf_internal.h"

/* ANSI-C includes */
#include <string.h>

/*=== Component Object API ===*/

int _pb_Comp_New(PBObject *obj, PBAttribute *attrs)
{
    _PBComponent *comp = (PBObject *)obj;
    PBAttribute *attr;
    PBPhysicalType phy_type;
    int err, bits, value_type;
    PBValue min, max;

    err = _pb_GenericNew(obj, attrs);
    if (PBERR_NONE != err)
        return err;

    phy_type = PBCT_UNKNOWN;
    bits = 0;
    value_type = PBVID_INTEGER;
    memset(&min, 0, sizeof(PBValue));
    memset(&max, 0, sizeof(PBValue));

    /* Parse attributes */
    while (pb_NextAttribute(&attrs, &attr)) {
        switch (attr->id) {
            case PBATTR_CMP_BITS: bits = attr->value.as_uint32; break;
            case PBATTR_CMP_PHYTYPE: phy_type = attr->value.as_uint32; break;
            case PBATTR_CMP_VALUETYPE: value_type = attr->value.as_uint32; break;
            case PBATTR_CMP_MIN: min = attr->value; break;
            case PBATTR_CMP_MAX: max = attr->value; break;
        }
    }

    /* Valid and store attributes */
    switch (phy_type) {
        case PBCT_LUMINANCE:
        case PBCT_CHROMATICY:
        case PBCT_OPACITY:
            comp->physical_type = phy_type;
            break;

        default:
            return PBERR_BADARGS;
    }

    if (memcmp(&min, &max, sizeof(PBValue)))
        return PBERR_BADARGS;

    if (bits == 0)
        return PBERR_BADARGS;

    switch (value_type) {
        case PBVID_INTEGER:
            if ((bits > 64) || (min.as_uint64 >= max.as_uint64))
                return PBERR_BADARGS;
            comp->value_type.as_integer.vid = PBVID_INTEGER;
            comp->value_type.as_integer.bits = bits;
            comp->value_type.as_integer.min = min.as_uint64;
            comp->value_type.as_integer.max = max.as_uint64;
            break;

        case PBVID_FLOATING:
            comp->value_type.as_floating.vid = PBVID_FLOATING;
            comp->value_type.as_floating.bits = bits;
            if (bits <= 32) {
                comp->value_type.as_floating.min = min.as_float;
                comp->value_type.as_floating.max = max.as_float;
            } else if (bits <= 64){
                comp->value_type.as_floating.min = min.as_double;
                comp->value_type.as_floating.max = max.as_double;
            } else
                return PBERR_BADARGS;
            if (comp->value_type.as_floating.min >= comp->value_type.as_floating.max)
                return PBERR_BADARGS;
            break;
    }

    return PBERR_NONE;
}

int _pb_Comp_GetAttr(PBObject *obj, uint32_t id, PBValue *value)
{
    _PBComponent *comp = (PBObject *)obj;

    switch (id) {
        case PBATTR_CMP_PHYTYPE: value->as_uint32 = comp->physical_type; return PBERR_NONE;
        case PBATTR_CMP_BITS: value->as_uint32 = comp->value_type.as_generic.bits; return PBERR_NONE;
        case PBATTR_CMP_VALUETYPE: value->as_uint32 = comp->value_type.as_generic.vid; return PBERR_NONE;
        case PBATTR_CMP_MIN:
            if (PBVID_INTEGER == comp->physical_type)
                value->as_uint64 = comp->value_type.as_integer.min;
            else
                value->as_double = comp->value_type.as_floating.min;
            return PBERR_NONE;
        case PBATTR_CMP_MAX:
            if (PBVID_INTEGER == comp->physical_type)
                value->as_uint64 = comp->value_type.as_integer.max;
            else
                value->as_double = comp->value_type.as_floating.max;
            return PBERR_NONE;
    }

    return _pb_GenericGetAttr(obj, id, value);
}

/* EOF */
