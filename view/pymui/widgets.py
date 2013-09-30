###############################################################################
# Copyright (c) 2009-2013 Guillaume Roguez
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
from math import ceil, floor

import main
from utils import _T
from model import prefs

prefs.add_default('pymui-ruler-bg-pen', 0)
prefs.add_default('pymui-ruler-fg-pen', 1)
prefs.add_default('pymui-ruler-pos-pen', 3)


class Ruler(pymui.Rectangle):
    _MCC_ = True
    
    SIZE = 20
    METRICS = {
        'px': [ _T('Pixels'), 'px', 1.0, 1.0, (1, 2, 5, 10, 25, 50, 100, 250, 500, 1000), (1,5,10,50,100) ],
        'cm': [ _T('Centimeters'), 'cm', 28.35, 28.35,  (1, 2, 5, 10, 25, 50, 100, 250, 500, 1000), (1,5,10,50,100) ],
        'in': [ _T('Inches'), 'in', 72.0, 72, (1, 2, 4, 8, 16, 32, 64, 128, 256, 512), (1,2,4,8,16) ],
    }
    METRIC_KEYS = [ 'px', 'cm', 'in' ]
    _pos = None
        
    def __init__(self, Horiz=True, **kwds):
        if Horiz:
            kwds['VertWeight'] = 0
        else:
            kwds['HorizWeight'] = 0
            
        kwds.update(Font=pymui.MUIV_Font_Tiny, FillArea=False)
        super(Ruler, self).__init__(**kwds)
        
        self._horiz = bool(Horiz)
        self.lo = 0.0
        self.hi = 0.0
        self.max_size = 1e6
        self.set_metric('px')
    
    @pymui.muimethod(pymui.MUIM_AskMinMax)
    def _mcc_AskMinMax(self, msg):
        msg.DoSuper()
        mmi = msg.MinMaxInfo.contents
        if self._horiz:
            mmi.MaxWidth = mmi.MaxWidth.value + pymui.MUI_MAXMAX
            mmi.MaxHeight = mmi.MaxHeight.value + Ruler.SIZE
            mmi.MinHeight = mmi.MinHeight.value + Ruler.SIZE
        else:
            mmi.MaxWidth = mmi.MaxWidth.value + Ruler.SIZE
            mmi.MinWidth = mmi.MinWidth.value + Ruler.SIZE
            mmi.MaxHeight = mmi.MaxHeight.value + pymui.MUI_MAXMAX
            
    @pymui.muimethod(pymui.MUIM_Draw)
    def _mcc_Draw(self, msg):
        msg.DoSuper()
        if not (msg.flags.value & pymui.MADF_DRAWOBJECT): return

        rp = self._rp
        bg = prefs['pymui-ruler-bg-pen']
        fg = prefs['pymui-ruler-fg-pen']
        rp.APen = fg
        a,b,c,d = self.MBox
        rp.Rect(bg, a, b, c, d, 1)
        rp.Rect(fg, a, b, c, d)
        del fg, bg, a, b, c, d
        
        if self._horiz:
            size = self.MWidth
            bar_size = self.MHeight
        else:
            size = self.MHeight
            bar_size = self.MWidth
            
        digit_height = self.FontYSize
        tick_len = self.SIZE * .35
        pxpu = Ruler.METRICS[self._metric][2 if self._horiz else 3]

        # Lo/Hi ruler bounds in pixels
        lo = self.lo / pxpu
        hi = self.hi / pxpu
        
        dist = hi - lo
        if not dist:
            return
            
        scale = ceil(self.max_size / pxpu)
        text_scale = '%d' % scale
        
        # inc = number of pixels to obtain one unit
        inc = abs(float(size) / dist)
        del dist
        
        text_width = len(text_scale) * digit_height + 1;

        n = 2 * text_width / abs(inc)
        for scale in self._scales:
            if scale > n:
                break
        scale = float(scale)
        
        def get_data(lo, hi, dim):
            data = []
            for i, subdiv in enumerate(self._subdiv):
                if dim / subdiv <= 5:
                    break
                    
                subinc = scale / subdiv
                data.append((bar_size / (i+1), subinc, floor(lo / subinc) * subinc, ceil(hi / subinc) * subinc))
                
            return data
        
        if lo < hi:
            data = get_data(lo, hi, scale*abs(inc))
        else:
            data = get_data(lo, hi, scale*abs(inc))
            
        metric = Ruler.METRICS[self._metric][1]
        
        self.AddClipping()
        try:
            if self._horiz:
                left = self.MLeft
                bot = self.MBottom
                top = self.MTop

                # Loop on drawable divisions
                text = rp.Text
                for bar_size, subinc, cur, end in data:
                    while cur <= end:
                        pos = left + int((cur - lo) * inc + .5)
                        
                        rp.Move(pos, bot - bar_size)
                        rp.Draw(pos, bot)
                        
                        if text:
                            text(pos+2, top + digit_height - 2, '%d' % cur + metric)
                            
                        cur += subinc
                        
                    text = None
                    
                # Cursor position bar
                if self._pos is not None:
                    rp.APen = prefs['pymui-ruler-pos-pen']
                    x = self._pos
                    rp.Move(x, top)
                    rp.Draw(x, bot)
                        
            else:
                top = self.MTop
                left = self.MLeft
                right = self.MRight
                
                # Loop on drawable divisions
                text = rp.Text
                for bar_size, subinc, cur, end in data:
                    while cur <= end:
                        pos = top + int((cur - lo) * inc + .5)
                            
                        rp.Move(right - bar_size, pos)
                        rp.Draw(right, pos)
                        
                        if text:
                            for i, c in enumerate('%d' % cur):
                                text(left+3, pos + (i+1) * digit_height - 2, c)
                            text(left+3, pos + (i+2) * digit_height - 2, metric)
                            
                        cur += subinc
                        
                    text = None
                    
                # Cursor position bar
                if self._pos is not None:
                    rp.APen = prefs['pymui-ruler-pos-pen']
                    y = self._pos
                    rp.Move(left, y)
                    rp.Draw(right, y)
                        
        finally:
            self.RemoveClipping()
        
    def set_metric(self, name):
        self._metric = name
        self._scales, self._subdiv = Ruler.METRICS[self._metric][-2:]
        self.Redraw()

    def set_pos(self, pos):
        #self._pos = pos
        #self.Redraw()
        self._pos = None # Disabled - TODO