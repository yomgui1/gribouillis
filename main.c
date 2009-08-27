#include <Python.h>

#include "brush_mcc.h"

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

#define Image(f) MUI_NewObject(MUIC_Dtpic, MUIA_Dtpic_Name, f, MUIA_Dtpic_LightenOnMouse, TRUE, TAG_DONE)

#define LAST_COLORS_NUM 4
#define BRUSH_SIZE 64
#define FATAL_PYTHON_ERROR "Fatal Python error."
#define RB CHECKIT
#define TG CHECKIT|MENUTOGGLE

enum {
    MEN_PROJECT=1,
};

struct NewMenu MenuData1[] =
{
    { NM_TITLE, "Project"                  ,"P",0 ,0             ,(APTR)MEN_PROJECT  },
    { NM_ITEM ,  "Quit"                    ,"Q",0 ,0             ,(APTR)MUIV_Application_ReturnID_Quit },

    { NM_END,NULL,0,0,0,(APTR)0 },
};

extern struct Library *PythonBase;
extern void init_muimodule(void);
extern void dprintf();

PyObject *gPyApp = NULL;
Object *gActiveBrush, *gColor=NULL;
struct Hook hook_ColorChanged;
ULONG gLastColors[3*LAST_COLORS_NUM] = {0};
ULONG gLastColorId=0;
struct MUI_CustomClass *gBrushMCC = NULL;

ULONG __stack = 1024*128;

//+ exit_handler
static void exit_handler(void)
{
    if (PyErr_Occurred())
        PyErr_Print();
 
    Py_XDECREF(gPyApp);
    Py_Finalize();

    if (NULL != gBrushMCC)
        BrushMCC_Term(gBrushMCC);
}
//-
//+ fail
static void fail(char *str)
{
    if (str) {
        puts(str);
        exit(20);
    }

    exit(0);
}
//-
//+ free_app
static void free_app(void *app)
{
    MUI_DisposeObject(app);
}
//-
//+ free_mo
static void free_mo(void *mo)
{
    Object *app, *parent;

    /* dispose only if not connected to an application and no parent */
    if (!get(mo, MUIA_ApplicationObject, &app) || !get(mo, MUIA_ApplicationObject, &parent)) {
        dprintf("Fatal gribouillis: unable free object %p!\n", mo);
        return;
    }
    
    if ((NULL == app) && (NULL == parent))
        MUI_DisposeObject(mo);
}
//-
//+ do_ColorWindow
static Object *do_ColorWindow(Object *cadjust)
{
    Object *win, *cn;

    win = WindowObject,
        MUIA_Window_ID, MAKE_ID('C', 'O', 'L', '1'),
        MUIA_Window_Title, "Color",
        WindowContents, VGroup,
            Child, cadjust,
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
        DoMethod(cadjust, MUIM_Notify, MUIA_Coloradjust_RGB, MUIV_EveryTime,
                 MUIV_Notify_Self, 4, MUIM_CallHook, &hook_ColorChanged, MUIV_TriggerValue, cn);
    }

    return win;
}
//-
//+ do_DrawingWindow
static Object *do_DrawingWindow(void)
{
    Object *win = WindowObject,
        MUIA_Window_Title, "Gribouillis",
        MUIA_Window_ID, MAKE_ID('D','R','A','W'),
        MUIA_Window_Open, TRUE,
        WindowContents, VGroup,
            Child, RectangleObject,
                MUIA_Background, MUII_SHINE,
                MUIA_FixWidth, 320,
                MUIA_FixHeight, 320,
            End,
        End,
    End;

    if (NULL != win) {
        DoMethod(win, MUIM_Notify, MUIA_Window_CloseRequest, TRUE,
                 MUIV_Notify_Application, 2, MUIM_Application_ReturnID, MUIV_Application_ReturnID_Quit);
    }

    return win;
}
//-
//+ do_App
static Object *do_App(void)
{
    Object *app = ApplicationObject,
        MUIA_Application_Title      , "Gribouillis",
        MUIA_Application_Version    , "$VER: Gribouillis "VERSION_STR" (" __DATE__ ")",
        MUIA_Application_Copyright  , "©2009, Guillaume ROGUEZ",
        MUIA_Application_Author     , "Guillaume ROGUEZ",
        MUIA_Application_Description, "Simple Painting program for MorphOS",
        MUIA_Application_Base       , "Gribouillis",

        MUIA_Application_Menustrip, MUI_MakeObject(MUIO_MenustripNM, MenuData1, MUIO_MenustripNM_CommandKeyCheck),
    End;

    return app;
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
    PyObject *pyo;

    if (!PyArg_ParseTuple(args, "O!III:set_color", &PyCObject_Type, &pyo, &r, &g, &b))
        return NULL;

    rgb[0] = MAKE_ID(r,r,r,r);
    rgb[1] = MAKE_ID(g,g,g,g);
    rgb[2] = MAKE_ID(b,b,b,b);

    set(PyCObject_AsVoidPtr(pyo), MUIA_Coloradjust_RGB, rgb);

    Py_RETURN_NONE;
}
//-
//+ core_get_color
static PyObject *core_get_color(PyObject *pyo)
{
    ULONG rgb[3];

    if (!PyCObject_Check(pyo)) {
        PyErr_SetString(PyExc_TypeError, "get_color get a Coloradjust MUI object as argument");
        return NULL;
    }

    if (!get(PyCObject_AsVoidPtr(pyo), MUIA_Coloradjust_RGB, rgb)) {
        PyErr_SetString(PyExc_SystemError, "get(MUIA_Coloradjust_RGB) failed");
        return NULL;
    }

    return Py_BuildValue("III", rgb[0]>>24, rgb[1]>>24, rgb[2]>>24);
}
//-
//+ core_create_app
static PyObject *core_create_app(void)
{
    Object *app = do_App();

    if (NULL == app) {
        PyErr_SetString(PyExc_SystemError, "MUI Application creation failed");
        return NULL;
    }

    return PyCObject_FromVoidPtr(app, free_app);
}
//-
//+ core_do_win_color
static PyObject *core_do_win_color(PyObject *pyo)
{
    Object *mo;

    if (!PyCObject_Check(pyo)) {
        PyErr_SetString(PyExc_TypeError, "do_win_color get a Coloradjust MUI object as argument");
        return NULL;
    }

    mo = do_ColorWindow(PyCObject_AsVoidPtr(pyo));
    if (NULL == mo) {
        PyErr_SetString(PyExc_SystemError, "MUI Color Window failed");
        return NULL;
    }

    return PyCObject_FromVoidPtr(mo, free_mo);
}
//-
//+ core_do_win_drawing
static PyObject *core_do_win_drawing(void)
{
    Object *mo = do_DrawingWindow();

    if (NULL == mo) {
        PyErr_SetString(PyExc_SystemError, "MUI Drawing Window failed");
        return NULL;
    }

    return PyCObject_FromVoidPtr(mo, free_mo);
}
//-
//+ core_do_color_adjust
static PyObject *core_do_color_adjust(void)
{
    Object *mo = ColoradjustObject, End;

    if (NULL == mo) {
        PyErr_SetString(PyExc_SystemError, "MUI Color Window failed");
        return NULL;
    }

    return PyCObject_FromVoidPtr(mo, free_mo);
}
//-

//+ _CoreMethods
static PyMethodDef _CoreMethods[] = {
    {"create_app", (PyCFunction)core_create_app, METH_NOARGS, NULL},

    {"do_win_color", (PyCFunction)core_do_win_color, METH_O, NULL},
    {"do_win_drawing", (PyCFunction)core_do_win_drawing, METH_NOARGS, NULL},
    {"do_color_adjust", (PyCFunction)core_do_color_adjust, METH_NOARGS, NULL},

    {"mui_image", core_image, METH_VARARGS, NULL},
    {"set_active_brush", core_active_brush, METH_VARARGS, NULL},
    {"set_color", core_set_color, METH_VARARGS, NULL},
    {"get_color", (PyCFunction)core_get_color, METH_O, NULL},

    {0}
};
//-

/*-----------------------------------------------------------------------------------------------------------*/      

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
//+ main
int main(int argc, char **argv)
{
    LONG res;
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
    gBrushMCC = BrushMCC_Init();
    if (NULL == gBrushMCC)
        fail("Failed to create MCC 'Image'");

    /*--- Run Python scripts ---*/

    m = PyImport_AddModule("__main__"); /* BR */
    if (NULL == m)
        fail(FATAL_PYTHON_ERROR);

    d = PyModule_GetDict(m); /* BR */

    init_muimodule();
    Py_InitModule("_core", _CoreMethods);

    /* Create the Python side of the application */
    if (PyRun_SimpleString("from startup import start"))
        fail(FATAL_PYTHON_ERROR);

    /* Create the Python application */
    gPyApp = PyRun_String("start()", Py_eval_input, d, d); /* NR */
    if (NULL == gPyApp)
        fail(FATAL_PYTHON_ERROR);

    /* Run the mainloop */
    PyRun_SimpleString("app.mainloop()");

    return 0;
}
//-
