/******************************************************************************
Copyright (c) 2009 Guillaume Roguez

Permission is hereby granted, free of charge, to any person
obtaining a copy of this software and associated documentation
files (the "Software"), to deal in the Software without
restriction, including without limitation the rights to use,
copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following
conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.
******************************************************************************/

#include "common.h"

#define MA_Ruler_Horiz      (MYTAGBASE+0x20) /* I.. BOOL */
#define MA_Ruler_Thickness  (MYTAGBASE+0x21) /* I.. UBYTE */
#define MA_Ruler_Div1       (MYTAGBASE+0x22) /* I.. UBYTE */
#define MA_Ruler_Div2       (MYTAGBASE+0x23) /* I.. UBYTE */
#define MA_Ruler_Base       (MYTAGBASE+0x25) /* I.. ULONG */
#define MA_Ruler_Resolution (MYTAGBASE+0x26) /* ISG FLOAT* */
#define MA_Ruler_Offset     (MYTAGBASE+0x27) /* ISG LONG */

#define SUPERCLASS MUIC_Area
#define UserLibID "$VER: "CLASS" "VERSION_STR" ("__DATE__")"

#define LIBQUERYID "RULES_MCC"
#define LIBQUERYDESCRIPTION "Ruler MCC"

#define ClassInit ClassInitFunc
#define ClassExit ClassExitFunc

#ifdef NDEBUG
#define D(x)
#else
#define D(x) x
#endif

#define bug dprintf

typedef struct Data
{
    FLOAT Resolution; /* Give number of pixels in 1 base unit */
    ULONG Base; /* Give the number of unit between 2 major divisions */
    LONG Offset; /* Offset of the first pixel off the ruler */
    UBYTE Div1; /* Number of sub-divisions between 2 major divisions */
    UBYTE Div2; /* Number of sub-divisions between 2 sub-divisions */
    UBYTE Thickness; /* Size in pixels of the ruler thickness */
    UBYTE Horiz; /* True if ruler shall be display horizontally */
    
    struct Region *ClipRegion;
} Data;
 
#include "mui/mccheader.c"

#include <graphics/gfxmacros.h>

#include <proto/graphics.h>
#include <proto/layers.h>

#include <string.h> /* for memset */

static struct Library *LayersBase;

//+ ClassInitFunc
BOOL ClassInitFunc(void)
{
    LayersBase = OpenLibrary("layers.library", 50);
    dprintf("layer library: %p\n", LayersBase);
    return NULL != LayersBase;
}
//-
//+ ClassExitFunc
VOID ClassExitFunc(void)
{
    if (NULL != LayersBase)
        CloseLibrary(LayersBase);
}
//-

/********************************************************************************************/

//+ mNew
static ULONG mNew(struct IClass *cl, Object *obj, Msg msg)
{
    Data *data;
    struct TagItem *tags, *tag;

    obj = (Object *)DoSuperMethodA(cl, obj, msg);
    if (NULL == obj)
        return 0;

    data = INST_DATA(cl, obj);
    memset(data, 0, sizeof(*data));

    tags=((struct opSet *)msg)->ops_AttrList;
    while NULL != (tag = NextTagItem(&tags)) {
        switch (tag->ti_Tag) {
            case MA_Ruler_Horiz: data->Horiz = tag->ti_Data; break;
            case MA_Ruler_Thickness: data->Thickness = tag->ti_Data; break;
            case MA_Ruler_Div1: data->Div1 = tag->ti_Data; break;
            case MA_Ruler_Div2: data->Div2 = tag->ti_Data; break;
            case MA_Ruler_Base: data->Base = tag->ti_Data; break;
            case MA_Ruler_Resolution: data->Resolution = *(FLOAT *)tag->ti_Data; break;
            case MA_Ruler_Offset: data->Offset = tag->ti_Data; break;
        }
    }

    if ((0 == data->Base) || (0 == data->Thickness) || (0 == data->Div1) || (0 == data->Div1) || (0.0 == data->Resolution)) {
        CoerceMethod(cl, obj, OM_DISPOSE);
        return 0;
    }

    return (ULONG)obj;
}
//-
//+ mAskMinMax
static ULONG mAskMinMax(struct IClass *cl, Object *obj, struct MUIP_AskMinMax *msg)
{
    Data *data = INST_DATA(cl, obj);

    DoSuperMethodA(cl, obj, msg);

    if (data->Horiz) {
        msg->MinMaxInfo->MinWidth  += 0;
        msg->MinMaxInfo->DefWidth  += 0;
        msg->MinMaxInfo->MaxWidth  += MUI_MAXMAX;

        msg->MinMaxInfo->MinHeight += self->Thickness;
        msg->MinMaxInfo->DefHeight += self->Thickness;
        msg->MinMaxInfo->MaxHeight += self->Thickness;
    } else {
        msg->MinMaxInfo->MinWidth  += self->Thickness;
        msg->MinMaxInfo->DefWidth  += self->Thickness;
        msg->MinMaxInfo->MaxWidth  += self->Thickness;

        msg->MinMaxInfo->MinHeight += 0;
        msg->MinMaxInfo->DefHeight += 0;
        msg->MinMaxInfo->MaxHeight += MUI_MAXMAX;
    }

    return 0;
}
//-
//+ mShow
static ULONG mShow(struct IClass *cl, Object *obj, Msg msg)
{
    Data *data = INST_DATA(cl, obj);

    data->ClipRegion = NewRegion();
    if (NULL != data->ClipRegion) {
        struct Rectangle rect = {_left(obj), _mtop(obj), _mright(obj), _bottom(obj)};

        OrRectRegion(data->ClipRegion, &rect);
        return DoSuperMethodA(cl, obj, msg);
    }

    return FALSE;
}
//-
//+ mHide
static ULONG mHide(struct IClass *cl, Object *obj, Msg msg)
{
    Data *data = INST_DATA(cl, obj);

    DisposeRegion(data->ClipRegion);
    return DoSuperMethodA(cl, obj, msg);
}
//-
//+ mDraw
static ULONG mDraw(struct IClass *cl, Object *obj, struct MUIP_Draw *msg)
{
    Data *data = INST_DATA(cl, obj);
    struct Rectangle rect = {_left(obj), _mtop(obj), _mright(obj), _bottom(obj)};
    struct RastPort *rp;
    struct Region *oldregion;
    FLOAT pos;

    DoSuperMethodA(cl, obj, msg);

    if (!(msg->flags & MADF_DRAWOBJECT))
        return 0;

    /* Install a clip region for text */
    ClearRegion(data->ClipRegion);
    OrRectRegion(data->ClipRegion, &rect);
    oldregion = InstallClipRegion(_window(obj)->WLayer, data->ClipRegion);

    rp = _rp(obj);

    if (self->Horiz) {
        _mleft(obj) + self->Offset;
        for (pos=_mleft(obj); pos <= _mright(obj);) {
            ULONG off = pos + self->Offset;

            Move(rp, i*, );
            Draw(rp, );
            i += self->Resolution;
        }
    } else {
        min = _mtop(obj);
        max = _mbottom(obj);
    }

    

    /* Remove the clip region before exit */
    InstallClipRegion(_window(obj)->WLayer, oldregion);
    return 0;
}
//-
//+ _Dispatcher
ULONG _Dispatcher(VOID)
{
    struct IClass *cl = (APTR)REG_A0;
    Object *obj = (APTR)REG_A2;
    Msg msg = (APTR)REG_A1;
 
    switch (msg->MethodID) {
        case OM_NEW         : return mNew        (cl, obj, (APTR)msg);
        case MUIM_AskMinMax : return mAskMinMax  (cl, obj, (APTR)msg);
        case MUIM_Show      : return mShow       (cl, obj, (APTR)msg);
        case MUIM_Hide      : return mHide       (cl, obj, (APTR)msg);
        case MUIM_Draw      : return mDraw       (cl, obj, (APTR)msg);
    }

    return DoSuperMethodA(cl, obj, msg);
}
//-

/* EOF */
