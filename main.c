#include <Python.h>

#include "brush_mcc.h"

#include <private/mui2intuition/mui.h>
#include <libraries/mui.h>

#undef USE_INLINE_STDARG
#include <proto/muimaster.h>
#include <proto/intuition.h>
#define USE_INLINE_STDARG

#define LAST_COLORS_NUM 4

#define FATAL_PYTHON_ERROR "Fatal Python error."

extern struct Library *PythonBase;

extern void init_muimodule(void);
extern void init_coremodule(void);

struct MUI_CustomClass *gBrushMCC=NULL;
ULONG __stack = 1024*128;

//+ myexit
static void myexit(char *str)
{
    BOOL pyerr = FALSE;

    if (PyErr_Occurred()) {
        pyerr = TRUE;
        PyErr_Print();
    }

    Py_Finalize();

    if (NULL != gBrushMCC)
        BrushMCC_Term(gBrushMCC);

    if (str || pyerr) {
        if (str)
            puts(str);
        exit(RETURN_ERROR);
    }

    exit(RETURN_OK);
}
//-
//+ main
int main(int argc, char **argv)
{
    PyObject *m;
    int res;

    /*--- Python initialisation ---*/
    res = PyMorphOS_Init(&argc, &argv);
    if (res != RETURN_OK)
        return res;

    Py_SetProgramName(argv[0]);
    Py_Initialize();
    PySys_SetArgv(argc, argv);

    m = PyImport_AddModule("__main__"); /* BR */
    if (NULL == m)
        myexit(FATAL_PYTHON_ERROR);

    init_muimodule();
    init_coremodule();

    /*--- MCCs creation ---*/
    gBrushMCC = BrushMCC_Init();
    if (NULL == gBrushMCC)
        myexit("Failed to create MCC 'Image'");

    /*--- Run Python code ---*/
    if (PyRun_SimpleString("from startup import start; start()"))
        myexit(FATAL_PYTHON_ERROR);

    return 0;
}
//-
