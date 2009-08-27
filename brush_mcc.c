#include "brush_mcc.h"

#undef USE_INLINE_STDARG
#include <clib/alib_protos.h>
#include <proto/muimaster.h>
#include <proto/intuition.h>      
#define USE_INLINE_STDARG

#include <proto/exec.h>
#include <proto/graphics.h>

#ifndef DISPATCHER
#define DISPATCHER(Name) \
static ULONG Name##_Dispatcher(void); \
static struct EmulLibEntry GATE ##Name##_Dispatcher = { TRAP_LIB, 0, (void (*)(void)) Name##_Dispatcher }; \
static ULONG Name##_Dispatcher(void) { struct IClass *cl=(struct IClass*)REG_A0; Msg msg=(Msg)REG_A1; Object *obj=(Object*)REG_A2;
#define DISPATCHER_REF(Name) &GATE##Name##_Dispatcher
#define DISPATCHER_END }
#endif

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
