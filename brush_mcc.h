#ifndef BRUSH_MCC_H
#define BRUSH_MCC_H

#include <private/mui2intuition/mui.h>
#include <libraries/mui.h>


#if 0
#define BrushObject(f) \
    NewObject(gBrushMCC->mcc_Class, NULL,                       \
              ImageFrame,                                       \
              MUIA_Dtpic_Name, (f),                             \
              MUIA_Dtpic_Scale, BRUSH_SIZE,                     \
              TAG_DONE)
#else
#define BrushObject(f) \
    MUI_NewObject(MUIC_Dtpic,                                   \
                  ImageButtonFrame,                             \
                  MUIA_Dtpic_Name, (f),                         \
                  MUIA_Dtpic_Scale, BRUSH_SIZE,                 \
                  MUIA_InputMode, MUIV_InputMode_Toggle,        \
                  TAG_DONE)
#endif

extern struct MUI_CustomClass * BrushMCC_Init(void);
extern void BrushMCC_Term(struct MUI_CustomClass * mcc);

extern struct MUI_CustomClass *gBrushMCC;

#endif /* BRUSH_MCC_H */
