#ifndef BRUSH_MCC_H
#define BRUSH_MCC_H

#include <private/mui2intuition/mui.h>
#include <libraries/mui.h>

#define BrushObject(f) NewObject(gBrushMCC->mcc_Class, NULL, \
    MUIA_Dtpic_Name, (f), \
    MUIA_Dtpic_Scale, BRUSH_SIZE, \
    TAG_DONE)

extern struct MUI_CustomClass * BrushMCC_Init(void);
extern void BrushMCC_Term(struct MUI_CustomClass * mcc);

#endif /* BRUSH_MCC_H */
