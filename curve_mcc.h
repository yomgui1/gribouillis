#ifndef CURVE_MCC_H
#define CURVE_MCC_H

#include "common.h"

#define CurveObject NewObject(gCurveMCC->mcc_Class, NULL

#define MM_Curve_Convert (MYTAGBASE+0x10)

extern struct MUI_CustomClass * CurveMCC_Init(void);
extern void CurveMCC_Term(struct MUI_CustomClass * mcc);

extern struct MUI_CustomClass *gCurveMCC;

#endif /* CURVE_MCC_H */
