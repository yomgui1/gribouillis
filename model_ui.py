###############################################################################
# Copyright (c) 2009 Guillaume Roguez
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
###############################################################################

from pymui import *

class DataWindow(Window):
    __rules_units = {
        'm'  : ('meter', 0.0254, 2, 5),
        'cm' : ('centimeter', 2.54, 2, 5),
        'mm' : ('millimeter', 25.4, 2, 5),
        'in' : ('inch', 1.0, 3, 3),
    }

    def __init__(self, title, controler):
        super(DataWindow, self).__init__(Title=title, ID='Data', RootObject=VGroup())

        # Defaults
        self.controler = controler
        self.__rules_units_keys = ['m', 'cm', 'mm', 'in']
        self.__res = (75, 75)

        # UI  
        gp = ColGroup(2)
        self.RootObject.AddChild(gp)
        
        o = Cycle(self.__rules_units_keys)
        o.Notify('Active', MUIV_EveryTime, self.OnRulesUnitChanged, MUIV_TriggerValue)
        o.Active = self.__rules_units_keys.index('cm')
        gp.AddChild(Label("Rules unit:"), o)
        
        for n, i in (('X', 0), ('Y', 1)):
            o = String(Accept="1234567890", Format='r', Integer=self.__res[i], MaxLen=10, Frame='String')
            o.Notify('Format', MUIV_EveryTime, self.OnResolutionChanged, i, MUIV_TriggerValue)
            gp.AddChild(Label(n+"-Resolution (dpi):"), o)

    def OnRulesUnitChanged(self, item):
        self.__rules_unit = self.__rules_units_keys[item]

    def OnResolutionChanged(self, n, value):
        self.__res[n] = value

    @property
    def rules_unit(self):
        "Unit to display inside side rules"
        return self.__rules_unit

    @property
    def resolutions(self):
        "2-Tuple containing X and Y surface resolutions in dot per inch (dpi)"
        return self.__res
 
