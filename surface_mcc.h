#ifndef SURFACE_MCC_H
#define SURFACE_MCC_H

#include "common.h"

#define SurfaceObject NewObject(gSurfaceMCC->mcc_Class, NULL

#define MA_Surface_MotionEvent (MYTAGBASE+1)
#define MA_Surface_LeftButtonPressed (MYTAGBASE+2)
#define MM_Surface_Draw (MYTAGBASE+3)

#define PRESSURE_MAX 0x7ffff800

struct SurfaceST_MotionEvent
{
    LONG X, Y, Z;
    LONG RangeX, RangeY, RangeZ;
    LONG AngleX, AngleY, AngleZ;
    LONG Pressure;
    BOOL InProximity;
    BOOL IsTablet;
};

struct MP_DrawEllipse
{
    ULONG MethodId;
    LONG x, y, pressure;
};

extern struct MUI_CustomClass * SurfaceMCC_Init(void);
extern void SurfaceMCC_Term(struct MUI_CustomClass * mcc);

extern struct MUI_CustomClass *gSurfaceMCC;

#endif /* SURFACE_MCC_H */
