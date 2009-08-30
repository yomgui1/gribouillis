#include <Python.h>

#include "common.h"
#include "brush_mcc.h"

#define LAST_COLORS_NUM 4

#define FATAL_PYTHON_ERROR "Fatal Python error."

extern void init_muimodule(void);
extern void init_coremodule(void);

struct MUI_CustomClass *gBrushMCC=NULL;
ULONG __stack = 1024*128;
Object *gApp = NULL;

//+ exit_handler
void exit_handler(void)
{
    if (NULL != gApp) {
        dprintf("Bad end: force to remove Application object\n");
        MUI_DisposeObject(gApp);
        gApp = NULL;
    }
}
//-
//+ myexit
static void myexit(char *str)
{
    BOOL pyerr = FALSE;

    if (PyErr_Occurred()) {
        PyErr_Print();
        pyerr = TRUE;    
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

    atexit(exit_handler);

    /*--- MCCs creation ---*/
    gBrushMCC = BrushMCC_Init();
    if (NULL == gBrushMCC)
        myexit("Failed to create MCC 'Image'");

    /*--- Run Python code ---*/
    if (PyRun_SimpleString("from startup import start; start()"))
        myexit(FATAL_PYTHON_ERROR);

    myexit(NULL);
    return 0;
}
//-
