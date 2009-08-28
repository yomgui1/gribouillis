#include "common.h"
#include "brush_mcc.h"

#define Py_RETURN_MUIObject(s, o) \
    s = PyCObject_FromVoidPtr(o, free_mo); \
    if (NULL == s) free_mo(o); \
    return s;

#define Image(f) MUI_NewObject(MUIC_Dtpic, MUIA_Dtpic_Name, (f), TAG_DONE)

#define BRUSH_SIZE 64
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

static struct Hook hook_ColorChanged;
static Object *gActiveBrush;

//+ free_mo
static void free_mo(void *mo)
{
    Object *app, *parent;

    /* dispose only if not connected to an application and no parent */
    if (!get(mo, MUIA_ApplicationObject, &app) || !get(mo, MUIA_ApplicationObject, &parent)) {
        dprintf("Fatal gribouillis: unable free object %p!\n", mo);
        return;
    }
    
    dprintf("freeing mui obj: %p (app=%p, parent=%p)\n", mo, app, parent);

    if ((app == mo) || ((NULL == app) && (NULL == parent)))
        MUI_DisposeObject(mo);
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

    dprintf("New App: %p\n", app);

    return app;
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

    dprintf("New ColorWindow: %p\n", win);

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

    dprintf("New DrawingWindow: %p\n", win);

    if (NULL != win) {
        DoMethod(win, MUIM_Notify, MUIA_Window_CloseRequest, TRUE,
                 MUIV_Notify_Application, 2, MUIM_Application_ReturnID, MUIV_Application_ReturnID_Quit);
    }

    return win;
}
//-
//+ do_BrushSelectWindow
static Object *do_BrushSelectWindow(PyObject *app)
{
    Object *win, *vg;

    win = WindowObject,
        MUIA_Window_ID, MAKE_ID('B', 'S', 'E', 'L'),
        MUIA_Window_Title, "Brush selection",
        WindowContents, VGroup,
            Child, HGroup,
                GroupFrameT("Current brush"),
                Child, gActiveBrush = Image("PROGDIR:brushes/ink_prev.png"),
                Child, HSpace(0),
            End,
            Child, RectangleObject,
                MUIA_Rectangle_HBar, TRUE,
                MUIA_FixHeight, 8,
            End,
            Child, ScrollgroupObject,
                MUIA_Scrollgroup_FreeHoriz, FALSE,
                MUIA_Scrollgroup_Contents, vg = ColGroupV(4),
                    VirtualFrame,
                    InnerSpacing(0, 0),
                End,
            End,
        End,
    End;

    dprintf("New BrushSelectWindow: %p\n", win);

    if (NULL != win) {
        PyObject *names;

        /* Close window when requested */
        DoMethod(win, MUIM_Notify, MUIA_Window_CloseRequest, TRUE,
                 MUIV_Notify_Self, 3, MUIM_Set, MUIA_Window_Open, FALSE);

        names = PyObject_GetAttrString(app, "brushes"); /* NR */
        if ((NULL != names) && PyList_Check(names)) {
            int i;

            DoMethod(vg, MUIM_Group_InitChange, TRUE);
            for (i=0; i < PyList_GET_SIZE(names); i++) {
                Object *mo;
                PyObject *pyo;

                pyo = PyObject_GetAttrString(PyList_GET_ITEM(names, i) /* BR */, "mui"); /* NR */
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
//+ OnColorChanged
static void OnColorChanged(struct Hook *hook, Object *caller, ULONG *args)
{
    ULONG *rgb = (ULONG *)args[0];
    Object *cn = (Object *)args[1];
    char buf[7];
    UBYTE r, g, b;

    r = rgb[0]>>24;
    g = rgb[1]>>24;
    b = rgb[2]>>24;

    /* Change the Color name string */
    sprintf(buf, "%02X%02X%02X", r, g, b);
    set(cn, MUIA_String_Contents, buf);
}
//-

/*-----------------------------------------------------------------------------------------------------------*/      

//+ core_brush
static PyObject *core_brush(PyObject *self, PyObject *args)
{
    STRPTR fn;
    Object *mo;

    if (!PyArg_ParseTuple(args, "s:mui_brush", &fn))
        return NULL;

    mo = BrushObject(fn);
    dprintf("New Brush: %p\n", mo);

    if (NULL == mo) {
        PyErr_SetString(PyExc_SystemError, "MUI Brush failed");
        return NULL;
    }
    
    Py_RETURN_MUIObject(self, mo);
}
//-
//+ core_active_brush
static PyObject *core_active_brush(PyObject *self, PyObject *args)
{
    STRPTR name;

    if (!PyArg_ParseTuple(args, "s:set_active_brush", &name))
        return NULL;

    assert(gActiveBrush != NULL);
    set(gActiveBrush, MUIA_Dtpic_Name, name);
    
    Py_RETURN_NONE;
}
//-
//+ core_set_color
static PyObject *core_set_color(PyObject *self, PyObject *args)
{
    ULONG rgb[3], r, g, b;
    PyObject *pyo;
    Object *mo;

    if (!PyArg_ParseTuple(args, "O!III:set_color", &PyCObject_Type, &pyo, &r, &g, &b))
        return NULL;

    rgb[0] = MAKE_ID(r,r,r,r);
    rgb[1] = MAKE_ID(g,g,g,g);
    rgb[2] = MAKE_ID(b,b,b,b);

    mo = PyCObject_AsVoidPtr(pyo);
    assert(mo != NULL);
    set(mo, MUIA_Coloradjust_RGB, rgb);

    Py_RETURN_NONE;
}
//-
//+ core_get_color
static PyObject *core_get_color(PyObject *self, PyObject *pyo)
{
    ULONG *rgb;
    UBYTE r,g,b;

    if (!PyCObject_Check(pyo)) {
        PyErr_SetString(PyExc_TypeError, "get_color get a Coloradjust MUI object as argument");
        return NULL;
    }

    if (!get(PyCObject_AsVoidPtr(pyo), MUIA_Coloradjust_RGB, &rgb)) {
        PyErr_SetString(PyExc_SystemError, "get(MUIA_Coloradjust_RGB) failed");
        return NULL;
    }

    r = rgb[0] >> 24; g = rgb[1] >> 24; b = rgb[2] >> 24;
    return Py_BuildValue("BBB", r, g, b);
}
//-
//+ core_create_app
static PyObject *core_create_app(PyObject *self)
{
    Object *app = do_App();

    if (NULL == app) {
        PyErr_SetString(PyExc_SystemError, "MUI Application creation failed");
        return NULL;
    }

    Py_RETURN_MUIObject(self, app);
}
//-
//+ core_do_win_color
static PyObject *core_do_win_color(PyObject *self, PyObject *pyo)
{
    Object *mo;

    if (!PyCObject_Check(pyo))
        return PyErr_Format(PyExc_TypeError, "do_win_color needs Coloradjust MUI object as argument, not %s", pyo->ob_type->tp_name);

    mo = do_ColorWindow(PyCObject_AsVoidPtr(pyo));
    if (NULL == mo) {
        PyErr_SetString(PyExc_SystemError, "MUI Color Window failed");
        return NULL;
    }

    Py_RETURN_MUIObject(self, mo);
}
//-
//+ core_do_win_drawing
static PyObject *core_do_win_drawing(PyObject *self)
{
    Object *mo = do_DrawingWindow();

    if (NULL == mo) {
        PyErr_SetString(PyExc_SystemError, "MUI Drawing Window failed");
        return NULL;
    }

    Py_RETURN_MUIObject(self, mo);
}
//-
//+ core_do_win_brushselect
static PyObject *core_do_win_brushselect(PyObject *self, PyObject *app)
{
    Object *mo = do_BrushSelectWindow(app);

    if (NULL == mo) {
        PyErr_SetString(PyExc_SystemError, "MUI BrushSelect window failed");
        return NULL;
    }

    Py_RETURN_MUIObject(self, mo);
}
//-
//+ core_do_color_adjust
static PyObject *core_do_color_adjust(PyObject *self, PyObject *args)
{
    Object *mo = ColoradjustObject, End;

    dprintf("New Coloradjust: %p\n", mo);   

    if (NULL == mo) {
        PyErr_SetString(PyExc_SystemError, "MUI Color Window failed");
        return NULL;
    }

    Py_RETURN_MUIObject(self, mo);
}
//-

//+ _CoreMethods
static PyMethodDef _CoreMethods[] = {
    {"create_app", (PyCFunction)core_create_app, METH_NOARGS, NULL},

    {"do_win_color", (PyCFunction)core_do_win_color, METH_O, NULL},
    {"do_win_drawing", (PyCFunction)core_do_win_drawing, METH_NOARGS, NULL},
    {"do_win_brushselect", core_do_win_brushselect, METH_O, NULL},
    {"do_color_adjust", (PyCFunction)core_do_color_adjust, METH_NOARGS, NULL},

    {"mui_brush", core_brush, METH_VARARGS, NULL},
    {"set_active_brush", core_active_brush, METH_VARARGS, NULL},
    {"set_color", core_set_color, METH_VARARGS, NULL},
    {"get_color", (PyCFunction)core_get_color, METH_O, NULL},

    {0}
};
//-

//+ init_coremodule
void init_coremodule(void)
{
    INIT_HOOK(&hook_ColorChanged, OnColorChanged);
    Py_InitModule("_core", _CoreMethods);
}
//-
