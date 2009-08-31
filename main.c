#include "common.h"
#include "surface_mcc.h"
#include "brush_mcc.h"
#include "curve_mcc.h"

#include <devices/usb.h>
#include <devices/usb_hid.h>

#include <proto/poseidon.h>

#define FATAL_PYTHON_ERROR "Fatal Python error."
#define WAC_HID_FEATURE_REPORT  0x03

struct ClassWacom
{
    struct Node            wh_Node;         /* Node linkage */
    struct PsdDevice   *   wh_Device;       /* Up linkage */

    APTR                   wh_Binding;
    struct Library *       wh_BindingClass;

    struct PsdConfig   *   wh_Config;       /* Up linkage */
    struct PsdInterface *  wh_Interface;    /* Up linkage */
    struct PsdPipe     *   wh_EP0Pipe;      /* Endpoint 0 pipe */
    struct PsdEndpoint *   wh_IntInEP;
    ULONG                  wh_IntInEP_Num;
    ULONG                  wh_IntInEP_MaxPktSize;
    ULONG                  wh_IntInEP_Interval;
    struct Task        *   wh_Task;         /* This Task */
    struct MsgPort     *   wh_TaskMsgPort;  /* Message Port of Subtask */
};

extern void init_muimodule(void);
extern void init_coremodule(void);
extern void init_surfacemodule(void);

void FreeWacom(struct ClassWacom *);

struct Library *PsdBase=NULL;
struct MUI_CustomClass *gSurfaceMCC=NULL;
struct MUI_CustomClass *gBrushMCC=NULL;
struct MUI_CustomClass *gCurveMCC=NULL;
ULONG __stack = 1024*128;
Object *gApp = NULL;
struct ClassWacom *gWacomHandle;
STRPTR gPrgName;

//+ exit_handler
void exit_handler(void)
{
    if (NULL != gApp) {
        dprintf("Bad end: force to remove Application object\n");
        MUI_DisposeObject(gApp);
        gApp = NULL;
    }

    if (NULL != gSurfaceMCC)
        SurfaceMCC_Term(gSurfaceMCC);

    if (NULL != gBrushMCC)
        BrushMCC_Term(gBrushMCC);

    if (NULL != gCurveMCC)
        CurveMCC_Term(gCurveMCC);

    if (NULL != gWacomHandle)
        FreeWacom(gWacomHandle);

    if (NULL != PsdBase)
        CloseLibrary(PsdBase);
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

    if (str || pyerr) {
        if (str)
            puts(str);
        exit(RETURN_ERROR);
    }

    exit(RETURN_OK);
}
//-
//+ FreeWacom
void FreeWacom(struct ClassWacom *wh)
{
    psdFreePipe(wh->wh_EP0Pipe);
    DeleteMsgPort(wh->wh_TaskMsgPort);
    psdFreeVec(wh);
}
//-
//+ InitWacom
struct ClassWacom * InitWacom(struct ClassWacom *wh)
{
    struct List *cfglist;
    struct List *iflist;
    struct List *altiflist;
    ULONG ifnum, altnum, is_in, tp;
    struct List *eplist;

    wh->wh_Task = FindTask(NULL);

    psdGetAttrs(PGA_DEVICE, wh->wh_Device,
                DA_ConfigList, (ULONG) &cfglist,
                TAG_END);

    if (NULL == cfglist->lh_Head->ln_Succ) {
        fprintf(stderr, "No configs?\n");
        return NULL;
    }

    wh->wh_Config = (struct PsdConfig *) cfglist->lh_Head;

    psdGetAttrs(PGA_CONFIG, wh->wh_Config,
                CA_InterfaceList, (ULONG) &iflist,
                TAG_END);

    if(NULL== iflist->lh_Head->ln_Succ) {
        fprintf(stderr, "No interfaces?\n");
        return NULL;
    }

    wh->wh_Interface = (struct PsdInterface *) iflist->lh_Head;
    psdGetAttrs(PGA_INTERFACE, wh->wh_Interface,
                IFA_InterfaceNum, (ULONG) &ifnum,
                IFA_AlternateNum, (ULONG) &altnum,
                IFA_AlternateIfList, (ULONG) &altiflist,
                IFA_EndpointList, (ULONG) &eplist,
                TAG_END);

    wh->wh_IntInEP = (struct PsdEndpoint *) eplist->lh_Head;
    if (NULL == wh->wh_IntInEP) {
        fprintf(stderr, "No endpoints?\n");
        return NULL;
    }

    psdGetAttrs(PGA_ENDPOINT, wh->wh_IntInEP,
                EA_IsIn, (ULONG) &is_in,
                EA_EndpointNum, (ULONG) &wh->wh_IntInEP_Num,
                EA_TransferType, (ULONG) &tp,
                EA_MaxPktSize, (ULONG) &wh->wh_IntInEP_MaxPktSize,
                EA_Interval, (ULONG) &wh->wh_IntInEP_Interval,
                TAG_END);

    /*Printf("Isin: %lu, EP #: %lu, TransfertType: %lu, MaxPktSize: %lu, Interval: %lu\n",
           is_in, wh->wh_IntInEP_Num, tp, wh->wh_IntInEP_MaxPktSize, wh->wh_IntInEP_Interval);*/

    psdGetAttrs(PGA_INTERFACE, wh->wh_Interface,
                IFA_Binding, (ULONG) &wh->wh_Binding,
                IFA_BindingClass, (ULONG) &wh->wh_BindingClass,
                TAG_END);
    if (NULL != wh->wh_Binding) {
        if (NULL != wh->wh_BindingClass) {
            //Printf("Binding found: @%p, base=%p\n", (ULONG) wh->wh_Binding, (ULONG) wh->wh_BindingClass);

            wh->wh_TaskMsgPort = CreateMsgPort();
            if (NULL != wh->wh_TaskMsgPort) {

                wh->wh_EP0Pipe = psdAllocPipe(wh->wh_Device, wh->wh_TaskMsgPort, NULL);
                if (NULL != wh->wh_EP0Pipe) {
                    return wh;
                } else
                     fprintf(stderr, "Couldn't allocate default pipe\n");
                DeleteMsgPort(wh->wh_TaskMsgPort);
            }
        } else
            fprintf(stderr, "Couldn't get binding library\n");
    } else
        fprintf(stderr, "Couldn't find any binding for this Wacom device!\n");

    return NULL;
}
//-
//+ FoundWacom
struct ClassWacom *FoundWacom(ULONG unit)
{
    struct ClassWacom *wh;
    struct PsdDevice *pd=NULL;
    ULONG pid=0, vid=0;
    STRPTR pname=NULL;
    ULONG bool=TRUE;
    APTR pif=NULL;

    psdLockReadPBase();
    do {
        pd = psdFindDevice(pd,
                           DA_VendorID, 0x056A,      /* Wacom */
                           TAG_END);

        if (NULL != pd) {
            pif = psdFindInterface(pd, pif,
                                   IFA_Class, HID_CLASSCODE,
                                   IFA_SubClass, HID_BOOT_SUBCLASS,
                                   IFA_Protocol, HID_PROTO_MOUSE,
                                   TAG_END);
        }
    } while ((NULL == pif) && (unit--));
    psdUnlockPBase();

    if (NULL == pif)
        return NULL;

    psdLockReadDevice(pd);
    if (psdGetAttrs(PGA_DEVICE, pd,
                    DA_HasDevDesc, (ULONG) &bool,
                    DA_VendorID, (ULONG) &vid,
                    DA_ProductID, (ULONG) &pid,
                    DA_ProductName, (ULONG) &pname,
                    TAG_END) != 4) {
        fprintf(stderr, "Couldn't get device description!\n");
        return NULL;
    }

    printf("Wacom HID (Mouse) device found: VID/DID = %04lX-%04lX, Name: '%s'\n",
           (ULONG) vid, (ULONG) pid, (ULONG) (pname?pname:(STRPTR) "<null>"));

    wh = psdAllocVec(sizeof(struct ClassWacom));
    if (NULL != wh) {
        wh->wh_Device = pd;
        if (NULL != InitWacom(wh)) {
            psdUnlockDevice(pd);
            return wh;
        } else
            fprintf(stderr, "Couldn't allocate Wacom...\n");
        psdUnlockDevice(pd);
        psdFreeVec(wh);
    }

    return NULL;
}
//-
//+ SetupWacom
void SetupWacom(struct ClassWacom *wh)
{
    char buf[10];
    ULONG ioerr, retry;

    retry = 0;
    for (;;) {
        buf[0] = 2; /* ReportID */
        buf[1] = 2; /* Tablet mode */

        psdPipeSetup(wh->wh_EP0Pipe, URTF_OUT|URTF_CLASS|URTF_INTERFACE,
                     UHR_SET_REPORT, (WAC_HID_FEATURE_REPORT << 8) + 2, 0);
        ioerr = psdDoPipe(wh->wh_EP0Pipe, &buf, 2);
        if (ioerr) {
            psdAddErrorMsg(RETURN_WARN, (STRPTR) gPrgName,
                           "UHR_SET_REPORT failed: %s (%ld)!",
                           (ULONG) psdNumToStr(NTS_IOERR, ioerr, "unknown"), ioerr);
            break;
        }  else {
            psdPipeSetup(wh->wh_EP0Pipe, URTF_IN|URTF_CLASS|URTF_INTERFACE,
                         UHR_GET_REPORT, (WAC_HID_FEATURE_REPORT << 8) + 2, 0);
            ioerr = psdDoPipe(wh->wh_EP0Pipe, &buf, 2);
            if (ioerr) {
                psdAddErrorMsg(RETURN_WARN, (STRPTR) gPrgName,
                               "UHR_GET_REPORT failed: %s (%ld)!",
                               (ULONG) psdNumToStr(NTS_IOERR, ioerr, "unknown"), ioerr);
                break;
            } else if (2 == buf[1])
                break;
            else {
                if (retry++ >= 5) {
                    fprintf(stderr, "Couldn't set the tablet feature mode!\n");
                    break;
                }
            }
        }
    }
}
//-
//+ main
int main(int argc, char **argv)
{
    PyObject *m;
    int res;

    atexit(exit_handler); 

    /*--- Python initialisation ---*/
    res = PyMorphOS_Init(&argc, &argv);
    if (res != RETURN_OK)
        return res;

    gPrgName = argv[0];
    Py_SetProgramName(gPrgName);
    Py_Initialize();
    PySys_SetArgv(argc, argv);

    /*--- Other init ---*/
    PsdBase = OpenLibrary("poseidon.library", 1);
    if (NULL == PsdBase)
        myexit("FAiled to open poseidon.library V1.0");
    
    gWacomHandle = FoundWacom(0);
    if (NULL != gWacomHandle)
        SetupWacom(gWacomHandle);

    /*--- MCCs creation ---*/
    gCurveMCC = CurveMCC_Init();
    if (NULL == gCurveMCC)
        myexit("Failed to create MCC 'Curve'");

    gBrushMCC = BrushMCC_Init();
    if (NULL == gBrushMCC)
        myexit("Failed to create MCC 'Brush'");

    gSurfaceMCC = SurfaceMCC_Init();
    if (NULL == gSurfaceMCC)
        myexit("Failed to create MCC 'Surface'");

    /*--- Run Python code ---*/
    m = PyImport_AddModule("__main__"); /* BR */
    if (NULL == m)
        myexit(FATAL_PYTHON_ERROR);

    init_muimodule();
    init_coremodule();
    init_surfacemodule();

    if (PyRun_SimpleString("from startup import start; start()"))
        myexit(FATAL_PYTHON_ERROR);

    myexit(NULL);
    return 0;
}
//-
