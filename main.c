#include <private/mui2intuition/mui.h>
#include <libraries/mui.h>
#include <libraries/gadtools.h>
#include <utility/hooks.h>

#undef USE_INLINE_STDARG
#include <clib/alib_protos.h>
#include <proto/muimaster.h>
#include <proto/intuition.h>      
#define USE_INLINE_STDARG

#include <proto/exec.h>
#include <proto/graphics.h>

#include <Python.h>
//#include <proto/python.h>

#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <stdarg.h>
#include <ctype.h>

#ifndef MAKE_ID
#define MAKE_ID(a,b,c,d) ((ULONG) (a)<<24 | (ULONG) (b)<<16 | (ULONG) (c)<<8 | (ULONG) (d))
#endif

#define INIT_HOOK(h, f) { struct Hook *_h = (struct Hook *)(h); \
    _h->h_Entry = (APTR) HookEntry; \
    _h->h_SubEntry = (APTR) (f); }

#ifndef DISPATCHER
#define DISPATCHER(Name) \
static ULONG Name##_Dispatcher(void); \
static struct EmulLibEntry GATE ##Name##_Dispatcher = { TRAP_LIB, 0, (void (*)(void)) Name##_Dispatcher }; \
static ULONG Name##_Dispatcher(void) { struct IClass *cl=(struct IClass*)REG_A0; Msg msg=(Msg)REG_A1; Object *obj=(Object*)REG_A2;
#define DISPATCHER_REF(Name) &GATE##Name##_Dispatcher
#define DISPATCHER_END }
#endif

#define Image(f) MUI_NewObject(MUIC_Dtpic, MUIA_Dtpic_Name, f, MUIA_Dtpic_LightenOnMouse, TRUE, TAG_DONE)
#define BrushObject(f) NewObject(gImageMCC->mcc_Class, NULL, \
    MUIA_Dtpic_Name, (f), \
    MUIA_Dtpic_Scale, BRUSH_SIZE, \
    TAG_DONE)

#define LAST_COLORS_NUM 4
#define BRUSH_SIZE 64

#define FATAL_PYTHON_ERROR "Fatal Python error."

#define RB CHECKIT
#define TG CHECKIT|MENUTOGGLE

enum {
    MEN_PROJECT=1,
    MEN_QUIT,
};

struct NewMenu MenuData1[] =
{
    { NM_TITLE, "Project"                  ,"P",0 ,0             ,(APTR)MEN_PROJECT  },
    { NM_ITEM ,  "Quit"                    ,"Q",0 ,0             ,(APTR)MEN_QUIT     },

    { NM_END,NULL,0,0,0,(APTR)0 },
};

extern struct Library *PythonBase;
extern void dprintf();

PyObject *gPyApp = NULL;
Object *gApp, *gWinDraw, *gActiveBrush, *gColor=NULL;
struct Hook hook_ColorChanged;
ULONG gLastColors[3*LAST_COLORS_NUM] = {0};
ULONG gLastColorId=0;
struct MUI_CustomClass *gImageMCC;

ULONG __stack = 1024*128;

//+ do_ColorWindow
static Object *do_ColorWindow(void)
{
    Object *win, *ca, *cn;

    win = WindowObject,
        MUIA_Window_ID, MAKE_ID('C', 'O', 'L', '1'),
        MUIA_Window_Title, "Color",
        WindowContents, VGroup,
            Child, ca = ColoradjustObject, End,
            Child, RectangleObject,
                MUIA_Weight, 0,
                MUIA_Rectangle_HBar, TRUE,
            End,
            Child, HGroup,
                Child, ColGroup(2),
                    Child, Label2("Hex value:"),
                    Child, cn = StringObject,
                        MUIA_String_Accept, "0123456789abcdefABCDEF",
                        MUIA_String_MaxLen, 7,
                        MUIA_FixWidthTxt, "#000000",
                    End,
                End,
                Child, HSpace(0),
            End,
        End,
    End;

    if (NULL != win) {
        /* Close window when requested */
        DoMethod(win, MUIM_Notify, MUIA_Window_CloseRequest, TRUE,
                 MUIV_Notify_Self, 3, MUIM_Set, MUIA_Window_Open, FALSE);
        DoMethod(ca, MUIM_Notify, MUIA_Coloradjust_RGB, MUIV_EveryTime,
                 MUIV_Notify_Self, 4, MUIM_CallHook, &hook_ColorChanged, MUIV_TriggerValue, cn);
        gColor = ca;
    }

    return win;
}
//-
//+ free_app
static void free_app(void *app)
{
    MUI_DisposeObject(gApp);
}
//-
//+ free_mo
static void free_mo(void *mo)
{
    Object *parent;

    if (get(mo, MUIA_Parent, &parent) && (NULL == parent))
        MUI_DisposeObject(mo);
}
//-

/*-----------------------------------------------------------------------------------------------------------*/      

typedef struct ImageMCCData {
    struct MUI_EventHandlerNode ehnode;
    BOOL selected;
} ImageMCCData;

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
    ImageMCCData *data = INST_DATA(cl, obj);   
    int pen;

    DoMethod(obj,MUIM_DrawBackground, _mleft(obj), _mtop(obj), _mwidth(obj), _mheight(obj), 0, 0, 0);
    DoSuperMethodA(cl, obj, msg);

    if (!(msg->flags & (MADF_DRAWOBJECT|MADF_DRAWUPDATE)))
        return 0;

    if (data->selected)
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
    ImageMCCData *data = INST_DATA(cl, obj);  
    
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
    ImageMCCData *data = INST_DATA(cl, obj);  
    
    DoMethod(_win(obj), MUIM_Window_RemEventHandler, &data->ehnode);

    return DoSuperMethodA(cl, obj, msg);
}
//-
//+ mHandleEvent
static ULONG mHandleEvent(struct IClass *cl, Object *obj, struct MUIP_HandleEvent *msg)
{
    #define _between(a,x,b) ((x)>=(a) && (x)<=(b))
    #define _isinobject(x,y) (_between(_mleft(obj),(x),_mright(obj)) && _between(_mtop(obj),(y),_mbottom(obj)))

    ImageMCCData *data = INST_DATA(cl, obj);

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
            case IDCMP_MOUSEBUTTONS: {
                if (SELECTDOWN == msg->imsg->Code) {
                    if (_isinobject(msg->imsg->MouseX, msg->imsg->MouseY)) {
                        STRPTR name = NULL;
                        
                        if (get(obj, MUIA_Dtpic_Name, &name) && name) {
                            Py_XDECREF(PyObject_CallMethod(gPyApp, "OnSelectedBrush", "s", name));
                        }
                    }
                }
            }
            break;

            case IDCMP_MOUSEMOVE:
                if (_isinobject(msg->imsg->MouseX, msg->imsg->MouseY)) {
                    data->selected = TRUE;
                    MUI_Redraw(obj, MADF_DRAWUPDATE);
                } else if (data->selected) {
                    data->selected = FALSE;
                    MUI_Redraw(obj, MADF_DRAWUPDATE);            
                }
                break;
        }
    }

    return 0;
}
//-

//+ DISPATCHER(ImageMCC)
DISPATCHER(ImageMCC)
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

//+ core_image
static PyObject *core_image(PyObject *self, PyObject *args)
{
    STRPTR fn;

    if (!PyArg_ParseTuple(args, "s:mui_image", &fn))
        return NULL;
    
    return PyCObject_FromVoidPtr(BrushObject(fn), free_mo);
}
//-
//+ core_active_brush
static PyObject *core_active_brush(PyObject *self, PyObject *args)
{
    STRPTR name;

    if (!PyArg_ParseTuple(args, "s:set_active_brush", &name))
        return NULL;

    set(gActiveBrush, MUIA_Dtpic_Name, name);
    
    Py_RETURN_NONE;
}
//-
//+ core_set_color
static PyObject *core_set_color(PyObject *self, PyObject *args)
{
    ULONG rgb[3], r, g, b;

    if (!PyArg_ParseTuple(args, "III:set_color", &r, &g, &b))
        return NULL;

    if (NULL != gColor) {        
        rgb[0] = MAKE_ID(r,r,r,r);
        rgb[1] = MAKE_ID(g,g,g,g);
        rgb[2] = MAKE_ID(b,b,b,b);

        set(gColor, MUIA_Coloradjust_RGB, rgb);
    }

    Py_RETURN_NONE;
}
//-
//+ core_get_color
static PyObject *core_get_color(void)
{
    ULONG rgb[3];

    get(gColor, MUIA_Coloradjust_RGB, rgb);

    return Py_BuildValue("III", rgb[0]>>24, rgb[1]>>24, rgb[2]>>24);
}
//-
//+ core_color_gui
static PyObject *core_color_gui(void)
{
    Object *mo = do_ColorWindow();

    if (NULL == mo) {
        PyErr_SetString(PyExc_SystemError, "MUI Color Window failed");
        return NULL;
    }

    return PyCObject_FromVoidPtr(mo, free_mo);
}
//-
//+ core_create_app
static PyObject *core_create_app(void)
{
    Object *strip;
    Object *mo = ApplicationObject,
        MUIA_Application_Title      , "Gribouillis",
        MUIA_Application_Version    , "$VER: Gribouillis "VERSION_STR" (" __DATE__ ")",
        MUIA_Application_Copyright  , "©2009, Guillaume ROGUEZ",
        MUIA_Application_Author     , "Guillaume ROGUEZ",
        MUIA_Application_Description, "Simple Painting program for MorphOS",
        MUIA_Application_Base       , "Gribouillis",

        MUIA_Application_Menustrip, strip = MUI_MakeObject(MUIO_MenustripNM, MenuData1, MUIO_MenustripNM_CommandKeyCheck),

        SubWindow, gWinDraw = WindowObject,
            MUIA_Window_Title, "Gribouillis",
            MUIA_Window_ID, MAKE_ID('D','R','A','W'),
            MUIA_Window_Open, TRUE,
            //MUIA_Window_Backdrop, TRUE,
            //MUIA_Window_DepthGadget, FALSE,
            WindowContents, VGroup,
                Child, RectangleObject,
                    MUIA_Background, MUII_SHINE,
                    MUIA_FixWidth, 320,
                    MUIA_FixHeight, 320,
                End,
            End,
        End,
    End;

    gApp = mo;

    if (NULL == mo) {
        PyErr_SetString(PyExc_SystemError, "MUI Application creation failed");
        return NULL;
    }

    return PyCObject_FromVoidPtr(mo, free_app);
}
//-
//+ core_win_open
static PyObject *core_win_open(PyObject *self, PyObject *args)
{
    PyObject *pyo;
    char state = TRUE;

    if (!PyArg_ParseTuple(args, "O!|b:win_open", &PyCObject_Type, &pyo, &state)) /* BR */
        return NULL;

    set(PyCObject_AsVoidPtr(pyo), MUIA_Window_Open, state);

    Py_RETURN_NONE;
}
//-
//+ core_add_member
static PyObject *core_add_member(PyObject *self, PyObject *args)
{
    PyObject *pyo1, *pyo2;

    if (!PyArg_ParseTuple(args, "O!O!:add_member", &PyCObject_Type, &pyo1, &PyCObject_Type, &pyo2)) /* BR */
        return NULL;

    DoMethod(PyCObject_AsVoidPtr(pyo1), OM_ADDMEMBER, PyCObject_AsVoidPtr(pyo2));

    Py_RETURN_NONE;
}
//-

//+ CoreMethods
static PyMethodDef CoreMethods[] = {
    {"mui_image", core_image, METH_VARARGS, NULL},
    {"set_active_brush", core_active_brush, METH_VARARGS, NULL},
    {"set_color", core_set_color, METH_VARARGS, NULL},
    {"get_color", (PyCFunction)core_get_color, METH_NOARGS, NULL},
    {"create_color_gui", (PyCFunction)core_color_gui, METH_NOARGS, NULL},
    {"create_app", (PyCFunction)core_create_app, METH_NOARGS, NULL},
    {"win_open", core_win_open, METH_VARARGS, NULL},
    {"add_member", core_add_member, METH_VARARGS, NULL},
    {0}
};
//-

/*-----------------------------------------------------------------------------------------------------------*/      

//+ exit_handler
void exit_handler(void)
{
    if (PyErr_Occurred())
        PyErr_Print();
 
    Py_XDECREF(gPyApp);       
    Py_Finalize();

    MUI_DeleteCustomClass(gImageMCC);        
}
//-
//+ fail
static VOID fail(char *str)
{
    if (str) {
        puts(str);
        exit(20);
    }

    exit(0);
}
//-
//+ OnColorChanged
static void OnColorChanged(struct Hook *hook, Object *caller, ULONG *args)
{
    ULONG *rgb = (ULONG *)args[0];
    Object *cn = (Object *)args[1];
    char buf[7];

    /* Change the Color name string */
    sprintf(buf, "%02X%02X%02X", rgb[0]>>24, rgb[1]>>24, rgb[2]>>24);
    set(cn, MUIA_String_Contents, buf);

    /* Notify the Python Application */
    Py_XDECREF(PyObject_CallMethod(gPyApp, "OnColor", "III", rgb[0]>>24, rgb[1]>>24, rgb[2]>>24));
}
//-
//+ do_BrushSelectWindow
static Object *do_BrushSelectWindow(void)
{
    Object *win, *vg;

    win = WindowObject,
        MUIA_Window_ID, MAKE_ID('B', 'S', 'E', 'L'),
        MUIA_Window_Title, "Brush selection",
        WindowContents, VGroup,
            Child, HGroup,
                Child, gActiveBrush = BrushObject("PROGDIR:brushes/ink_prev.png"),
                Child, HSpace(0),
            End,
            Child, RectangleObject,
                MUIA_Rectangle_HBar, TRUE,
                MUIA_FixHeight, 8,
            End,
            Child, ScrollgroupObject,
                MUIA_Scrollgroup_FreeHoriz, FALSE,
                MUIA_Scrollgroup_Contents, vg = ColGroupV(4), End,
            End,
        End,
    End;

    if (NULL != win) {
        PyObject *names;

        /* Close window when requested */
        DoMethod(win, MUIM_Notify, MUIA_Window_CloseRequest, TRUE,
                 MUIV_Notify_Self, 3, MUIM_Set, MUIA_Window_Open, FALSE);

        names = PyObject_GetAttrString(gPyApp, "brushes"); /* NR */
        if ((NULL != names) && PyList_Check(names)) {
            int i;

            DoMethod(vg, MUIM_Group_InitChange, TRUE);
            for (i=0; i < PyList_GET_SIZE(names); i++) {
                Object *mo;
                PyObject *pyo;

                pyo = PyObject_GetAttrString(PyList_GET_ITEM(names, i) /* BR */, "muio"); /* NR */
                if (NULL != pyo) {
                    mo = PyCObject_AsVoidPtr(pyo);
                    if (NULL != mo)
                        DoMethod(vg, OM_ADDMEMBER, mo);
                    Py_DECREF(pyo);
                }
            }
            DoMethod(vg, MUIM_Group_InitChange, FALSE);
        }

        Py_XDECREF(names);
        PyErr_Clear();
    }

    return win;
}
//-
//+ main
int main(int argc, char **argv)
{
    BOOL run = TRUE;
    LONG sigs, res;
    PyObject *m, *d;

    /*--- Hooks ---*/
    INIT_HOOK(&hook_ColorChanged, OnColorChanged);
    
    /*--- Python initialisation ---*/
    res = PyMorphOS_Init(&argc, &argv);
    if (res != RETURN_OK) return res;

    Py_SetProgramName(argv[0]);
    Py_Initialize();
    PySys_SetArgv(argc, argv);

    atexit(exit_handler);   
 
    /*--- MCCs creation ---*/
    gImageMCC = MUI_CreateCustomClass(NULL, MUIC_Dtpic, NULL, sizeof(ImageMCCData), DISPATCHER_REF(ImageMCC));
    if (NULL == gImageMCC)
        fail("Failed to create MCC 'Image'");

    /*--- Python script running ---*/

    m = PyImport_AddModule("__main__"); /* BR */
    if (NULL == m)
        fail(FATAL_PYTHON_ERROR);

    Py_InitModule("_core", CoreMethods);

    d = PyModule_GetDict(m); /* BR */

    /* Create the Python side of the application */
    if (PyRun_SimpleString("from startup import start"))
        fail(FATAL_PYTHON_ERROR);

    /* Create the Python application */
    gPyApp = PyRun_String("start()", Py_eval_input, d, d); /* NR */
    if (NULL == gPyApp)
        fail(FATAL_PYTHON_ERROR);

    /*--- Install MUI Notifications ---*/
    DoMethod(gWinDraw, MUIM_Notify, MUIA_Window_CloseRequest, TRUE,
             gApp, 2, MUIM_Application_ReturnID, MUIV_Application_ReturnID_Quit);

    #if 0
    /* 'c' pressed => Open Color window */
    DoMethod(gWinDraw, MUIM_Notify, MUIA_Window_InputEvent, "c",
             gWinColor, 3, MUIM_Set, MUIA_Window_Open, TRUE);

    /* 'b' pressed => Open Brush Selection window */
    DoMethod(gWinDraw, MUIM_Notify, MUIA_Window_InputEvent, "b",
             gWinBrushSelect, 3, MUIM_Set, MUIA_Window_Open, TRUE);
    #endif

    while (run) {
        ULONG id = DoMethod(gApp, MUIM_Application_Input, &sigs);

        switch (id) {
            case MUIV_Application_ReturnID_Quit:
            case MEN_QUIT:
                run = FALSE;
                break;
        }
        if (run && sigs) Wait(sigs);
    }

    fail(NULL);
    return 0;
}
//-
