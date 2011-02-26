/******************************************************************************
Copyright (c) 2011 Guillaume Roguez

<license to provide>

******************************************************************************/

#include "pixbuf_internal.h"

/* ANSI-C includes */
#include <string.h>

/*=== Generic Attributes API ===*/

int pb_NextAttribute(PBAttribute **attr_array, PBAttribute **attr)
{
    if (NULL == attr_array[0])
        return 0;

    switch ((attr_array[0])->id) {
        case PBATTR_END: return 0;
        case PBATTR_MORE:
            attr_array[0] = attr_array[0]->value_ptr;
            break;

        default:;
    }
    
    attr[0] = attr_array[0];
    attr_array[0]++;

    return 1;
}

int pb_FindAttribute(PBAttribute *attr_array, uint32_t id, size_t value_len, void *value)
{
    PBAttribute *attr;
    
    while (pb_NextAttribute(&attr_array, &attr)) {
        if (attr->id == id) {
            memcpy(value, attr->value_ptr, value_len);
            return 1;
        }
    }
    
    return 0;
}

/*=== Generic Object API ===*/

static int _pb_GenericSetAttributes(PBObject *obj, PBAttribute *attrs)
{
    return PBERR_NOTSETATTR;
}

static int _pb_GenericGetAttr(PBObject *obj, uint32_t id, void *value)
{
    _PBObject *_obj = obj;
    
    switch (id) {
        case PBATTR_CONTEXT: PBDT_SET(void *, value, _obj->ctx); break;
        default: return PBERR_NOTGETATTR;
    }
    
    return PBERR_NONE;
}

static void _pb_RootDestroyObject(_PBContext *ctx, _PBObject *obj)
{
    /* force a NULL access if this function is called later with same object */
    memset(obj, 0, sizeof(_PBObject));
    ctx->user_free(obj);
}

int pb_NewObject(PBObject *ctx, PBObject **obj, int type, PBAttribute *attrs)
{
    _PBObject *_obj;
    _PBContext dummy_ctx;
    size_t size;
    _PBNewProto new_func = NULL;
    _PBDestroyProto destroy_func = NULL;
    _PBSetAttributesProto seta_func = _pb_GenericSetAttributes;
    _PBGetAttrProto geta_func = _pb_GenericGetAttr;
    int err;

    /* Special handling for Context creation */
    if (PBOT_CONTEXT == type) {
        err = _pb_Ctx_InitContext(&dummy_ctx, attrs);
        if (PBERR_NONE != err)
            return err;
            
        ctx = &dummy_ctx; /* use our dummy as temporary context */
        
    } else if (!_PB_OBJCHECK(ctx, PBOT_CONTEXT))
        return PBERR_BADCTX;
        
    switch (type) {
        case PBOT_CONTEXT:
            size = sizeof(_PBContext);
            break;

        case PBOT_FORMAT:
            size = sizeof(_PBFormat);
            break;

        case PBOT_COMPONENT:
            size = sizeof(_PBComponent);
            new_func = _pb_Comp_New;
            break;

        case PBOT_IMAGE:
            size = sizeof(_PBImage);
            break;

        //case PBOT_TRANSLATOR:

        default: return PBERR_BADARGS;
    }

    /* Object allocation */
    _obj = *obj = ((_PBContext *)ctx)->user_malloc(size);
    if (NULL == *obj)
        return PBERR_NOMEM;

    /* Context creation case handling */
    if (PBOT_CONTEXT == type) {
        err = _pb_Ctx_InitContext((_PBContext *)_obj, attrs);
        if (PBERR_NONE != err) {
            _pb_RootDestroyObject(&dummy_ctx, _obj);
            return err;
        }
        
        ctx = _obj;
    }
    
    /* Object basic initialisations */
    _obj->ctx = ctx;
    _obj->obsig = (type << 24) | (size & 0x00ffffff);
    _obj->destroy = destroy_func;
    _obj->setattrs = seta_func;
    _obj->getattr = geta_func;
    
    /* User initialisations */
    if (NULL != new_func) {
        err = new_func(_obj, attrs);
        if (PBERR_NONE != err)
            _pb_RootDestroyObject(ctx, _obj);
    } else
        err = PBERR_NONE;
    
    return err;
}

int pb_DestroyObject(PBObject *obj)
{
    _PBObject *_obj = (_PBObject *)obj;
    int err;

    if (NULL != _obj->destroy)
        err = _obj->destroy(obj);
    else
        err = PBERR_NONE;
    
    /* mandatory and never fails (memory deallocation) */
    _pb_RootDestroyObject(_obj->ctx, _obj);
    
    return err;
}

int pb_GetAttr(PBObject *obj, uint32_t id, void *value_ptr)
{
    _PBObject *_obj = obj;
    int err;
    
    err = _obj->getattr(obj, id, value_ptr);
    if (PBERR_NOTGETATTR == err)
        return _pb_GenericGetAttr(obj, id, value_ptr);
        
    return err;
}

int pb_SetAttributes(PBObject *obj, PBAttribute *attrs)
{
    _PBObject *_obj = obj;
    int err;
    
    err = _obj->setattrs(obj, attrs);
    if (PBERR_NOTSETATTR == err)
        return _pb_GenericSetAttributes(obj, attrs);
        
    return err;
}

int pb_SetAttr(PBObject *obj, uint32_t id, void *value_ptr)
{
    PBAttribute attrs[2];
    
    attrs[0].id = id;
    attrs[0].value_ptr = value_ptr;
    attrs[1].id = PBATTR_END;
    
    return pb_SetAttributes(obj, attrs);
}

/* EOF */
