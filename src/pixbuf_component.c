/******************************************************************************
Copyright (c) 2011 Guillaume Roguez

<license to provide>

******************************************************************************/

#include "pixbuf_internal.h"

/* ANSI-C includes */
#include <string.h>
#include <float.h>

/*=== Component Object API ===*/

int _pb_Comp_New(PBObject *obj, PBAttribute *attrs)
{
    _PBComponent *comp = (PBObject *)obj;
    PBAttribute *attr;
    PBPhysicalType phy_type;
    int bits, vtid;
    void *min_ptr, *max_ptr;

    /* attributes default value */
    phy_type = PBCT_UNKNOWN;
    vtid = -1;
    bits = 0;
    min_ptr = NULL;
    max_ptr = NULL;

    /* Parse attributes */
    while (pb_NextAttribute(&attrs, &attr)) {
        switch (attr->id) {
            case PBATTR_CMP_PHYTYPE: phy_type = *(PBPhysicalType *)attr->value_ptr; break;
            case PBATTR_CMP_VALUETYPEID: vtid = *(PBValueTypeID *)attr->value_ptr; break;
            case PBATTR_CMP_BITS: bits = *(int *)attr->value_ptr; break;
            case PBATTR_CMP_MIN: min_ptr = attr->value_ptr; break;
            case PBATTR_CMP_MAX: max_ptr = attr->value_ptr; break;
            default:;
        }
    }

    /* Valid and store attributes */
    switch (phy_type) {
        case PBCT_UNKNOWN:
        case PBCT_LUMINANCE:
        case PBCT_CHROMATICY:
        case PBCT_OPACITY:
            comp->physical_type = phy_type;
            break;

        default: return PBERR_BADARGS;
    }

    switch (vtid) {
        case PBVID_SIGNED_INTEGER:
            if ((bits < 1) || (bits > 64))
                return PBERR_BADARGS;

            comp->value_type.as_signed_integer.min = (1ULL << (bits-1)) - 1;
            if (NULL != min_ptr) {
                int64_t min = *(int64_t *)min_ptr;

                if (min < comp->value_type.as_signed_integer.min)
                    return PBERR_BADARGS;

                comp->value_type.as_signed_integer.min = min;
            }
            comp->value_type.as_signed_integer.max = 1ULL << (bits-1);
            if (NULL != max_ptr) {
                int64_t max = *(int64_t *)max_ptr;

                if (max > comp->value_type.as_signed_integer.max)
                    return PBERR_BADARGS;

                comp->value_type.as_signed_integer.max = max;
            }
            if (comp->value_type.as_signed_integer.min > comp->value_type.as_signed_integer.max)
                return PBERR_BADARGS;
            break;

        case PBVID_UNSIGNED_INTEGER:
            if ((bits < 1) || (bits > 64))
                return PBERR_BADARGS;

            comp->value_type.as_unsigned_integer.min = 0;
            if (NULL != min_ptr) {
                uint64_t min = *(uint64_t *)min_ptr;

                comp->value_type.as_unsigned_integer.min = min;
            }
            comp->value_type.as_unsigned_integer.max = UINT64_MAX >> (64-bits);
            if (NULL != max_ptr) {
                uint64_t max = *(uint64_t *)max_ptr;

                if (max > comp->value_type.as_unsigned_integer.max)
                    return PBERR_BADARGS;

                comp->value_type.as_unsigned_integer.max = max;
            }
            if (comp->value_type.as_unsigned_integer.min > comp->value_type.as_unsigned_integer.max)
                return PBERR_BADARGS;

        case PBVID_FLOATING:
            if ((bits != 32) || (bits != 64))
                return PBERR_BADARGS;

            comp->value_type.as_floating.min = bits == 32 ? FLT_MIN : DBL_MIN;
            if (NULL != min_ptr) {
                double min = *(double *)min_ptr;

                if (min < comp->value_type.as_floating.min)
                    return PBERR_BADARGS;

                comp->value_type.as_floating.min = min;
            }
            comp->value_type.as_floating.max = bits == 32 ? FLT_MAX : DBL_MAX;
            if (NULL != max_ptr) {
                double max = *(double *)max_ptr;

                if (max > comp->value_type.as_floating.max)
                    return PBERR_BADARGS;

                comp->value_type.as_floating.max = max;
            }
            if (comp->value_type.as_floating.min > comp->value_type.as_floating.max)
                return PBERR_BADARGS;
            break;

        default: return PBERR_BADARGS;
    }

    comp->value_type.as_generic.vid = vtid;
    comp->value_type.as_generic.bits = bits;

    return PBERR_NONE;
}

int _pb_Comp_GetAttr(PBObject *obj, uint32_t id, void *value_ptr)
{
    _PBComponent *comp = (PBObject *)obj;

    switch (id) {
        case PBATTR_CMP_PHYTYPE: PBDT_SET(PBPhysicalType, value_ptr, comp->physical_type); break;
        default: return PBERR_NOTGETATTR;
    }

    return PBERR_NONE;
}

/* EOF */
