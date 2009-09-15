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

#define MM_Raster_Move (MYTAGBASE+0x00)

typedef struct Data {
    UWORD Width, Height;
    struct BitMap * BitMap; /* Contains the last rasted view */
    struct RastPort RastPort; /* RastPort used with the previous bitmap */
    ULONG UpdateFlags;
    struct Rectangle Rects[4];
} Data;

struct MP_Raster_Move {
    ULONG dx, dy;
}; 

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
//+ mSetup
static ULONG mSetup(struct IClass *cl, Object *obj, Msg msg)
{
    Data *data = INST_DATA(cl, obj);
    struct Screen *scr;

    if (!DoSuperMethodA(cl, obj, msg))
        return FALSE;

    scr = _screen(obj);
    
    /* Alloc a bitmap as large as the screen size if the size has changed or if not allocated yet */
    if ((NULL == data->BitMap) || (data->Width != scr->Width) || (data->Height != scr->Height)) {
        if (NULL != data->BitMap)
            FreeBitMap(data->BitMap);
        
        data->Width = scr->Width;
        data->Height = scr->Height;
        data->BitMap = AllocBitMap(data->Width, data->Height, 24, BMF_CLEAR|BMF_DISPLAYABLE, NULL);
        if (NULL == data->BitMap)
            return FALSE;

        InitRastPort(&data->RastPort);
        data->RastPort.BitMap = data->BitMap;
    }

    return TRUE;
}
//-
//+ mShow
static ULONG mShow(struct IClass *cl, Object *obj, Msg msg)
{
    Data *data = INST_DATA(cl, obj);
    LONG delta_w, delta_h;

    /* mShow called when object's bbox has changed */

    delta_w = _mwidth(obj) - data->Width;
    delta_h = _mheight(obj) - data->Height;

    data->UpdateFlags = 0;
    if (0 < delta_w) { /* increased width */
        data->Rects[3].MinX = data->Width;
        data->Rects[3].MaxX = _mwidth(obj);
        data->Rects[3].MinY = 0;
        data->Rects[3].MaxY = MIN(data->Height, _mheight(obj));
        data->UpdateFlags |= 1<<3;
    } else if (0 > delta_w) { /* reduced width */
        data->UpdateFlags |= 1<<7;
    }
        
    if (0 < delta_h) { /* increased height */
        data->Rects[1].MinX = 0;
        data->Rects[1].MaxX = _mwidth(obj);
        data->Rects[1].MinX = data->Height;
        data->Rects[1].MaxX = _mheight(obj);
        data->UpdateFlags |= 1<<1;
    } else if (0 > delta_h) { /* reduced height */
        data->UpdateFlags |= 1<<5;
    }

    return DoSuperMethodA(cl, obj, msg);
}
//-
//+ mDispose
static ULONG mDispose(struct IClass *cl, Object *obj, Msg msg)
{
    Data *data = INST_DATA(cl, obj);

    if (NULL != data->BitMap)
        FreeBitMap(data->BitMap);

    return DoSuperMethodA(cl, obj, msg);
}
//-
//+ mDraw
static ULONG mDraw(struct IClass *cl, Object *obj, struct MUIP_Draw *msg)
{
    Data *data = INST_DATA(cl, obj);  
    
    DoSuperMethodA(cl, obj, msg);

    if (msg->flags & MADF_DRAWOBJECT)
        BltBitMapRastPort(data->BitMap, 0, 0, _rp(obj), _mleft(obj), _mtop(obj), _mwidth(obj), _mheight(obj), 0xc0);

    return 0;
}
//-
//+ mMove
static ULONG mMove(struct IClass *cl, Object *obj, struct MP_Raster_Move *msg)
{
    Data *data = INST_DATA(cl, obj);
    
    BltBitMap(data->BitMap, 0, 0, data->BitMap, msg->dx, msg->dy, _mwidth(obj), _mheight(obj), 0xc0, -1, NULL);

    /* TODO: we need to compute which part of the bitmap need to be redraw */

    return 0;
}
//-

/********************************************************************************************/

//+ _Dispatcher
ULONG _Dispatcher(void)
{
    struct IClass *cl = (APTR)REG_A0;
    Object *obj = (APTR)REG_A2;
    Msg msg = (APTR)REG_A1;

    switch (msg->MethodID) {
        case OM_DISPOSE      : return mDispose    (cl, obj, (APTR)msg);
        case MUIM_AskMinMax  : return mAskMinMax  (cl, obj, (APTR)msg);
        case MUIM_Setup      : return mSetup      (cl, obj, (APTR)msg);
        //case MUIM_Show       : return mShow       (cl, obj, (APTR)msg);
        case MUIM_Draw       : return mDraw       (cl, obj, (APTR)msg);
        case MM_Raster_Move  : return mMove       (cl, obj, (APTR)msg);
    }

    return DoSuperMethodA(cl, obj, msg);
}
//-

/* EOF */
