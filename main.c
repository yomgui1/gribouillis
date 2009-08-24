#include <libraries/mui.h>
#include <clib/alib_protos.h>

#include <proto/exec.h>
#include <proto/intuition.h>

#undef USE_INLINE_STDARG
#include <proto/muimaster.h>
#define USE_INLINE_STDARG

#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <stdarg.h>
#include <ctype.h>

#ifndef MAKE_ID
#define MAKE_ID(a,b,c,d) ((ULONG) (a)<<24 | (ULONG) (b)<<16 | (ULONG) (c)<<8 | (ULONG) (d))
#endif

struct Library *MUIMasterBase = NULL;

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

int main(int argc, char **argv)
{
    Object *app, *win_main;
    BOOL run = TRUE;
    LONG sigs;
    
    app = ApplicationObject,
        MUIA_Application_Title      , "Gribouillis",
        MUIA_Application_Version    , "$VER: Gribouillis "VERSION_STR" (" __DATE__ ")",
        MUIA_Application_Copyright  , "©2009, Guillaume ROGUEZ",
        MUIA_Application_Author     , "Guillaume ROGUEZ",
        MUIA_Application_Description, "Simple Painting program for MorphOS",
        MUIA_Application_Base       , "Gribouillis",

        SubWindow, win_main = WindowObject,
            MUIA_Window_Title, "Show Tree",
            MUIA_Window_ID   , MAKE_ID('M','A','I','N'),
            WindowContents, VGroup,

                Child, TextObject,
                    TextFrame,
                    //MUIA_Background, MUII_TextBack,
                    MUIA_Text_Contents, "\33c",
                    End,

                End,
            End,
        End;

    if (!app)
        fail(app, "Failed to create Application.");

    DoMethod(win_main, MUIM_Notify,
             MUIA_Window_CloseRequest, TRUE, (ULONG)app, 2,
             MUIM_Application_ReturnID,
             MUIV_Application_ReturnID_Quit);

    set(win_main, MUIA_Window_Open, TRUE);

    while (run) {
        ULONG id = DoMethod(app, MUIM_Application_Input, (ULONG)&sigs);

        switch (id) {
            case MUIV_Application_ReturnID_Quit:
                run = FALSE;
                break;
        }
        if (run && sigs) Wait(sigs);
    }

    set(win_main, MUIA_Window_Open, FALSE);
    fail(app, NULL);
    return(0);
}
