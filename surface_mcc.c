#include "common.h"
#include "surface_mcc.h"

#include <proto/graphics.h>
#include <proto/utility.h>

typedef struct MCCData {
    struct MUI_EventHandlerNode ehnode;
    struct SurfaceST_MotionEvent mevt;
} MCCData;

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
//+ mDraw
static ULONG mDraw(struct IClass *cl, Object *obj, struct MUIP_Draw *msg)
{
    DoSuperMethodA(cl, obj, msg);

    if (!(msg->flags & (MADF_DRAWOBJECT|MADF_DRAWUPDATE)))
        return 0;

    return 0;
}
//-
//+ mSetup
static ULONG mSetup(struct IClass *cl, Object *obj, Msg msg)
{
    MCCData *data = INST_DATA(cl, obj);
    
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
    MCCData *data = INST_DATA(cl, obj);
    
    DoMethod(_win(obj), MUIM_Window_RemEventHandler, &data->ehnode);
    return DoSuperMethodA(cl, obj, msg);
}
//-
//+ mHandleEvent
static ULONG mHandleEvent(struct IClass *cl, Object *obj, struct MUIP_HandleEvent *msg)
{
    #define _between(a,x,b) ((x)>=(a) && (x)<=(b))
    #define _isinobject(x,y) (_between(_mleft(obj),(x),_mright(obj)) && _between(_mtop(obj),(y),_mbottom(obj)))

    MCCData *data = INST_DATA(cl, obj);
    struct IntuiMessage *imsg = msg->imsg;
    
    if (NULL != imsg) {
        struct TabletData *td = ((struct ExtIntuiMessage *)imsg)->eim_TabletData;

        switch (msg->imsg->Class) {
            case IDCMP_MOUSEBUTTONS:
                if (SELECTDOWN == msg->imsg->Code)
                    if (_isinobject(msg->imsg->MouseX, msg->imsg->MouseY)) {
                        if (NULL != td) {        
                        } else {
                        }
                    }
                break;

            case IDCMP_MOUSEMOVE:
                if (_isinobject(msg->imsg->MouseX, msg->imsg->MouseY)) {
                    struct Screen *scr = _screen(obj); 
                    
                    if (NULL != td) {
                        struct TagItem *tag, *tags = td->td_TagList;

                        data->mevt.X = td->td_TabletX;
                        data->mevt.Y = td->td_TabletY;
                        data->mevt.RangeX = td->td_RangeX;
                        data->mevt.RangeY = td->td_RangeY;

                        while (NULL != (tag = NextTagItem(&tags))) {
                            switch (tag->ti_Tag) {
                                case TABLETA_Pressure: data->mevt.Pressure = tag->ti_Data; break;
                                case TABLETA_InProximity: data->mevt.InProximity = tag->ti_Data; break;
                                case TABLETA_TabletZ: data->mevt.Z = tag->ti_Data; break;
                                case TABLETA_RangeZ: data->mevt.RangeZ = tag->ti_Data; break;
                                case TABLETA_AngleX: data->mevt.AngleX = tag->ti_Data; break;
                                case TABLETA_AngleY: data->mevt.AngleY = tag->ti_Data; break;
                                case TABLETA_AngleZ: data->mevt.AngleZ = tag->ti_Data; break;
                            }
                        }
                    } else {
                        data->mevt.X = imsg->MouseX - _mleft(obj);
                        data->mevt.Y = imsg->MouseY - _mtop(obj);
                        data->mevt.Z = 0;
                        data->mevt.AngleX = 0;
                        data->mevt.AngleY = 0;
                        data->mevt.AngleZ = 0;
                        data->mevt.RangeX = scr->Width;
                        data->mevt.RangeY = scr->Height;
                        data->mevt.RangeZ = 0;
                        data->mevt.Pressure = 0;
                    }

                    set(obj, MA_Surface_MotionEvent, &data->mevt);
                }
                break;
        }
    }

    return 0;
}
//-

//+ DISPATCHER
DISPATCHER(mcc)
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

//+ SurfaceMCC_Init
struct MUI_CustomClass * SurfaceMCC_Init(void)
{
    return MUI_CreateCustomClass(NULL, MUIC_Area, NULL, sizeof(MCCData), DISPATCHER_REF(mcc));
}
//-
//+ SurfaceMCC_Term
void SurfaceMCC_Term(struct MUI_CustomClass * mcc)
{
    MUI_DeleteCustomClass(mcc);
}
//-
