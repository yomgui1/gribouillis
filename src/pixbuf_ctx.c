/******************************************************************************
Copyright (c) 2011 Guillaume Roguez

<license to provide>

******************************************************************************/

#include "pixbuf_internal.h"

/*=== Context Object API ===*/

int _pb_Ctx_GetAttr(PBObject *obj, uint32_t id, void *value_ptr)
{
    _PBContext *ctx = (_PBContext *)obj;

    if (!_PB_OBJCHECK(ctx, PBOT_CONTEXT))
        return PBERR_BADOBJ;

    switch (id) {
        case PBATTR_CTX_MALLOC: PBDT_SET(void *, value_ptr, ctx->user_malloc); break;
        case PBATTR_CTX_FREE: PBDT_SET(void *, value_ptr, ctx->user_free); break;
        default: return PBERR_NOTGETATTR;
    }

    return PBERR_NONE;
}

int _pb_Ctx_InitContext(_PBContext *ctx, PBAttribute *attrs)
{
    PBUserMallocProto user_malloc;
    PBUserFreeProto user_free;

    /* As pb_NewObjectA needs a valid context object,
     * we create dummy one, fill mem routines and process as usual.
     */

    /* Attributes handling */
    if (NULL != attrs) {
        pb_FindAttribute(attrs, PBATTR_CTX_MALLOC, sizeof(user_malloc), (void **)&user_malloc);
        pb_FindAttribute(attrs, PBATTR_CTX_FREE, sizeof(user_free), (void **)&user_free);
    }

    if (NULL == user_malloc)
        user_malloc = malloc;

    if (NULL == user_free)
        user_free = free;

    ctx->user_malloc = user_malloc;
    ctx->user_free = user_free;
    ctx->base.ctx = ctx;

    return PBERR_NONE;
}

/* EOF */
