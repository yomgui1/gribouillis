#include <private/mui2intuition/mui.h>
#include <libraries/mui.h>
#include <libraries/gadtools.h>
#include <utility/hooks.h>
#include <proto/exec.h>

#undef USE_INLINE_STDARG
#include <clib/alib_protos.h>  
#include <proto/muimaster.h>
#include <proto/intuition.h>      
#define USE_INLINE_STDARG

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

#define Image(f) MUI_NewObject(MUIC_Dtpic, MUIA_Dtpic_Name, f, TAG_DONE)
#define BrushObject(f) MUI_NewObject(MUIC_Dtpic, \
    MUIA_Dtpic_Name, f, \
    MUIA_Dtpic_LightenOnMouse, TRUE, \
    MUIA_Dtpic_Scale, BRUSH_SIZE, \
    MUIA_InputMode, MUIV_InputMode_RelVerify, TAG_DONE)

#define LAST_COLORS_NUM 4
#define BRUSH_SIZE 32

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

//+ brushes
STRPTR brushes[] = {
    "brushes/ab002_prev.png",
    "brushes/ab007_prev.png",
    "brushes/ab009_prev.png",
    "brushes/ab023_prev.png",
    "brushes/ab026_prev.png",
    "brushes/ab028_prev.png",
    "brushes/ab033_prev.png",
    "brushes/ab043_prev.png",
    "brushes/aspec_fun_5_prev.png",
    "brushes/aspect_fun_1_prev.png",
    "brushes/aspect_fun_3_prev.png",
    "brushes/basic_prev.png",
    "brushes/bi000_prev.png",
    "brushes/bi001_prev.png",
    "brushes/bi003_prev.png",
    "brushes/bi004_prev.png",
    "brushes/bi006_prev.png",
    "brushes/bi010_prev.png",
    "brushes/bigcharcoal_prev.png",
    "brushes/blend+paint_prev.png",
    "brushes/blur_prev.png",
    "brushes/bulk_prev.png",
    "brushes/charcoal_prev.png",
    "brushes/coarse_bulk_1_prev.png",
    "brushes/coarse_bulk_2_prev.png",
    "brushes/coarse_bulk_3_prev.png",
    "brushes/coarse_bulk_4_prev.png",
    "brushes/dry_brush_prev.png",
    "brushes/glow_prev.png",
    "brushes/hair_prev.png",
    "brushes/hard_sting_prev.png",
    "brushes/hue_fun_prev.png",
    "brushes/ink_eraser_prev.png",
    "brushes/ink_prev.png",
    "brushes/leaves_prev.png",
    "brushes/long_grass_prev.png",
    "brushes/loosedots_prev.png",
    "brushes/marker-01_prev.png",
    "brushes/marker-02_prev.png",
    "brushes/marker-03_prev.png",
    "brushes/marker-04_prev.png",
    "brushes/marker-05_prev.png",
    "brushes/marker-06_prev.png",
    "brushes/modelling_prev.png",
    "brushes/o001_prev.png",
    "brushes/o009_prev.png",
    "brushes/o014_prev.png",
    "brushes/o017_prev.png",
    "brushes/o022_prev.png",
    "brushes/o028_prev.png",
    "brushes/o032_prev.png",
    "brushes/o300_prev.png",
    "brushes/o388_prev.png",
    "brushes/o397_prev.png",
    "brushes/o398_prev.png",
    "brushes/o512_prev.png",
    "brushes/o558_prev.png",
    "brushes/o594_prev.png",
    "brushes/o826_prev.png",
    "brushes/o834_prev.png",
    "brushes/o888_prev.png",
    "brushes/o945_prev.png",
    "brushes/old_b008_prev.png",
    "brushes/painting_knife_prev.png",
    "brushes/pencil-2b_prev.png",
    "brushes/pencil-6b_prev.png",
    "brushes/pencil-8b_prev.png",
    "brushes/pencil-blur_prev.png",
    "brushes/pencil-h_prev.png",
    "brushes/pencil-hb_prev.png",
    "brushes/pencil-rubber_prev.png",
    "brushes/pencil_prev.png",
    "brushes/pick_and_drag_prev.png",
    "brushes/pointy_ink_prev.png",
    "brushes/redbrush_prev.png",
    "brushes/s000_prev.png",
    "brushes/s002_prev.png",
    "brushes/s003_prev.png",
    "brushes/s004_prev.png",
    "brushes/s006_prev.png",
    "brushes/s007_prev.png",
    "brushes/s008_prev.png",
    "brushes/s009_prev.png",
    "brushes/s011_prev.png",
    "brushes/s014_prev.png",
    "brushes/s015_prev.png",
    "brushes/s018_prev.png",
    "brushes/s020_prev.png",
    "brushes/s021_prev.png",
    "brushes/s023_prev.png",
    "brushes/s109_prev.png",
    "brushes/short_grass_prev.png",
    "brushes/slow_prev.png",
    "brushes/smudge_prev.png",
    "brushes/soft_sting_prev.png",
    "brushes/soft_water_prev.png",
    "brushes/solid_water_prev.png",
    "brushes/splatter-01_prev.png",
    "brushes/splatter-02_prev.png",
    "brushes/splatter-03_prev.png",
    "brushes/splatter-04_prev.png",
    "brushes/splatter-05_prev.png",
    "brushes/splatter-06_prev.png",
    "brushes/subtle_pencil_prev.png",
    "brushes/textured_ink_prev.png",
    NULL
};
//-

Object *gWinColor, *gWinBrushSelect;
struct Hook hook_ColorChanged;
ULONG gLastColors[3*LAST_COLORS_NUM] = {0};
ULONG gLastColorId=0;

//+ fail
static VOID fail(APTR app,char *str)
{
    if (app)
        MUI_DisposeObject(app);

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
        STRPTR *name;

        /* Close window when requested */
        DoMethod(win, MUIM_Notify, MUIA_Window_CloseRequest, TRUE,
                 MUIV_Notify_Self, 3, MUIM_Set, MUIA_Window_Open, FALSE);

        DoMethod(vg, MUIM_Group_InitChange, TRUE);
        for (name=brushes; NULL != *name; name++) {
            Object *o = BrushObject(*name);

            if (NULL != o)
                DoMethod(vg, OM_ADDMEMBER, o);
        }
        DoMethod(vg, MUIM_Group_InitChange, FALSE);
    }

    return win;
}
//-
//+ main
int main(int argc, char **argv)
{
    Object *app, *win_main, *strip;
    BOOL run = TRUE;
    LONG sigs;
    
    INIT_HOOK(&hook_ColorChanged, OnColorChanged);

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
            MUIA_Window_ID   , MAKE_ID('D','R','A','W'),
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

    DoMethod(win_main, MUIM_Notify, MUIA_Window_CloseRequest, TRUE,
             app, 2, MUIM_Application_ReturnID, MUIV_Application_ReturnID_Quit);

    /* 'c' pressed => Open Color window */
    DoMethod(win_main, MUIM_Notify, MUIA_Window_InputEvent, "c",
             gWinColor, 3, MUIM_Set, MUIA_Window_Open, TRUE);

    /* 'b' pressed => Open Brush Selection window */
    DoMethod(win_main, MUIM_Notify, MUIA_Window_InputEvent, "b",
             gWinBrushSelect, 3, MUIM_Set, MUIA_Window_Open, TRUE);

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
    return(0);
}
//-
