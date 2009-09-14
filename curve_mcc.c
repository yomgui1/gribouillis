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

#define MA_Curve_Points    (MYTAGBASE+0x10)
#define MA_Curve_Count     (MYTAGBASE+0x11)
#define MM_Curve_DeleteAll (MYTAGBASE+0x12)
#define MM_Curve_MapValue  (MYTAGBASE+0x13)

struct MP_Curve_MapValue { ULONG MethodID; FLOAT *Value; };

#define SUPERCLASS MUIC_Area
#define UserLibID "$VER: "CLASS" "VERSION_STR" ("__DATE__")"

#define LIBQUERYID "CURVE_MCC"
#define LIBQUERYDESCRIPTION "Curve editor MCC"

#define ClassInit ClassInitFunc
#define ClassExit ClassExitFunc

#ifdef NDEBUG
#define D(x)
#else
#define D(x) x
#endif

#define bug dprintf

typedef struct FloatPoint
{
    FLOAT x, y;
} FloatPoint;

typedef struct KnotNode {
    struct MinNode kn_Node;
    FloatPoint     kn_Position;
} KnotNode;

typedef struct Data
{
    struct MinList              KnotList;
    struct MUI_EventHandlerNode EventNode;
    struct Region *             ClipRegion;
    KnotNode *                  GrabNode;
    KnotNode *                  LastAdded;
    ULONG Pen_Bg, Pen_Grid, Pen_Line, Pen_Knot;
    FloatPoint                  Old;
} Data;
 
#include "mui/mccheader.c"

#include <graphics/gfxmacros.h>

#include <proto/graphics.h>
#include <proto/layers.h>

#include <string.h> /* memset */

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

#define KNOT_RADIUS 4
#define GRID_DIVX 4
#define GRID_DIVY 4

static struct Library *LayersBase;

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
static KnotNode *add_knot(Data *data, FLOAT x, FLOAT y)
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
            if (x > node->kn_Position.x)
                continue;

            if (x == node->kn_Position.x) {
                node->kn_Position.y = y;
                new_node = node;
            } else {
                node = (KnotNode *)GetPred(node);
                new_node = new_knot(x, y);
                data->LastAdded = new_node;
                if (new_node != NULL) {
                    INSERT(&data->KnotList, new_node, node);
                }
            }

            return new_node;
        }

        if (x == 1.0) {
            new_node = new_knot(x, y);
            if (new_node != NULL)
                ADDTAIL(&data->KnotList, new_node);
        } else
            D(bug("%s:%u: bad case!\n", __FUNCTION__, __LINE__));
    }

    return new_node;
}
//-
//+ del_knot
static void del_knot(Data *data, KnotNode *node)
{
    if ((node != (KnotNode *)GetHead(&data->KnotList)) && (node != (KnotNode *)GetTail(&data->KnotList)))
        REMOVE(node);
    else if (NULL != data->GrabNode)
        node->kn_Position = data->Old;
}
//-
//+ find_knot
static KnotNode *find_knot(Data *data, FLOAT x, FLOAT y, FLOAT radius)
{
    KnotNode *node;

    ForeachNode(&data->KnotList, node) {
        if (_between(node->kn_Position.x-radius, x, node->kn_Position.x+radius)
            && _between(node->kn_Position.y-radius, y, node->kn_Position.y+radius)) {
            return node;
        }
    }

    return NULL;
}
//-
//+ set_knot
static void set_knot(KnotNode *node, FLOAT x, FLOAT y)
{
    KnotNode *pred, *succ;

    x = CLAMP(x, 0.0, 1.0);
    y = CLAMP(y, 0.0, 1.0);

    pred = (KnotNode *)GetPred(node);
    succ = (KnotNode *)GetSucc(node);

    /* Lock knot moves between its predecessor and successor knots.
     * And block first and last knots on their x position.
     */

    if ((NULL != pred) && (NULL != succ))
        node->kn_Position.x = CLAMP(x, pred->kn_Position.x, succ->kn_Position.x);

    node->kn_Position.y = y;
}
//-

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
    NEWLIST(&data->KnotList);

    /* Add first and last knots, these ones can't be moved in the x-axis */
    if ((NULL == add_knot(data, 0.0, 0.0)) || (NULL == add_knot(data, 1.0, 1.0))) {
        CoerceMethod(cl, obj, OM_DISPOSE);
        return NULL;
    }

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
    CoerceMethod(cl, obj, MM_Curve_DeleteAll);
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
    Data *data = INST_DATA(cl, obj);
    
    if (!DoSuperMethodA(cl, obj, msg))
        return FALSE;

    data->Pen_Bg = _dri(obj)->dri_Pens[MPEN_HALFSHADOW];
    data->Pen_Grid = _dri(obj)->dri_Pens[MPEN_SHINE];
    data->Pen_Line = _dri(obj)->dri_Pens[MPEN_HALFSHINE];
    data->Pen_Knot = _dri(obj)->dri_Pens[TEXTPEN];

    data->EventNode.ehn_Object = obj;
    data->EventNode.ehn_Class  = cl;
    data->EventNode.ehn_Events = IDCMP_MOUSEBUTTONS;
    data->EventNode.ehn_Flags  = MUI_EHF_GUIMODE;
    DoMethod(_win(obj), MUIM_Window_AddEventHandler, &data->EventNode);

    return TRUE;
}
//-
//+ mCleanup
static ULONG mCleanup(struct IClass *cl, Object *obj, Msg msg)
{
    Data *data = INST_DATA(cl, obj);
    
    DoMethod(_win(obj), MUIM_Window_RemEventHandler, &data->EventNode);
    return DoSuperMethodA(cl, obj, msg);
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
    struct RastPort *rp;
    struct Region *oldregion;
    UWORD left, right, top, bottom, width, height;
    int i;

    DoSuperMethodA(cl, obj, msg);

    if (!(msg->flags & MADF_DRAWOBJECT))
        return 0;

    oldregion = InstallClipRegion(_window(obj)->WLayer, data->ClipRegion);

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
    //RectFill(rp, left, top, right, bottom);

    /* Draw the grid */
    SetAPen(rp, data->Pen_Grid);
    for (i=0; i <= GRID_DIVX; i++) { /* divisions for X-axis */
        ULONG x = left + width * i / GRID_DIVX;

        Move(rp, x, top);
        Draw(rp, x, bottom);
    }
    for (i=0; i <= GRID_DIVY; i++) { /* divisions for Y-axis */
        ULONG y = top + height * i / GRID_DIVY;

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
            
            if (node == data->GrabNode) {
                SetDrMd(rp, COMPLEMENT);
                DrawCircle(rp, x0, y0, KNOT_RADIUS);
                SetDrMd(rp, JAM1);
            } else
                RectFill(rp, x0-KNOT_RADIUS, y0-KNOT_RADIUS, x0+KNOT_RADIUS, y0+KNOT_RADIUS);   
        }
    }

    InstallClipRegion(_window(obj)->WLayer, oldregion);

    return 0;
}
//-
//+ mHandleEvent
static ULONG mHandleEvent(struct IClass *cl, Object *obj, struct MUIP_HandleEvent *msg)
{
    #define _isinobject(x,y) (_between(_mleft(obj),(x),_mright(obj)) && _between(_mtop(obj),(y),_mbottom(obj)))

    Data *data = INST_DATA(cl, obj);
    
    if (NULL != msg->imsg) {
        switch (msg->imsg->Class) {
            case IDCMP_VANILLAKEY:
                if (NULL != data->GrabNode) { /* In grab mode */
                    switch (msg->imsg->Code) {
                        case 0x08:
                        case 0x7f:
                            /* Delete selected */
                            del_knot(data, data->GrabNode);
                            data->GrabNode = NULL;

                            DoMethod(_win(obj), MUIM_Window_RemEventHandler, &data->EventNode);
                            data->EventNode.ehn_Events &= ~(IDCMP_MOUSEMOVE | IDCMP_VANILLAKEY);
                            DoMethod(_win(obj), MUIM_Window_AddEventHandler, &data->EventNode);

                            MUI_Redraw(obj, MADF_DRAWOBJECT);
                            return MUI_EventHandlerRC_Eat;

                        default:
                    }
                }
                break;

            case IDCMP_MOUSEBUTTONS:
                {
                    BOOL down = (msg->imsg->Code & IECODE_UP_PREFIX) == 0;
                    BOOL button = msg->imsg->Code & (IECODE_LBUTTON|IECODE_MBUTTON|IECODE_RBUTTON);
                    FLOAT fx, fy;
                    KnotNode *node;

                    /* Convert raster position into [0.0, 1.0] range */
                    fx = (FLOAT)(msg->imsg->MouseX - _mleft(obj)) / (_mwidth(obj) - 1);
                    fy = 1.0 - (FLOAT)(msg->imsg->MouseY - _mtop(obj)) / (_mheight(obj) - 1);
 
                    if (_isinobject(msg->imsg->MouseX, msg->imsg->MouseY)) {
                        if (NULL == data->GrabNode) { /* Not in grab mode */
                            if ((button == IECODE_LBUTTON) && down) {
                                FLOAT fr;

                                /* convert pixel radius into float radius */
                                fr = (FLOAT)(KNOT_RADIUS+1) / (_mwidth(obj) - 1);

                                node = find_knot(data, fx, fy, fr);
                                if (NULL != node) { /* Click on an existing knot */
                                    data->GrabNode = node; /* Enter in grab mode */
                                    set_knot(node, fx, fy); /* move the knot */
                                } else { /* New knot wanted */
                                    node = add_knot(data, fx, fy); /* may return an existing node if user click
                                                                    * just perfectly on the same y-level.
                                                                    */
                                    data->GrabNode = node; /* Enter in grab mode */
                                    set_knot(node, fx, fy); /* move the knot */
                                }

                                data->Old = node->kn_Position;

                                /* We enter in grab mode => listen to mouse move */
                                DoMethod(_win(obj), MUIM_Window_RemEventHandler, &data->EventNode);
                                data->EventNode.ehn_Events |= IDCMP_MOUSEMOVE | IDCMP_VANILLAKEY;
                                DoMethod(_win(obj), MUIM_Window_AddEventHandler, &data->EventNode);

                                MUI_Redraw(obj, MADF_DRAWOBJECT);
                                return MUI_EventHandlerRC_Eat;
                            }
                        }
                    }

                    if (NULL != data->GrabNode) { /* In grab mode */
                        if ((button == IECODE_LBUTTON) && !down) {
                            /* Was in grab mode => confirm node position and return to normal mode */
                            set_knot(data->GrabNode, data->GrabNode->kn_Position.x, data->GrabNode->kn_Position.y);
                            data->GrabNode = NULL;
                            data->LastAdded = NULL; /* or it can be deleted to next move+rbutton */

                            /* We leave grab mode => stop to listen to mouse move */
                            DoMethod(_win(obj), MUIM_Window_RemEventHandler, &data->EventNode);
                            data->EventNode.ehn_Events &= ~(IDCMP_MOUSEMOVE | IDCMP_VANILLAKEY);
                            DoMethod(_win(obj), MUIM_Window_AddEventHandler, &data->EventNode);

                            MUI_Redraw(obj, MADF_DRAWOBJECT);
                        }

                        if ((button == IECODE_RBUTTON) && down) {
                            /* Cancel move/delete new knot and leave the grab mode */
                            if (data->LastAdded == data->GrabNode)
                                del_knot(data, data->GrabNode);
                            else
                                set_knot(data->GrabNode, data->Old.x, data->Old.y);
                            data->GrabNode = NULL;

                            DoMethod(_win(obj), MUIM_Window_RemEventHandler, &data->EventNode);
                            data->EventNode.ehn_Events &= ~(IDCMP_MOUSEMOVE | IDCMP_VANILLAKEY);
                            DoMethod(_win(obj), MUIM_Window_AddEventHandler, &data->EventNode);

                            MUI_Redraw(obj, MADF_DRAWOBJECT);
                        }

                        return MUI_EventHandlerRC_Eat;
                    }
                }
                break;

            case IDCMP_MOUSEMOVE:
                if (_isinobject(msg->imsg->MouseX, msg->imsg->MouseY)) {
                    FLOAT fx, fy;

                    /* We suppose that we are in grab mode if IDCMP_MOUSEMOVE is set */

                    /* Convert raster position into [0.0, 1.0] range */
                    fx = (FLOAT)(msg->imsg->MouseX - _mleft(obj)) / (_mwidth(obj) - 1);
                    fy = 1.0 - (FLOAT)(msg->imsg->MouseY - _mtop(obj)) / (_mheight(obj) - 1);

                    set_knot(data->GrabNode, fx, fy);
                    MUI_Redraw(obj, MADF_DRAWOBJECT);

                    return MUI_EventHandlerRC_Eat;
                }
                break;
        }
    }

    return 0;
}
//-
//+ mDeleteAll
static ULONG mDeleteAll(struct IClass *cl, Object *obj, Msg msg)
{
    Data *data = INST_DATA(cl, obj);
    KnotNode *node, *head, *tail;
    APTR next;

    head = (APTR)GetHead(&data->KnotList);
    tail = (APTR)GetTail(&data->KnotList);

    /* Remove all knots, except head and tail ones */
    ForeachNodeSafe(&data->KnotList, node, next) {
        if ((node != head) && (node != tail))
            FreeMem(node, sizeof(*node));
    }
    NEWLIST(&data->KnotList);

    /* Reset head and tail knots */
    ADDHEAD(&data->KnotList, head);
    ADDTAIL(&data->KnotList, tail);
    
    set_knot(head, 0.0, 0.0);
    set_knot(tail, 1.0, 1.0);

    MUI_Redraw(obj, MADF_DRAWOBJECT);
    return 0;
}
//-
//+ mMapValue
static ULONG mMapValue(struct IClass *cl, Object *obj, struct MP_Curve_MapValue *msg)
{
    Data *data = INST_DATA(cl, obj);
    KnotNode *succ, *pred;

    if ((*msg->Value < 0.0) || (*msg->Value > 1.0))
        return FALSE;

    succ = (APTR)GetHead(&data->KnotList); 

    /* handle case where x = 0.0 */
    if (*msg->Value == 0.0) {
        *msg->Value = succ->kn_Position.y;
        return TRUE;
    }

    /* Search the right segment (pred, succ) */
    for (;;) {
        pred = succ;
        succ = (APTR)GetSucc(succ);
        
        if (NULL == succ)
            return FALSE;
        
        if (succ->kn_Position.x < *msg->Value)
            continue;

        /* Linear interpolation */
        *msg->Value = pred->kn_Position.y
            + ((*msg->Value - pred->kn_Position.x) * (succ->kn_Position.y - pred->kn_Position.y))
            / (succ->kn_Position.x - pred->kn_Position.x);

        return TRUE;
    }
}
//-
//+ _Dispatcher
ULONG _Dispatcher(VOID)
{
    struct IClass *cl = (APTR)REG_A0;
    Object *obj = (APTR)REG_A2;
    Msg msg = (APTR)REG_A1;
 
    switch (msg->MethodID) {
        case OM_NEW            : return mNew        (cl, obj, (APTR)msg);
        case OM_DISPOSE        : return mDispose    (cl, obj, (APTR)msg);
        case MUIM_AskMinMax    : return mAskMinMax  (cl, obj, (APTR)msg);
        case MUIM_Setup        : return mSetup      (cl, obj, (APTR)msg);
        case MUIM_Cleanup      : return mCleanup    (cl, obj, (APTR)msg);
        case MUIM_Show         : return mShow       (cl, obj, (APTR)msg);
        case MUIM_Hide         : return mHide       (cl, obj, (APTR)msg);
        case MUIM_Draw         : return mDraw       (cl, obj, (APTR)msg);
        case MUIM_HandleEvent  : return mHandleEvent(cl, obj, (APTR)msg);
        case MM_Curve_DeleteAll: return mDeleteAll  (cl, obj, (APTR)msg);
        case MM_Curve_MapValue : return mMapValue   (cl, obj, (APTR)msg);
    }

    return DoSuperMethodA(cl, obj, msg);
}
//-

/* EOF */
