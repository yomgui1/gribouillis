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
#include "brush_mcc.h"

#include <proto/graphics.h>

typedef struct BrushMCCData {
    struct MUI_EventHandlerNode ehnode;
    BOOL under_mouse;
} BrushMCCData;

//+ mAskMinMax
static ULONG mAskMinMax(struct IClass *cl, Object *obj, struct MUIP_AskMinMax *msg)
{
    DoSuperMethodA(cl, obj, msg);

    msg->MinMaxInfo->MinWidth  += 2;
    msg->MinMaxInfo->DefWidth  += 2;
    msg->MinMaxInfo->MaxWidth  += 2;

    msg->MinMaxInfo->MinHeight += 2;
    msg->MinMaxInfo->DefHeight += 2;
    msg->MinMaxInfo->MaxHeight += 2;

    return 0;
}
//-
//+ mDraw
static ULONG mDraw(struct IClass *cl, Object *obj, struct MUIP_Draw *msg)
{
    BrushMCCData *data = INST_DATA(cl, obj);   
    int pen;

    DoMethod(obj,MUIM_DrawBackground, _mleft(obj), _mtop(obj), _mwidth(obj), _mheight(obj), 0, 0, 0);
    DoSuperMethodA(cl, obj, msg);

    if (!(msg->flags & (MADF_DRAWOBJECT|MADF_DRAWUPDATE)))
        return 0;

    if (data->under_mouse)
        pen = MPEN_SHADOW;
    else
        return 0;

    SetAPen(_rp(obj), _dri(obj)->dri_Pens[pen]);

    Move(_rp(obj), _mleft(obj), _mtop(obj));
    Draw(_rp(obj), _mright(obj), _mtop(obj));
    Draw(_rp(obj), _mright(obj), _mbottom(obj));
    Draw(_rp(obj), _mleft(obj), _mbottom(obj));
    Draw(_rp(obj), _mleft(obj), _mtop(obj));

    return 0;
}
//-
//+ mSetup
static ULONG mSetup(struct IClass *cl, Object *obj, Msg msg)
{
    BrushMCCData *data = INST_DATA(cl, obj);  
    
    if (!DoSuperMethodA(cl, obj, msg))
        return FALSE;

    data->ehnode.ehn_Object = obj;
    data->ehnode.ehn_Class  = cl;
    data->ehnode.ehn_Events = IDCMP_MOUSEMOVE|IDCMP_MOUSEBUTTONS;
    DoMethod(_win(obj), MUIM_Window_AddEventHandler, &data->ehnode);

    return TRUE;
}
//-
//+ mCleanup
static ULONG mCleanup(struct IClass *cl, Object *obj, Msg msg)
{
    BrushMCCData *data = INST_DATA(cl, obj);  
    
    DoMethod(_win(obj), MUIM_Window_RemEventHandler, &data->ehnode);

    return DoSuperMethodA(cl, obj, msg);
}
//-
//+ mHandleEvent
static ULONG mHandleEvent(struct IClass *cl, Object *obj, struct MUIP_HandleEvent *msg)
{
    #define _between(a,x,b) ((x)>=(a) && (x)<=(b))
    #define _isinobject(x,y) (_between(_mleft(obj),(x),_mright(obj)) && _between(_mtop(obj),(y),_mbottom(obj)))

    BrushMCCData *data = INST_DATA(cl, obj);

    #if 0
    if (msg->muikey != MUIKEY_NONE) {
        switch (msg->muikey) {
            //case MUIKEY_LEFT : data->sx=-1; MUI_Redraw(obj,MADF_DRAWUPDATE); break;
            //case MUIKEY_RIGHT: data->sx= 1; MUI_Redraw(obj,MADF_DRAWUPDATE); break;
            //case MUIKEY_UP   : data->sy=-1; MUI_Redraw(obj,MADF_DRAWUPDATE); break;
            //case MUIKEY_DOWN : data->sy= 1; MUI_Redraw(obj,MADF_DRAWUPDATE); break;
        }
    }
    #endif

    if (msg->imsg) {
        switch (msg->imsg->Class) {
            case IDCMP_MOUSEBUTTONS:
                if (SELECTDOWN == msg->imsg->Code) {
                    if (_isinobject(msg->imsg->MouseX, msg->imsg->MouseY))
                        set(obj, MUIA_Selected, TRUE);
                }
                break;

            case IDCMP_MOUSEMOVE:
                if (_isinobject(msg->imsg->MouseX, msg->imsg->MouseY)) {
                    data->under_mouse = TRUE;
                    MUI_Redraw(obj, MADF_DRAWUPDATE);
                } else if (data->under_mouse) {
                    data->under_mouse = FALSE;
                    MUI_Redraw(obj, MADF_DRAWUPDATE);
                }
                break;
        }
    }

    return 0;
}
//-

//+ DISPATCHER(BrushMCC)
DISPATCHER(BrushMCC)
{
    switch (msg->MethodID) {
        case MUIM_AskMinMax  : return mAskMinMax  (cl, obj, (APTR)msg);
        case MUIM_Draw       : return mDraw       (cl, obj, (APTR)msg);
        case MUIM_HandleEvent: return mHandleEvent(cl, obj, (APTR)msg);
        case MUIM_Setup      : return mSetup      (cl, obj, (APTR)msg);
        case MUIM_Cleanup    : return mCleanup    (cl, obj, (APTR)msg);
    }

    return DoSuperMethodA(cl, obj, msg);
}
DISPATCHER_END
//-

/*-----------------------------------------------------------------------------------------------------------*/

//+ BrushMCC_Init
struct MUI_CustomClass * BrushMCC_Init(void)
{
    return MUI_CreateCustomClass(NULL, MUIC_Dtpic, NULL, sizeof(BrushMCCData), DISPATCHER_REF(BrushMCC));
}
//-
//+ BrushMCC_Term
void BrushMCC_Term(struct MUI_CustomClass * mcc)
{
    MUI_DeleteCustomClass(mcc);
}
//-
