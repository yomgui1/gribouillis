#ifndef SURFACE_MCC_H
#define SURFACE_MCC_H

#include "common.h"

#define SurfaceObject NewObject(gSurfaceMCC->mcc_Class, NULL

extern struct MUI_CustomClass * SurfaceMCC_Init(void);
extern void SurfaceMCC_Term(struct MUI_CustomClass * mcc);

extern struct MUI_CustomClass *gSurfaceMCC;

#endif /* SURFACE_MCC_H */
