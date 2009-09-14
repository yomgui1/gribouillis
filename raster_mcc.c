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

#define SUPERCLASS MUIC_Area
#define UserLibID "$VER: "CLASS" "VERSION_STR" ("__DATE__")"

#define LIBQUERYID "RASTER_MCC"
#define LIBQUERYDESCRIPTION "Raster MCC"

typedef struct Data {
    APTR Clipping;
    struct BitMap * RasteredBitMap; /* Contains the last rasted view */
    struct RastPort RastPort; /* RastPort used with the previous bitmap */
    ULONG UpdateFlags;
    struct Rectangle Rects[4];
} Data;

#include "mui/mccheader.c"

#include <proto/graphics.h>

//+ mAskMinMax
static ULONG mAskMinMax(struct IClass *cl, Object *obj, struct MUIP_AskMinMax *msg)
{
    DoSuperMethodA(cl, obj, msg);

    msg->MinMaxInfo->MinWidth  += 0;
    msg->MinMaxInfo->DefWidth  += 320;
    msg->MinMaxInfo->MaxWidth  += MUI_MAXMAX;

    msg->MinMaxInfo->MinHeight += 0;
    msg->MinMaxInfo->DefHeight += 320;
    msg->MinMaxInfo->MaxHeight += MUI_MAXMAX;

    return 0;
}
//-
//+ mShow
static ULONG mShow(struct IClass *cl, Object *obj, Msg msg)
{
    Data *data = INST_DATA(cl, obj);

    /* Clipping for draw routines */
    data->Clipping = MUI_AddClipping(muiRenderInfo(obj), _mleft(obj), _mtop(obj), _mwidth(obj), _mheight(obj));
    if (NULL == data->Clipping)
        return FALSE;

    /* First creation step */
    if (NULL == data->RasteredBitMap) {
        data->RasteredBitMap = AllocBitMap(_mwidth(obj), _mheight(obj), 24, BMF_CLEAR|BMF_DISPLAYABLE, NULL);
        if (NULL == data->RasteredBitMap)
            return FALSE;
        InitRastPort(&data->RastPort);
        data->RastPort.BitMap = data->RasteredBitMap;
    } else { /* Check for raster area changes */
        LONG delta_w, delta_h;

        delta_w = _mwidth(obj) - data->BitMap->Width;
        delta_w = _mheight(obj) - data->BitMap->Height;

        data->UpdateFlags = 0;

        if (0 < delta_w) { /* increased width */
            data->Rects[3].XMin = data->BitMap->Width;
            data->Rects[3].XMax = _mwidth(obj);
            data->Rects[3].YMin = 0;
            data->Rects[3].YMax = min(data->BitMap->Height, _mheight(obj));
            data->UpdateFlags |= 1<<3;
        } else if (0 > delta_w) { /* reduced width */
            data->UpdateFlags |= 1<<7;
        }
        
        if (0 < delta_h) { /* increased height */
            data->Rects[1].XMin = 0;
            data->Rects[1].XMax = _mwidth(obj);
            data->Rects[1].YMin = data->BitMap->Height;
            data->Rects[1].YMax = _mheight(obj);
            data->UpdateFlags |= 1<<1;
        } else if (0 > delta_h) { /* reduced height */
            data->UpdateFlags |= 1<<5;
        }
    }

    return DoSuperMethodA(cl, obj, msg);
}
//-
//+ mHide
static ULONG mHide(struct IClass *cl, Object *obj, Msg msg)
{
    Data *data = INST_DATA(cl, obj);

    MUI_RemoveClipping(muiRenderInfo(obj), data->Clipping);

    return DoSuperMethodA(cl, obj, msg);
}
//-
//+ mDispose
static ULONG mDispose(struct IClass *cl, Object *obj, Msg msg)
{
    Data *data = INST_DATA(cl, obj);

    if (NULL != data->RasteredBitMap)
        FreeBitMap(data->RasteredBitMap);

    return DoSuperMethodA(cl, obj, msg);
}
//-
//+ mDraw
static ULONG mDraw(struct IClass *cl, Object *obj, struct MUIP_Draw *msg)
{
    DoSuperMethodA(cl, obj, msg);

#if 0
    if (!(msg->flags & (MADF_DRAWOBJECT|MADF_DRAWUPDATE)))
        return 0;
#endif

    data->UpdateFlags = 0;

    return 0;
}
//-

/********************************************************************************************/

//+ _Dispatcher
ULONG _Dispatcher(VOID)
{
    struct IClass *cl = (APTR)REG_A0;
    Object *obj = (APTR)REG_A2;
    Msg msg = (APTR)REG_A1;

    switch (msg->MethodID) {
        case OM_DISPOSE      : return mDispose    (cl, obj, (APTR)msg);
        case MUIM_AskMinMax  : return mAskMinMax  (cl, obj, (APTR)msg);
        case MUIM_Show       : return mShow       (cl, obj, (APTR)msg);
        case MUIM_Hide       : return mHide       (cl, obj, (APTR)msg);
        case MUIM_Draw       : return mDraw       (cl, obj, (APTR)msg);
    }

    return DoSuperMethodA(cl, obj, msg);
}
//-

/* EOF */
