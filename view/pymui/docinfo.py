###############################################################################
# Copyright (c) 2009-2011 Guillaume Roguez
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

import pymui

import view
from utils import _T
from .widgets import Ruler

__all__ = [ 'DocInfoWindow' ]

class DocInfoWindow(pymui.Window):
    __docproxy = None
    
    def __init__(self, name):
        super(DocInfoWindow, self).__init__(name, ID='INFO',
                                            CloseOnReq=True)
        self.name = name
        
        top = pymui.VGroup()
        self.RootObject = top
        
        # Document name
        name = pymui.Text(Frame='Text')
        top.AddChild(name)
        
        # Dimensions
        dim_grp = pymui.VGroup(GroupTitle=_T("Dimensions"))
        use_full_bt = pymui.SimpleButton(_T("No limits"), CycleChain=True)
        use_cur_bt = pymui.SimpleButton(_T("Set to current size"), CycleChain=True)
        ori_x = pymui.String(Frame='String', Accept="-0123456789", CycleChain=True)
        ori_y = pymui.String(Frame='String', Accept="-0123456789", CycleChain=True)
        size_x = pymui.String(Frame='String', Accept="-0123456789", CycleChain=True)
        size_y = pymui.String(Frame='String', Accept="-0123456789", CycleChain=True)
        
        box = pymui.ColGroup(2)
        box.AddChild(pymui.Label(_T("X Origin")+':'))
        box.AddChild(ori_x)
        box.AddChild(pymui.Label(_T("Y Origin")+':'))
        box.AddChild(ori_y)
        box.AddChild(pymui.Label(_T("Width")+':'))
        box.AddChild(size_x)
        box.AddChild(pymui.Label(_T("Height")+':'))
        box.AddChild(size_y)
        
        ori_x.Notify('Acknowledge', self._modify_dim, 0)
        ori_y.Notify('Acknowledge', self._modify_dim, 1)
        size_x.Notify('Acknowledge', self._modify_dim, 2)
        size_y.Notify('Acknowledge', self._modify_dim, 3)
        
        pp = pymui.Text(_T("Passe-Partout"),
                        InputMode='Toggle',
                        Frame='Button',
                        Background='ButtonBack',
                        PreParse=pymui.MUIX_C,
                        Selected=False)
        pp.Notify('Selected', self._toggle_pp)
        dim_grp.AddChild(pp)
        
        dim_grp.AddChild(pymui.HGroup(Child=(use_full_bt, use_cur_bt)))
        dim_grp.AddChild(box)
        top.AddChild(dim_grp)
        
        def callback(evt):
            self.__docproxy.set_metadata(dimensions=None)
        
        use_full_bt.Notify('Pressed', callback, when=False)
        
        def callback(evt):
            _, _, w, h = area = self.__docproxy.document.area
            if not (w and h):
                area = None
            self.__docproxy.set_metadata(dimensions=area)
            
        use_cur_bt.Notify('Pressed', callback, when=False)
        
        # Density
        dpi_grp = pymui.VGroup(GroupTitle=_T("Density"))
        use_calib_bt = pymui.SimpleButton(_T("Set from calibration"), CycleChain=True)
        dpi_x = pymui.String(Frame='String', Accept="0123456789.", CycleChain=True)
        dpi_y = pymui.String(Frame='String', Accept="0123456789.", CycleChain=True)
        
        box = pymui.ColGroup(2)
        box.AddChild(pymui.Label(_T("X")+':'))
        box.AddChild(dpi_x)
        box.AddChild(pymui.Label(_T("Y")+':'))
        box.AddChild(dpi_y)
        
        dpi_grp.AddChild(use_calib_bt)
        dpi_grp.AddChild(box)
        top.AddChild(dpi_grp)
        
        def callback(evt):
            dpi_x = Ruler.METRICS['in'][2]
            dpi_y = Ruler.METRICS['in'][3]
            self.__docproxy.set_metadata(densities=[dpi_x, dpi_y])
            
        use_calib_bt.Notify('Pressed', callback, when=False)
        
        self.widgets = {
            'name': name,
            'dpi-x': dpi_x,
            'dpi-y': dpi_y,
            'dim-x': size_x,
            'dim-y': size_y,
            'ori-x': ori_x,
            'ori-y': ori_y,
            }
            
    def _toggle_pp(self, evt):
        vpmd = pymui.GetApp().mediator.viewport_mediator
        vpmd.enable_passepartout(vpmd.active, evt.value.value)
        
    def _modify_dim(self, evt, idx):
        n = int(evt.value.contents)
        area = self.__docproxy.document.metadata['dimensions']
        if area:
            vpmd = pymui.GetApp().mediator.viewport_mediator
            vpmd.enable_passepartout(vpmd.active, True)
            area = list(area)
        else:
            area = [0]*4
        area[idx] = n
        self.__docproxy.set_metadata(dimensions=area)
        
    def __set_docproxy(self, dp):
        self.__docproxy = dp
        self.widgets['name'].Contents = dp.docname
        x,y,w,h = map(str, dp.document.metadata['dimensions'] or [0]*4)
        self.widgets['ori-x'].Contents = x
        self.widgets['ori-y'].Contents = y
        self.widgets['dim-x'].Contents = w
        self.widgets['dim-y'].Contents = h
        dx, dy = dp.document.metadata['densities']
        self.widgets['dpi-x'].Contents = str(dx)
        self.widgets['dpi-y'].Contents = str(dy)
        
    def __del_docproxy(self):
        self.Open = False
        self.__docproxy = None
        
    docproxy = property(fget=lambda self: self.__docproxy, fset=__set_docproxy, fdel=__del_docproxy)