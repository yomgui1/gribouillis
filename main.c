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

extern void dprintf();

#define INIT_HOOK(h, f) { struct Hook *_h = (struct Hook *)(h); \
    _h->h_Entry = (APTR) HookEntry; \
    _h->h_SubEntry = (APTR) (f); }

#define Image(f) MUI_NewObject(MUIC_Dtpic, MUIA_Dtpic_Name, f, TAG_DONE)
#define BrushObject(f) MUI_NewObject(MUIC_Dtpic, \
    MUIA_Dtpic_Name, (f), \
    MUIA_Dtpic_Scale, BRUSH_SIZE, \
    MUIA_Dtpic_LightenOnMouse, TRUE, \
    MUIA_InputMode, MUIV_InputMode_Toggle, \
    MUIA_Frame, MUIV_Frame_ImageButton, \
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

PyObject *gPyGlobalDict = NULL, *gPyApp = NULL;
Object *gWinColor, *gWinBrushSelect;
struct Hook hook_ColorChanged;
ULONG gLastColors[3*LAST_COLORS_NUM] = {0};
ULONG gLastColorId=0;

ULONG __stack = 1024*128;

//+ fail
static VOID fail(APTR app,char *str)
{
    if (app)
        MUI_DisposeObject(app);

    if (PyErr_Occurred())
        PyErr_Print();

    Py_Finalize();

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

    /* Save this one as the last color used */

}
//-
//+ do_ColorWindow
static Object *do_ColorWindow(void)
{
    Object *win, *ca, *cn;

    win = gWinColor = WindowObject,
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
    }

    return win;
}
//-
//+ do_BrushSelectWindow
static Object *do_BrushSelectWindow(void)
{
    Object *win, *vg;

    win = gWinBrushSelect = WindowObject,
        MUIA_Window_ID, MAKE_ID('B', 'S', 'E', 'L'),
        MUIA_Window_Title, "Brush selection",
        WindowContents, HGroup,
            Child, ScrollgroupObject,
                MUIA_Scrollgroup_FreeHoriz, FALSE,
                MUIA_Scrollgroup_Contents, vg = ColGroupV(6), End,
            End,
        End,
    End;

    if (NULL != win) {
        PyObject *names;

        /* Close window when requested */
        DoMethod(win, MUIM_Notify, MUIA_Window_CloseRequest, TRUE,
                 MUIV_Notify_Self, 3, MUIM_Set, MUIA_Window_Open, FALSE);

        names = PyObject_GetAttrString(gPyApp, "brushes_names");
        if ((NULL != names) && PyList_Check(names)) {
            int i;

            DoMethod(vg, MUIM_Group_InitChange, TRUE);
            for (i=PyList_GET_SIZE(names); i; i--) {
                Object *mo;
                STRPTR name;

                name = PyString_AsString(PyList_GET_ITEM(names, i));
                printf("Load brush image '%s'\n", name);
                mo = BrushObject(name);
                if (NULL != mo)
                    DoMethod(vg, OM_ADDMEMBER, mo);
            }
            DoMethod(vg, MUIM_Group_InitChange, FALSE);
        } else
            printf("bad names: %p\n", names);

        Py_XDECREF(names);
        PyErr_Clear();
    }

    return win;
}
//-
//+ main
int main(int argc, char **argv)
{
    Object *app, *win_main, *strip;
    BOOL run = TRUE;
    LONG sigs, res;
    PyObject *m;
    
    /*--- Python startup ---*/
    res = PyMorphOS_Init(&argc, &argv);
    if (res != RETURN_OK) return res;

    Py_SetProgramName(argv[0]);
    Py_Initialize();
    PySys_SetArgv(argc, argv);

    m = PyImport_AddModule("__main__");
    if (NULL == m)
        fail(NULL, FATAL_PYTHON_ERROR);

    gPyGlobalDict = PyModule_GetDict(m);
    if (NULL == gPyGlobalDict)
        fail(NULL, FATAL_PYTHON_ERROR);

    /* Create the Python side of the application */
    PyRun_String("import os, startup; app=startup.Application(os.getcwd())", Py_file_input, gPyGlobalDict, gPyGlobalDict);
    gPyApp = PyDict_GetItemString(gPyGlobalDict, "app");
    if (NULL == gPyApp)
        fail(NULL, FATAL_PYTHON_ERROR);

    //Py_INCREF(gPyApp);

    /*--- Hooks ---*/
    INIT_HOOK(&hook_ColorChanged, OnColorChanged);

    /*--- GUI ---*/
    app = ApplicationObject,
        MUIA_Application_Title      , "Gribouillis",
        MUIA_Application_Version    , "$VER: Gribouillis "VERSION_STR" (" __DATE__ ")",
        MUIA_Application_Copyright  , "©2009, Guillaume ROGUEZ",
        MUIA_Application_Author     , "Guillaume ROGUEZ",
        MUIA_Application_Description, "Simple Painting program for MorphOS",
        MUIA_Application_Base       , "Gribouillis",

        MUIA_Application_Menustrip, strip = MUI_MakeObject(MUIO_MenustripNM, MenuData1, MUIO_MenustripNM_CommandKeyCheck),

        SubWindow, win_main = WindowObject,
            MUIA_Window_Title, "Gribouillis",
            MUIA_Window_ID, MAKE_ID('D','R','A','W'),
            MUIA_Window_Backdrop, TRUE,
            MUIA_Window_DepthGadget, FALSE,
            WindowContents, VGroup,
                Child, VSpace(0),
                Child, HCenter(SimpleButton("jfgjdfklgjdflgjkd")),
                Child, VSpace(0),
            End,
        End,

        SubWindow, do_ColorWindow(),
        SubWindow, do_BrushSelectWindow(),
    End;

    if (!app)
        fail(app, "Failed to create Application.");

    /*--- Install MUI Notifications ---*/
    DoMethod(win_main, MUIM_Notify, MUIA_Window_CloseRequest, TRUE,
             app, 2, MUIM_Application_ReturnID, MUIV_Application_ReturnID_Quit);

    /* 'c' pressed => Open Color window */
    DoMethod(win_main, MUIM_Notify, MUIA_Window_InputEvent, "c",
             gWinColor, 3, MUIM_Set, MUIA_Window_Open, TRUE);

    /* 'b' pressed => Open Brush Selection window */
    DoMethod(win_main, MUIM_Notify, MUIA_Window_InputEvent, "b",
             gWinBrushSelect, 3, MUIM_Set, MUIA_Window_Open, TRUE);

    /* Open Windows now */
    set(win_main, MUIA_Window_Open, TRUE);
    set(gWinColor, MUIA_Window_Open, TRUE);
    set(gWinBrushSelect, MUIA_Window_Open, TRUE);

    while (run) {
        ULONG id = DoMethod(app, MUIM_Application_Input, &sigs);

        switch (id) {
            case MUIV_Application_ReturnID_Quit:
            case MEN_QUIT:
                run = FALSE;
                break;
        }
        if (run && sigs) Wait(sigs);
    }

    set(win_main, MUIA_Window_Open, FALSE);

    fail(app, NULL);
    return 0;
}
//-
