from pymui import Area

MYTAGBASE = ((1<<31) | 0x95fe0000)
MA_Curve_Points    = (MYTAGBASE+0x10)
MA_Curve_Count     = (MYTAGBASE+0x11)
MM_Curve_DeleteAll = (MYTAGBASE+0x12)
MM_Curve_MapValue  = (MYTAGBASE+0x13)

class Curve(Area):
    CLASSID = "Curve.mcc"
    ATTRIBUTES = {
        MA_Curve_Points: ('Points', 'p', '..g'),
        MA_Curve_Count:  ('Count',  'I', '..g'),
        }
