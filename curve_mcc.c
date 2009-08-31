#include "common.h"
#include "curve_mcc.h"

#include <proto/graphics.h>

#define CLAMP(v, min, max) ({                             \
            typeof(v) _v = (v);                                 \
            typeof(min) _min = (min);                           \
            typeof(max) _max = (max);                           \
            (_v < _min) ? _min : ((_v > _max) ? _max : _v); })

#define _between(a,x,b) ((x)>=(a) && (x)<=(b))

#define DRAW_AREA_MIN_WIDTH  200
#define DRAW_AREA_MIN_HEIGHT 100
#define DRAW_AREA_DEFAULT_WIDTH  300
#define DRAW_AREA_DEFAULT_HEIGHT 200

#define KNOT_RADIUS 3

typedef struct FloatPoint
{
    FLOAT x, y;
} FloatPoint;

typedef struct KnotNode {
    struct MinNode kn_Node;
    FloatPoint     kn_Position;
} KnotNode;

typedef struct MCCData {
    struct MinList              KnotList;
    struct MUI_EventHandlerNode EventNode;
    KnotNode *                  GrabNode;
    ULONG Pen_Bg, Pen_Grid, Pen_Line, Pen_Knot;
} MCCData;

//+ new_knot
static KnotNode *new_knot(FLOAT x, FLOAT y)
{
    KnotNode *node = AllocMem(sizeof(*node), MEMF_PUBLIC);
    if (node != NULL) {
        node->kn_Position.x = x;
        node->kn_Position.y = y;
    }
    return node;
}
//-
//+ add_knot
static KnotNode *add_knot(MCCData *data, FLOAT x, FLOAT y)
{
    KnotNode *node, *new_node = NULL;

    if ((x < 0.0) || (x > 1.0))
        return NULL;

    y = CLAMP(y, 0.0, 1.0);

    if (IsListEmpty((struct List *)&data->KnotList)) {
        new_node = new_knot(x, y);
        if (new_node != NULL) {
            ADDHEAD(&data->KnotList, new_node);
        }
    } else {
        ForeachNode(&data->KnotList, node) {
            if (x < node->kn_Position.x)
                continue;

            if (x == node->kn_Position.x) {
                node->kn_Position.y = y;
                new_node = node;
            } else {
                new_node = new_knot(x, y);
                if (new_node != NULL) {
                    INSERT(&data->KnotList, new_node, node);
                }
            }

            break;
        }
    }

    return new_node;
}
//-
//+ find_knot
static KnotNode *find_knot(MCCData *data, FLOAT x, FLOAT y, FLOAT radius)
{
    KnotNode *node;

    ForeachNode(&data->KnotList, node) {
        if (_between(node->kn_Position.x-radius, x, node->kn_Position.x+radius)
            && _between(node->kn_Position.y-radius, y, node->kn_Position.y+radius))
            return node;
    }

    return NULL;
}
//-
//+ set_knot
static void set_knot(KnotNode *node, FLOAT x, FLOAT y)
{
    KnotNode *pred, *succ;

    pred = (KnotNode *)GetPred(node);
    succ = (KnotNode *)GetSucc(node);

    /* Lock knot moves between its predecessor and successor knots.
     * And block first and last knots on their x position.
     */

    if ((NULL != pred) && (NULL != succ))
        node->kn_Position.x = CLAMP(x, pred->kn_Position.x, succ->kn_Position.x);

    node->kn_Position.y = CLAMP(y, pred->kn_Position.y, succ->kn_Position.y);
}
//-

/*-----------------------------------------------------------------------------------------------------------*/

//+ mNew
static ULONG mNew(struct IClass *cl, Object *obj, Msg msg)
{
    MCCData *data;
    struct TagItem *tags, *tag;

    obj = (Object *)DoSuperMethodA(cl, obj, msg);
	if (NULL == obj)
		return 0;

	data = INST_DATA(cl, obj);
    memset(data, 0, sizeof(*data));
    NEWLIST(&data->KnotList);

    /* Add first and last knots, these ones can't be moved in the x-axis */
    if ((NULL == add_knot(data, 0.0, 0.0)) || (NULL == add_knot(data, 1.0, 1.0)))
        return NULL;

#if 0
    tags=((struct opSet *)msg)->ops_AttrList;
    while NULL != (tag = NextTagItem(&tags)) {
		switch (tag->ti_Tag) {
			case :
				if (tag->ti_Data)
					data->penspec = *((struct MUI_PenSpec *)tag->ti_Data);
				break;
		}
	}
#endif

	return (ULONG)obj;
}
//-
//+ mDispose
static ULONG mDispose(struct IClass *cl, Object *obj, Msg msg)
{
    MCCData *data = INST_DATA(cl, obj);
    KnotNode *node;
    APTR next;

    ForeachNodeSafe(&data->KnotList, node, next)
        FreeMem(node, sizeof(*node));

	return DoSuperMethodA(cl, obj, msg);
}
//-
//+ mAskMinMax
static ULONG mAskMinMax(struct IClass *cl, Object *obj, struct MUIP_AskMinMax *msg)
{
    DoSuperMethodA(cl, obj, msg);

    msg->MinMaxInfo->MinWidth  += DRAW_AREA_MIN_WIDTH;
    msg->MinMaxInfo->DefWidth  += DRAW_AREA_DEFAULT_WIDTH;
    msg->MinMaxInfo->MaxWidth  += MUI_MAXMAX;

    msg->MinMaxInfo->MinHeight += DRAW_AREA_MIN_HEIGHT;
    msg->MinMaxInfo->DefHeight += DRAW_AREA_DEFAULT_WIDTH;
    msg->MinMaxInfo->MaxHeight += MUI_MAXMAX;

    return 0;
}
//-
//+ mSetup
static ULONG mSetup(struct IClass *cl, Object *obj, Msg msg)
{
    MCCData *data = INST_DATA(cl, obj);
    
    if (!DoSuperMethodA(cl, obj, msg))
        return FALSE;

    data->Pen_Bg = _dri(obj)->dri_Pens[MPEN_BACKGROUND];
    data->Pen_Grid = _dri(obj)->dri_Pens[MPEN_HALFSHADOW];
    data->Pen_Line = _dri(obj)->dri_Pens[MPEN_SHINE];
    data->Pen_Knot = _dri(obj)->dri_Pens[TEXTPEN];

    data->EventNode.ehn_Object = obj;
    data->EventNode.ehn_Class  = cl;
    data->EventNode.ehn_Events = IDCMP_MOUSEMOVE;
    data->EventNode.ehn_Flags  = MUI_EHF_GUIMODE;
    DoMethod(_win(obj), MUIM_Window_AddEventHandler, &data->EventNode);

    return TRUE;
}
//-
//+ mCleanup
static ULONG mCleanup(struct IClass *cl, Object *obj, Msg msg)
{
    MCCData *data = INST_DATA(cl, obj);
    
    DoMethod(_win(obj), MUIM_Window_RemEventHandler, &data->EventNode);
    return DoSuperMethodA(cl, obj, msg);
}
//-
//+ mDraw
static ULONG mDraw(struct IClass *cl, Object *obj, struct MUIP_Draw *msg)
{
    MCCData *data;
    struct RastPort *rp;
    UWORD left, right, top, bottom, width, height;
    int i;

    if (!(msg->flags & MADF_DRAWOBJECT))
        return 0;

    data = INST_DATA(cl, obj);
    rp = _rp(obj);
    left = _mleft(obj);
    top = _mtop(obj);
    right = _mright(obj);
    bottom = _mbottom(obj);
    width = right - left;
    height = bottom - top;

    /* Draw the background */
    SetAPen(rp, data->Pen_Bg);
    RectFill(rp, left, top, right, bottom);

    /* Draw the grid */
    SetAPen(rp, data->Pen_Grid);
    for (i=0; i <= 10; i++) { /* 10 divisions for X-axis */
        ULONG x = left + width * i / 10;

        Move(rp, x, top);
        Draw(rp, x, bottom);
    }
    for (i=0; i <= 5; i++) { /* 5 divisions for Y-axis */
        ULONG y = top + height * i / 5;

        Move(rp, left, y);
        Draw(rp, right, y);
    }
    
    {
        KnotNode *node;
        ULONG x0, y0;

        /* Draw lines between controls points */
        SetAPen(rp, data->Pen_Line);

        node = (APTR)GetHead(&data->KnotList);
        x0 = left + (ULONG)(node->kn_Position.x * width);
        y0 = bottom - (ULONG)(node->kn_Position.y * height);
        
        Move(rp, x0, y0);
        while (NULL != (node = (APTR)GetSucc(node))) {
            x0 = left + (ULONG)(node->kn_Position.x * width);
            y0 = bottom - (ULONG)(node->kn_Position.y * height);
            Draw(rp, x0, y0);
        }

        /* Draw control points themself */
        SetAPen(rp, data->Pen_Knot);

        ForeachNode(&data->KnotList, node) {
            x0 = left + (ULONG)(node->kn_Position.x * width);
            y0 = bottom - (ULONG)(node->kn_Position.y * height);
            
            RectFill(rp, x0-KNOT_RADIUS, y0-KNOT_RADIUS, x0+KNOT_RADIUS, y0+KNOT_RADIUS);
        }
    }

    return 0;
}
//-
//+ mHandleEvent
static ULONG mHandleEvent(struct IClass *cl, Object *obj, struct MUIP_HandleEvent *msg)
{
    #define _isinobject(x,y) (_between(_mleft(obj),(x),_mright(obj)) && _between(_mtop(obj),(y),_mbottom(obj)))

    MCCData *data = INST_DATA(cl, obj);
    
    if (NULL != msg->imsg) {
        switch (msg->imsg->Class) {
            case IDCMP_MOUSEBUTTONS:
                if (_isinobject(msg->imsg->MouseX, msg->imsg->MouseY)) {
                    BOOL down = (msg->imsg->Code & IECODE_UP_PREFIX) == 0;
                    BOOL buttons = msg->imsg->Code & (IECODE_LBUTTON|IECODE_MBUTTON|IECODE_RBUTTON);
                    FLOAT fx, fy;
                    KnotNode *node;

                    /* Convert raster position into [0.0, 1.0] range */
                    fx = (FLOAT)(msg->imsg->MouseX - _mleft(obj)) / (_mwidth(obj) - 1);
                    fy = (FLOAT)(msg->imsg->MouseY - _mtop(obj)) / (_mheight(obj) - 1);

                    if (NULL == data->GrabNode) { /* Not in grab mode */
                        if ((buttons == IECODE_LBUTTON) && down) {
                            FLOAT fr;

                            /* convert pixel radius into float radius */
                            fr = (FLOAT)KNOT_RADIUS / (_mwidth(obj) - 1);

                            node = find_knot(data, fx, fy, fr);
                            if (NULL != node) { /* Click on an existing knot */
                                data->GrabNode = node; /* Enter in grab mode */
                                set_knot(node, fx, fy); /* move the knot */
                            } else { /* New knot wanted */
                                node = add_knot(data, fx, fy); /* may return an existing node if user click
                                                                * just perfeclty on the same y-level.
                                                                */
                                data->GrabNode = node; /* Enter in grab mode */
                                set_knot(node, fx, fy); /* move the knot */
                            }

                            /* We enter in grab mode => listen to mouse move */
                            DoMethod(_win(obj), MUIM_Window_RemEventHandler, &data->EventNode);
                            data->EventNode.ehn_Events |= IDCMP_MOUSEMOVE;
                            DoMethod(_win(obj), MUIM_Window_AddEventHandler, &data->EventNode);

                            MUI_Redraw(obj, MADF_DRAWOBJECT);
                        }
                    } else { /* In grab mode */
                        if (((buttons & IECODE_LBUTTON) == IECODE_LBUTTON) && !down) {
                            /* Was in grab mode => confirm node position and return to normal mode */
                            
                            set_knot(data->GrabNode, fx, fy);

                            data->GrabNode = NULL;

                            /* We leave grab mode => stop to listen to mouse move */
                            DoMethod(_win(obj), MUIM_Window_RemEventHandler, &data->EventNode);
                            data->EventNode.ehn_Events &= ~IDCMP_MOUSEMOVE;
                            DoMethod(_win(obj), MUIM_Window_AddEventHandler, &data->EventNode);

                            MUI_Redraw(obj, MADF_DRAWOBJECT);
                        }
                    }
                }
                break;

            case IDCMP_MOUSEMOVE:
                if (_isinobject(msg->imsg->MouseX, msg->imsg->MouseY)) {
                    FLOAT fx, fy;

                    /* We suppose that we are in grab mode if IDCMP_MOUSEMOVE is set */

                    /* Convert raster position into [0.0, 1.0] range */
                    fx = (FLOAT)(msg->imsg->MouseX - _mleft(obj)) / (_mwidth(obj) - 1);
                    fy = (FLOAT)(msg->imsg->MouseY - _mtop(obj)) / (_mheight(obj) - 1);

                    set_knot(data->GrabNode, fx, fy);
                    MUI_Redraw(obj, MADF_DRAWOBJECT);
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
        case OM_NEW          : return mNew        (cl, obj, (APTR)msg);
        case OM_DISPOSE      : return mDispose    (cl, obj, (APTR)msg);  
        case MUIM_AskMinMax  : return mAskMinMax  (cl, obj, (APTR)msg);
        case MUIM_Setup      : return mSetup      (cl, obj, (APTR)msg);
		case MUIM_Cleanup    : return mCleanup    (cl, obj, (APTR)msg);
        case MUIM_Draw       : return mDraw       (cl, obj, (APTR)msg);
        case MUIM_HandleEvent: return mHandleEvent(cl, obj, (APTR)msg);
    }

    return DoSuperMethodA(cl, obj, msg);
}
DISPATCHER_END
//-

/*-----------------------------------------------------------------------------------------------------------*/

//+ CurveMCC_Init
struct MUI_CustomClass * CurveMCC_Init(void)
{
    return MUI_CreateCustomClass(NULL, MUIC_Area, NULL, sizeof(MCCData), DISPATCHER_REF(mcc));
}
//-
//+ CurveMCC_Term
void CurveMCC_Term(struct MUI_CustomClass * mcc)
{
    MUI_DeleteCustomClass(mcc);
}
//-
