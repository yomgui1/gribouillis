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

class ModelInfoWindow(Window):
    __res_units = {
        'm'  : ('meter', 0.0254, 2, 5),
        'cm' : ('centimeter', 2.54, 2, 5),
        'mm' : ('millimeter', 25.4, 2, 5),
        'in' : ('inch', 1.0, 3, 3),
    }

    def __init__(self, title):
        ro = VGroup()
        super(DataWindow, self).__init__(title, ID='Data', RootObject=ro)

        # Defaults
        self.__res_units_keys = ['m', 'cm', 'mm', 'in']
        self._res = [(72, 'in'), (72, 'in')]

        # UI  
        gp = ColGroup(2)
        ro.AddChild(gp)

        self._ImageSize = Text()
        gp.AddChild(Label("Image area:"), self._ImageSize)
        
        self._MemoryUsed = Text()
        gp.AddChild(Label("Memory used:"), self._MemoryUsed)

        self._ResUnit = Cycle(self.__res_units_keys, CycleChain=True)
        self._ResUnit.Active = self.__res_units_keys.index('in')
        self._ResUnit.Notify('Active', MUIV_EveryTime, self.OnResUnitChanged, MUIV_TriggerValue)
        gp.AddChild(Label("Resolution unit:"), self._ResUnit)
        
        for i, n in enumerate("XY"):
            self._ResObj[i] = String(Accept="1234567890", Format='r', MaxLen=10, Frame='String', CycleChain=True)
            self._ResObj[i].Notify('Integer', MUIV_EveryTime, self.OnResolutionChanged, i, MUIV_TriggerValue)
            gp.AddChild(Label(n+"-Resolution:"), self._ResObj[i])

        self._Author = String(Frame='String', CycleChain=True)
        self._Author.Notify('Contents', MUIV_EveryTime, self.OnContentsChanged, self._Author, 'Author')
        gp.AddChild(Label("Author:"), self._Author)

        self._Comments = String(Frame='String', SetVMax=False, CycleChain=True)
        self._Comments.Notify('Contents', MUIV_EveryTime, self.OnContentsChanged, self._Comments, 'Comments')
        gp.AddChild(Label("Comments:"), self._Comments)

        o = SimpleButton("Refresh"); o.CycleChain = True
        o.Notify('Pressed', False, self.ShowModel, None)
        ro.AddChild(HBar(), o)

    def ShowModel(self, model):
        if model:
            self.model = model
        elif self.model:
            model = self.model
        else:
            raise RuntimeError("No model set yet")
            
        self.Close()
        info = model.info
        self._Author.Contents = info.get('Author')
        self._Comments.Contents = info.get('Comments')
        unit = info.get('ResolutionUnit', 'in')
        self._ResUnit.NNSet('Active', self.__res_units_keys.index(unit))
        for i, n in enumerate("XY"):
            res = info.get(n+'Resolution', 72)
            self._res[i] = (res, unit)
            self._ResObj[i].Integer = res
        self.Open()

    def OnContentsChanged(self, obj, attr):
        self.model.info[attr] = obj.Contents

    def OnResUnitChanged(self, active):
        # Change current resolution for this new unit
        new_unit = self.__res_units_keys[active]
        for i, (res, unit) in enumerate(self._res):
            self.ResObj[i].Integer = int(res/self.__res_units[unit][1]*self.__res_units[new_unit][1])
        self.model.info['ResolutionUnit'] = new_unit

    def OnResolutionChanged(self, n, value):
        self._res[n] = value, self.__res_units_keys[self._ResUnit.Active]
        if 0 == n:
            self.model.info['XResolution'] = value
        else:
            self.model.info['YResolution'] = value
        self.model.info['DPI'] = self.dpi

    @property
    def res_unit(self):
        "Unit of resolution"
        return self.__res_units_keys[self._ResUnit.Active]

    @property
    def resolutions(self):
        "2-Tuple containing X and Y surface resolutions (pixels per ResolutionUnit, see res_unit)"
        return int(self._ResObj[0].Contents), int(self._ResObj[1].Contents)

    @property
    def dpi(self):
        "2-Tuple containing X and Y surface resolutions in dot per inch (dpi)"
        res_x, res_y = self._ResObj
        def ConvertToDPI():
            for res in enumerate(self._ResObj):
                if res[1] == 'in':
                    yield res[0]
                else:
                    yield int(res[0] / self.__res_units[res[1]][1])

        return tuple(ConvertToDPI())

    @property
    def author(self):
        return self._Author.Contents

    @property
    def comments(self):
        return self._Comments.Contents
