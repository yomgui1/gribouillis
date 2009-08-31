#include "common.h"
#include "surface_mcc.h"

#include <proto/graphics.h>
#include <proto/utility.h>
#include <proto/layers.h>

#define AREA_SIZE 200   

typedef struct MCCData {
    struct MUI_EventHandlerNode ehnode;
    struct SurfaceST_MotionEvent mevt;
    struct Region *clip;
    WORD areaBuffer[AREA_SIZE];
    struct AreaInfo areaInfo;
    struct TmpRas tmpRas;
    PLANEPTR planePtr;
    UWORD w, h;
    LONG ox, oy;
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
//+ mDrawEllipse
static ULONG mDrawEllipse(struct IClass *cl, Object *obj, struct MP_DrawEllipse *msg)
{
    MCCData *data = INST_DATA(cl, obj);   
    FLOAT pressure = (float)msg->pressure / PRESSURE_MAX;
    LONG r, i;
    struct Region *old;
    UWORD xx, yy;   
    LONG dx, dy, dr;

    xx = msg->x + _mleft(obj);
    yy = msg->y + _mtop(obj);

    if (data->ox >= 0) {
        old = InstallClipRegion(_window(obj)->WLayer, data->clip);

        _rp(obj)->AreaInfo = &data->areaInfo; 
        _rp(obj)->TmpRas = &data->tmpRas;

        SetAPen(_rp(obj), _dri(obj)->dri_Pens[TEXTPEN]);
        SetDrMd(_rp(obj), JAM1);

        if (msg->pressure > 0)
            r = pressure * pressure * 8.;
        else
            r = 0;

        dx = xx - data->ox;
        dy = yy - data->oy;
        dr = sqrt(dx*dx+dy*dy) * 2;
        
        for (i=0; i <= dr; i++)
            AreaEllipse(_rp(obj), data->ox + (dx * i / dr), data->oy + (dy * i / dr), r, r);
        AreaEnd(_rp(obj));

        InstallClipRegion(_window(obj)->WLayer, old);

        _rp(obj)->AreaInfo = NULL;  
        _rp(obj)->TmpRas = NULL;
    }

      
    data->ox = xx;
    data->oy = yy;

    return 0;
}
//-
//+ mSetup
static ULONG mSetup(struct IClass *cl, Object *obj, Msg msg)
{
    MCCData *data = INST_DATA(cl, obj);
    USHORT i;
    
    if (!DoSuperMethodA(cl, obj, msg))
        return FALSE;

    data->ehnode.ehn_Object = obj;
    data->ehnode.ehn_Class  = cl;
    data->ehnode.ehn_Events = IDCMP_MOUSEMOVE|IDCMP_MOUSEBUTTONS;
    DoMethod(_win(obj), MUIM_Window_AddEventHandler, &data->ehnode);

    for (i=0; i<AREA_SIZE; i++)
        data->areaBuffer[i] = 0;

    InitArea(&data->areaInfo, data->areaBuffer, (AREA_SIZE*2)/5);
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
//+ mShow
static ULONG mShow(struct IClass *cl, Object *obj, Msg msg)
{
    MCCData *data = INST_DATA(cl, obj);
    UWORD w=_window(obj)->Width, h=_window(obj)->Height;

    data->planePtr = AllocRaster(w, h);
    if (NULL == data->planePtr)
        return FALSE;

    data->ox = -1;

    data->w = w;
    data->h = h;
    InitTmpRas(&data->tmpRas, data->planePtr, RASSIZE(w, h));

    data->clip = NewRegion();
    if (NULL != data->clip) {
        struct Rectangle rect = {_left(obj), _mtop(obj), _mright(obj), _bottom(obj)};

        OrRectRegion(data->clip, &rect);
        return DoSuperMethodA(cl, obj, msg);
    }

    return FALSE;
}
//-
//+ mHide
static ULONG mHide(struct IClass *cl, Object *obj, Msg msg)
{
    MCCData *data = INST_DATA(cl, obj);

    DisposeRegion(data->clip);
    FreeRaster(data->planePtr, data->w, data->h);

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
                if (_isinobject(msg->imsg->MouseX, msg->imsg->MouseY)) { 
                    BOOL down = (msg->imsg->Code & IECODE_UP_PREFIX) == 0;
                    BOOL select = (msg->imsg->Code & IECODE_LBUTTON) == IECODE_LBUTTON;

                    if (NULL != td) {
                        if (select)
                            set(obj, MA_Surface_LeftButtonPressed, down);
                    } else {
                        if (select)
                            set(obj, MA_Surface_LeftButtonPressed, down);
                    }

                    if (select && !down)
                        data->ox = -1;
                }
                break;

            case IDCMP_MOUSEMOVE:
                if (_isinobject(msg->imsg->MouseX, msg->imsg->MouseY)) {
                    struct Screen *scr = _screen(obj); 
                    
                    if (NULL != td) {
                        struct TagItem *tag, *tags = td->td_TagList;

                        data->mevt.X = (td->td_TabletX * scr->Width / td->td_RangeX) - _mleft(obj) - _window(obj)->LeftEdge;
                        data->mevt.Y = (td->td_TabletY * scr->Height / td->td_RangeY) - _mtop(obj) - _window(obj)->TopEdge;
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

                        data->mevt.IsTablet = TRUE;
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
                        data->mevt.Pressure = PRESSURE_MAX / 2;
                        data->mevt.InProximity = TRUE;
                        data->mevt.IsTablet = FALSE;
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
        case MUIM_Show       : return mShow       (cl, obj, (APTR)msg);
        case MUIM_Hide       : return mHide       (cl, obj, (APTR)msg);
        case MM_Surface_Draw : return mDrawEllipse(cl, obj, (APTR)msg);
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
