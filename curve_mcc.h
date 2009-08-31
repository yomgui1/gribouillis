#ifndef CURVE_MCC_H
#define CURVE_MCC_H

#include "common.h"

#define CurveObject NewObject(gCurveMCC->mcc_Class, NULL

#define MA_Curve_Points    (MYTAGBASE+0x10)
#define MA_Curve_Count     (MYTAGBASE+0x11)
#define MM_Curve_DeleteAll (MYTAGBASE+0x12)
#define MM_Curve_MapValue  (MYTAGBASE+0x13)

struct MP_Curve_MapValue { ULONG MethodID; FLOAT *Value; };

extern struct MUI_CustomClass * CurveMCC_Init(void);
extern void CurveMCC_Term(struct MUI_CustomClass * mcc);

extern struct MUI_CustomClass *gCurveMCC;

#endif /* CURVE_MCC_H */
