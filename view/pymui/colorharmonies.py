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

# Python 2.5 compatibility
from __future__ import with_statement

import pymui, cairo, os
from math import *
from colorsys import hsv_to_rgb, rgb_to_hsv

import model, view, main, utils

from utils import mvcHandler, _T

__all__ = [ 'ColorHarmoniesWindow', 'ColorHarmoniesWindowMediator' ]

pi2 = pi*2
IECODE_LBUTTON = 0x68

def get_angle(x,y):
    if x == 0:
        if y == 0: return None
        return pi/2 if y > 0 else -pi/2
    a = atan(float(y)/x)
    if x < 0: return a+pi
    if y < 0: return pi2+a
    return a

def get_pos(r, angle):
    x = r*cos(angle)
    y = r*sin(angle)
    return x,y


class ColorWeelHarmonies(pymui.Area):
    _MCC_ = True

    EVENTMAP = {
        pymui.IDCMP_MOUSEBUTTONS : 'mouse-button',
        pymui.IDCMP_MOUSEMOVE    : 'mouse-motion',
        pymui.IDCMP_RAWKEY       : 'rawkey',
        }

    circle_img_raw = None
    circle_img = None
    __hsv = [0., 0., 0.]
    __pos = (0., 0.)
    __vmin = 0.0

    WHEEL_RADIUS = 64.0

    HARMONIES_RADIUS = 20
    HARMONIES_PADDING = 10

    WHEEL_PADDING = HARMONIES_RADIUS + HARMONIES_PADDING + 5

    HARMONIES_RADIUS_IN = WHEEL_RADIUS + HARMONIES_PADDING
    HARMONIES_RADIUS_OUT = HARMONIES_RADIUS_IN + HARMONIES_RADIUS

    def __init__(self):
        super(ColorWeelHarmonies, self).__init__(InnerSpacing=(0,)*4,
                                                 Frame='None',
                                                 DoubleBuffer=True)

        self._ev = pymui.EventHandler()
        self._watchers = {}

    def add_watcher(self, name, cb, *args):
        wl = self._watchers.get(name)
        if wl is None:
            self._watchers[name] = wl = []
        wl.append((cb, args))

    def enable_mouse_motion(self, state=True):
        self._ev.uninstall()
        if state:
            idcmp = self._ev.idcmp | pymui.IDCMP_MOUSEMOVE
        else:
            idcmp = self._ev.idcmp & ~pymui.IDCMP_MOUSEMOVE
        self._ev.install(self, idcmp)

    @pymui.muimethod(pymui.MUIM_Setup)
    def MCC_Setup(self, msg):
        self._ev.install(self, pymui.IDCMP_RAWKEY | pymui.IDCMP_MOUSEBUTTONS)
        return msg.DoSuper()

    @pymui.muimethod(pymui.MUIM_Cleanup)
    def MCC_Cleanup(self, msg):
        self._ev.uninstall()
        return msg.DoSuper()

    @pymui.muimethod(pymui.MUIM_HandleEvent)
    def MCC_HandleEvent(self, msg):
        self._ev.readmsg(msg)
        wl = self._watchers.get(ColorWeelHarmonies.EVENTMAP.get(self._ev.Class), [])
        for cb, args in wl:
            return cb(self._ev, *args)

    @pymui.muimethod(pymui.MUIM_AskMinMax)
    def _mcc_AskMinMax(self, msg):
        msg.DoSuper()

        minmax = msg.MinMaxInfo.contents

        w = int((self.WHEEL_RADIUS + self.WHEEL_PADDING)*2)
        minmax.MinWidth = minmax.MinWidth.value + w
        minmax.MinHeight = minmax.MinHeight.value + w
        minmax.MaxWidth = minmax.MinWidth
        minmax.MaxHeight = minmax.MinHeight

    @pymui.muimethod(pymui.MUIM_Draw)
    def _mcc_Draw(self, msg):
        msg.DoSuper()

        if msg.flags.value & pymui.MADF_DRAWOBJECT:
            cr = self.cairo_context
            self.FillCairoContext()

            cr.save()
            self.repaint(cr)
            cr.restore()

    def mouse_to_user(self, x, y):
        x -= self.MLeft+self.WHEEL_PADDING+self.WHEEL_RADIUS
        y -= self.MTop+self.WHEEL_PADDING+self.WHEEL_RADIUS
        return x,y

    def hit_circle(self, x, y):
        return hypot(x, y) <= self.WHEEL_RADIUS

    def hit_harmony(self, x, y):
        r = hypot(x, y)
        if r >= self.HARMONIES_RADIUS_IN and r <= self.HARMONIES_RADIUS_OUT:
            # note: x and y can't be both 0 here
            self.Redraw()
            h = (get_angle(x, -y)/pi2) % 1.0
            h = (h-self.__hsv[0]) % 1.0
            h = ceil(floor(int(h*48)/2.)/2)/12.
            
            return (self.__hsv[0] + h) % 1.0, self.__hsv[1], self.__hsv[2]

    def repaint(self, cr):
        img = self.draw_circle(self.WHEEL_RADIUS)
        cr.set_source_surface(img, 0, 0)
        cr.paint()

        t = img.get_width() / 2.
        cr.translate(t,t)

        x,y = self.__pos
        h,s,v = self.__hsv

        cr.move_to(0,0)
        cr.line_to(*get_pos(self.HARMONIES_RADIUS_IN, -h*pi2))
        cr.set_source_rgba(0,0,0,1)
        cr.set_line_width(1.5)
        cr.stroke()

        # Draw current color position as 2 circles
        cr.set_line_width(1.5)

        cr.arc(x,y,3,0,pi2)
        vi = 1.-v
        cr.set_source_rgb(vi,vi,vi)
        cr.stroke()
        
        cr.arc(x,y,2.5,0,pi2)
        cr.set_source_rgb(0,0,0)
        cr.stroke()

        del t,x,y

        # Draw harmonies
        da = (get_angle(*self.__pos) or 0.)-pi/12.
        for i in xrange(12):
            cr.set_line_width(1 if i else 3)
            a1 = i*pi/6.+radians(3)+da
            a2 = (i+1)*pi/6.-radians(3)+da
            cr.arc(0,0,self.HARMONIES_RADIUS_IN,a1,a2)
            cr.arc_negative(0,0,self.HARMONIES_RADIUS_OUT,a2,a1)
            cr.close_path()
            cr.set_source_rgb(*hsv_to_rgb((h-i/12.) % 1.0 ,s,v))
            cr.fill_preserve()
            cr.set_source_rgb(vi,vi,vi)
            cr.stroke()

    def draw_circle_raw(self, r):
        if self.circle_img_raw:
            return self.circle_img_raw
        r2 = r + self.WHEEL_PADDING
        w = int(2*r2)
        img = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, w)
        cr = cairo.Context(img)
        cr.translate(r2,r2)
        cr.set_line_width(r*0.02)
        a = 0.0
        da = 0.5*atan(1./r)
        while a < pi2:
            c = hsv_to_rgb(a/pi2, 1., 1.)
            cr.set_source_rgb(*c)
            cr.move_to(*get_pos(1., -a))
            cr.line_to(*get_pos(r, -a))
            cr.stroke()
            a += da
        self.circle_img_raw = img
        return img

    def draw_circle(self, r):
        if self.circle_img:
            return self.circle_img

        circle_img = self.draw_circle_raw(r)
        w = circle_img.get_width()

        img = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, w)
        cr = cairo.Context(img)
        cr.set_source_surface(circle_img, 0, 0)
        cr.paint()
        w /= 2.
        cr.translate(w, w)

        v = self.__vmin
        pat = cairo.RadialGradient(0,0,0,0,0,r)
        pat.add_color_stop_rgb(0,v,v,v)
        pat.add_color_stop_rgba(1,0,0,0,0)

        cr.arc(0,0,self.WHEEL_RADIUS+1,0,pi2)
        cr.clip()

        cr.set_source(pat)
        cr.paint()

        self.circle_img = img
        return img

    def set_pos(self, x, y):
        self.__pos = x,y
        s = min(self.WHEEL_RADIUS, sqrt(x*x+y*y))/self.WHEEL_RADIUS
        v = self.__vmin*(1-s) + s
        h = get_angle(x,-y)
        if h is None:
            h = 0
        else:
            h = (h / pi2) % 1.0
        self.hsv = h,s,v
        return h,s,v

    def get_hsv(self):
        return tuple(self.__hsv)

    def set_hsv(self, hsv):
        hsv = list(hsv)
        if self.__hsv != hsv:
            self.__hsv = hsv
            self.circle_img = None
            self.__pos = get_pos(hsv[1]*self.WHEEL_RADIUS, -hsv[0]*pi2)
            self.Redraw()

    def get_vmin(self):
        return self.__vmin
        
    def set_vmin(self, v):
        self.__vmin = v
        self.set_pos(*self.__pos)
        
    hsv = property(fget=get_hsv, fset=set_hsv)
    vmin = property(fget=get_vmin, fset=set_vmin)

class ColorWeelHarmonies2(pymui.Area):
    _MCC_ = True

    EVENTMAP = {
        pymui.IDCMP_MOUSEBUTTONS : 'mouse-button',
        pymui.IDCMP_MOUSEMOVE    : 'mouse-motion',
        pymui.IDCMP_RAWKEY       : 'rawkey',
        }

    _hue_ring = None
    circle_img = None
    __hsv = [0., 0., 0.]
    __pos = (0., 0.)
    __rect = None

    WHEEL_RADIUS = 128.0

    HARMONIES_RADIUS = 20
    HARMONIES_PADDING = 10
    
    WHEEL_HUE_RING_RADIUS = 64
    WHEEL_HUE_RING_WIDTH = 16
    WHEEL_HUE_RING_RADIUS_OUT = WHEEL_HUE_RING_RADIUS+WHEEL_HUE_RING_WIDTH

    WHEEL_PADDING = HARMONIES_RADIUS + HARMONIES_PADDING + 5

    HARMONIES_RADIUS_IN = WHEEL_RADIUS + HARMONIES_PADDING
    HARMONIES_RADIUS_OUT = HARMONIES_RADIUS_IN + HARMONIES_RADIUS

    def __init__(self):
        super(ColorWeelHarmonies2, self).__init__(InnerSpacing=(0,)*4,
                                                 Frame='None',
                                                 DoubleBuffer=True)

        self._ev = pymui.EventHandler()
        self._watchers = {}

    def add_watcher(self, name, cb, *args):
        wl = self._watchers.get(name)
        if wl is None:
            self._watchers[name] = wl = []
        wl.append((cb, args))

    def enable_mouse_motion(self, state=True):
        self._ev.uninstall()
        if state:
            idcmp = self._ev.idcmp | pymui.IDCMP_MOUSEMOVE
        else:
            idcmp = self._ev.idcmp & ~pymui.IDCMP_MOUSEMOVE
        self._ev.install(self, idcmp)

    @pymui.muimethod(pymui.MUIM_Setup)
    def MCC_Setup(self, msg):
        self._ev.install(self, pymui.IDCMP_RAWKEY | pymui.IDCMP_MOUSEBUTTONS)
        return msg.DoSuper()

    @pymui.muimethod(pymui.MUIM_Cleanup)
    def MCC_Cleanup(self, msg):
        self._ev.uninstall()
        return msg.DoSuper()

    @pymui.muimethod(pymui.MUIM_HandleEvent)
    def MCC_HandleEvent(self, msg):
        self._ev.readmsg(msg)
        wl = self._watchers.get(ColorWeelHarmonies.EVENTMAP.get(self._ev.Class), [])
        for cb, args in wl:
            return cb(self._ev, *args)

    @pymui.muimethod(pymui.MUIM_AskMinMax)
    def _mcc_AskMinMax(self, msg):
        msg.DoSuper()

        minmax = msg.MinMaxInfo.contents

        w = int(self.WHEEL_HUE_RING_RADIUS_OUT*2+2)
        minmax.MinWidth = minmax.MinWidth.value + w
        minmax.MinHeight = minmax.MinHeight.value + w
        minmax.MaxWidth = minmax.MinWidth
        minmax.MaxHeight = minmax.MinHeight

    @pymui.muimethod(pymui.MUIM_Draw)
    def _mcc_Draw(self, msg):
        msg.DoSuper()

        if msg.flags.value & pymui.MADF_DRAWOBJECT:
            cr = self.cairo_context
            self.FillCairoContext()

            cr.save()
            self.repaint(cr)
            cr.restore()

    def mouse_to_user(self, x, y):
        r = self._hue_ring.get_width()/2
        x -= self.MLeft+r
        y -= self.MTop+r
        return x,y

    def hit_square(self, *p):
        return hypot(*p) < self.WHEEL_HUE_RING_RADIUS-1
        
    def hit_hue(self, *p):
        h = hypot(*p)
        return h >= self.WHEEL_HUE_RING_RADIUS and h <= self.WHEEL_HUE_RING_RADIUS_OUT

    def hit_harmony(self, x, y):
        r = hypot(x, y)
        if r >= self.HARMONIES_RADIUS_IN and r <= self.HARMONIES_RADIUS_OUT:
            # note: x and y can't be both 0 here
            self.Redraw()
            h = (get_angle(x, -y)/pi2) % 1.0
            h = (h-self.__hsv[0]) % 1.0
            h = ceil(floor(int(h*48)/2.)/2)/12.
            
            return (self.__hsv[0] + h) % 1.0, self.__hsv[1], self.__hsv[2]

    def repaint(self, cr):
        # Draw HUE ring
        hue_ring = self.draw_hue_ring()
        cr.set_source_surface(hue_ring, 0, 0)
        cr.paint()

        h = self.__hsv[0]
        a = h*pi2
        w = hue_ring.get_width()
        c = w/2
        rect = self.draw_rect(int(self.WHEEL_HUE_RING_RADIUS*2/sqrt(2)-4))
        cr.translate(c, c)
        self.__angle = pi/4 - a
        cr.rotate(self.__angle)
        t = -rect.get_width()/2
        cr.set_source_surface(rect,t,t)
        cr.paint()
        cr.identity_matrix()
        
        # Draw current HUE position as 2 circles
        x, y = get_pos(self.WHEEL_HUE_RING_RADIUS+self.WHEEL_HUE_RING_WIDTH/2, -a)
        x += c
        y += c
        cr.set_line_width(1.5)
        cr.set_source_rgb(1,1,1)
        cr.arc(x,y,6,0,pi2)
        cr.stroke()
        cr.set_source_rgb(0,0,0)
        cr.arc(x,y,5,0,pi2)
        cr.stroke()
        
        cr.set_line_width(1)
        cr.set_source_rgb(0,0,0)
        cr.move_to(x-.5,y)
        cr.line_to(x+.5,y)
        cr.stroke()
        
        return

        # Draw harmonies
        da = (get_angle(*self.__pos) or 0.)-pi/12.
        for i in xrange(12):
            cr.set_line_width(1 if i else 3)
            a1 = i*pi/6.+radians(3)+da
            a2 = (i+1)*pi/6.-radians(3)+da
            cr.arc(0,0,self.HARMONIES_RADIUS_IN,a1,a2)
            cr.arc_negative(0,0,self.HARMONIES_RADIUS_OUT,a2,a1)
            cr.close_path()
            cr.set_source_rgb(*hsv_to_rgb((h-i/12.) % 1.0 ,s,v))
            cr.fill_preserve()
            cr.set_source_rgb(vi,vi,vi)
            cr.stroke()

    def draw_hue_ring(self):
        if self._hue_ring:
            return self._hue_ring
        r = self.WHEEL_HUE_RING_RADIUS
        r2 = self.WHEEL_HUE_RING_RADIUS_OUT
        w = int(2*r2+2)
        img = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, w)
        cr = cairo.Context(img)
        cr.translate(r2+1,r2+1)
        cr.set_line_width(r*0.02)
        a = 0.0
        da = 0.5*atan(1./r)
        while a < pi2:
            c = hsv_to_rgb(a/pi2, 1., 1.)
            cr.set_source_rgb(*c)
            cr.move_to(*get_pos(r, -a))
            cr.line_to(*get_pos(r2, -a))
            cr.stroke()
            a += da
        self._hue_ring = img
        return img
    
    def draw_rect(self, w):
        if self.__rect:
            return self.__rect
            
        self.__rect = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, w)
        cr = cairo.Context(self.__rect)

        h,s,v = self.__hsv
        w -= 1
        for y in xrange(w+1):
            i = float(y) / w
            pat = cairo.LinearGradient(0, 0, w, 0)
            pat.add_color_stop_rgb(0,*hsv_to_rgb(h,0,1-i/2))
            pat.add_color_stop_rgb(1,*hsv_to_rgb(h,1,1-i))
            cr.move_to(0, y)
            cr.line_to(w, y)
            cr.set_source(pat)
            cr.stroke()
            
        return self.__rect
                    
        # Position inside the rect represented by circles
        x, y = self.__pos
        cr.set_source_rgb(1,1,1)
        cr.arc(x, y, 6, 0, pi2)
        cr.stroke()
        
        cr.set_source_rgb(0,0,0)
        cr.arc(x, y, 5, 0, pi2)
        cr.stroke()
        
        cr.move_to(x-.5, y)
        cr.line_to(x+.5, y)
        cr.stroke()

        return self.__rect

    def set_pos(self, x, y):
        self.__pos = x,y
        s = min(self.WHEEL_RADIUS, sqrt(x*x+y*y))/self.WHEEL_RADIUS
        v = self.__vmin*(1-s) + s
        h = get_angle(x,-y)
        if h is None:
            h = 0
        else:
            h = (h / pi2) % 1.0
        self.hsv = h,s,v
        return h,s,v
        
    def set_hue_pos(self, x, y):
        self.__hsv[0] = ((get_angle(x,-y) or 0.) / pi2) % 1.0
        self.hsv = self.__hsv
        return self.__hsv
        
    def set_square_pos(self, x, y):
        r = hypot(x, y)
        a = get_angle(x, y)
        if a:
            a -= self.__angle
        else:
            a = 0.
        x, y = get_pos(r, a)
        w = self.__rect.get_width()-1
        h = self.__rect.get_height()-1
        x = min(max(0., x+w/2.), float(w))
        y = min(max(0., y+h/2.), float(h))
        self.__pos = x, y
        x /= w
        y /= w
        y = 1-y
        s = x*y
        self.hsv = self.__hsv[0], s, (1-x)*(1+y)/2+s
        return self.__hsv

    def get_hsv(self):
        return tuple(self.__hsv)

    def set_hsv(self, hsv):
        hsv = list(hsv)
        if self.__hsv != hsv:
            self.__rect = None
            self.__hsv = hsv
            self.Redraw()
        
    hsv = property(fget=get_hsv, fset=set_hsv)


class ColorBox(pymui.Rectangle):
    _MCC_ = True
    _rgb = None
    
    def __init__(self, **kw):
        super(ColorBox, self).__init__(Draggable=True, **kw)
    
    @pymui.muimethod(pymui.MUIM_DragQuery)
    def _mcc_DragQuery(self, msg):
        msg.DoSuper()
        obj = msg.obj.contents
        return hasattr(obj, 'rgb') and obj.rgb is not None

    def _set_rgb(self, rgb):
        self._rgb = rgb
        if rgb is not None:
            self.Background = '2:%08x,%08x,%08x' % tuple(0x01010101 * int(v*255) for v in rgb)
        else:
            self.Background = pymui.MUII_ImageButtonBack
        
    def _get_rgb(self):
        return self._rgb
        
    rgb = property(fget=_get_rgb, fset=_set_rgb)


class DropColorBox(pymui.Rectangle):
    _MCC_ = True
    _rgb = None
    
    def __init__(self, width, height):
        super(DropColorBox, self).__init__(Frame='ImageButton',
                                            Background='ImageButtonBack',
                                            Selected=False,
                                            Dropable=True,
                                            Draggable=True,
                                            FixWidth=width, FixHeight=height,
                                            InputMode='RelVerify')
                                            
    @pymui.muimethod(pymui.MUIM_DragQuery)
    def _mcc_DragQuery(self, msg):
        msg.DoSuper()
        obj = msg.obj.contents
        return hasattr(obj, 'rgb') and obj.rgb is not None
                                            
    @pymui.muimethod(pymui.MUIM_DragDrop)
    def _mcc_Drop(self, msg):
        msg.DoSuper()
        obj = msg.obj.contents
        rgb = self.rgb
        self.rgb = obj.rgb
        if isinstance(obj, DropColorBox):
            obj.rgb = rgb
            
    def _set_rgb(self, rgb):
        if rgb is not None:
            self._rgb = tuple(rgb)
            self.Background = '2:%08x,%08x,%08x' % tuple(0x01010101 * int(v*255) for v in rgb)
        else:
            self._rgb = None
            self.Background = pymui.MUII_ImageButtonBack
        
    def _get_rgb(self):
        return self._rgb
        
    rgb = property(fget=_get_rgb, fset=_set_rgb)

    
class ColorHarmoniesWindow(pymui.Window):
    def __init__(self):
        super(ColorHarmoniesWindow, self).__init__(ID='CHRM',
                                                   Title='Color Harmonies',
                                                   CloseOnReq=True)

        self.RootObject = top = pymui.VGroup()
        self.widgets = {}

        self.colorwheel = ColorWeelHarmonies2()        
        top.AddChild(pymui.HCenter(self.colorwheel))

        self.hue = pymui.Slider(Min=0, Max=360, CycleChain=True)
        self.sat = pymui.Slider(Min=0, Max=100, CycleChain=True)
        self.value = pymui.Slider(Min=0, Max=100, CycleChain=True)
        
        self.red = pymui.Slider(Min=0, Max=255, CycleChain=True)
        self.green = pymui.Slider(Min=0, Max=255, CycleChain=True)
        self.blue = pymui.Slider(Min=0, Max=255, CycleChain=True)

        self.colorbox = ColorBox(Frame='Virtual', MaxWidth=16)

        grp = pymui.HGroup()
        grp.AddChild(self.colorbox)
        grp.AddChild(pymui.ColGroup(2, Child=(pymui.Label(_T('Red')+':'), self.red,
                                       pymui.Label(_T('Green')+':'), self.green,
                                       pymui.Label(_T('Blue')+':'), self.blue,
                                       pymui.Label(_T('Hue')+':'), self.hue,
                                       pymui.Label(_T('Saturation')+':'), self.sat,
                                       pymui.Label(_T('Value')+':'), self.value)))
        top.AddChild(grp)                

        bt = pymui.SimpleButton(_T("Use as background"), CycleChain=True)
        top.AddChild(bt)
        self.widgets['AsBgBt'] = bt
        
        top.AddChild(pymui.HBar(3))
        
        grp = pymui.VGroup(GroupTitle=_T('Palette'))
        top.AddChild(grp)
        
        ld_pal = pymui.SimpleButton(_T("Load"), CycleChain=True)
        sv_pal = pymui.SimpleButton(_T("Save"), CycleChain=True)
        grp.AddChild(pymui.HGroup(Child=(ld_pal, sv_pal)))
        
        vgrp = pymui.Virtgroup(SameSize=True, Columns=8, Spacing=0, HorizWeight=100, Horiz=False)
        sgrp = pymui.Scrollgroup(Contents=vgrp, AutoBars=True, FreeHoriz=False)
        grp.AddChild(pymui.HGroup(Child=(pymui.HSpace(0, HorizWeight=1), sgrp, pymui.HSpace(1, HorizWeight=1))))
        self._pal_bt = []
        for i in xrange(256):
            bt = DropColorBox(10, 10)
            vgrp.AddChild(bt)
            bt.Notify('Pressed', self._on_palbt, when=False)
            
            # Default colors: first = black, second = white
            if i == 0:
                bt.rgb = (0,0,0)
            elif i == 1:
                bt.rgb = (1,1,1)
                
            self._pal_bt.append(bt)

        # Notifications        
        self.hue.Notify('Value', lambda evt: self._set_hsv_channel(evt.value.value / 360., 0))
        self.sat.Notify('Value', lambda evt: self._set_hsv_channel(evt.value.value / 100., 1))
        self.value.Notify('Value', lambda evt: self._set_hsv_channel(evt.value.value / 100., 2))
        
        self.red.Notify('Value', lambda evt: self._set_rgb_channel(evt.value.value / 255., 0))
        self.green.Notify('Value', lambda evt: self._set_rgb_channel(evt.value.value / 255., 1))
        self.blue.Notify('Value', lambda evt: self._set_rgb_channel(evt.value.value / 255., 2))

        ld_pal.Notify('Pressed', self._on_ld_pal_pressed, when=False)
        sv_pal.Notify('Pressed', self._on_sv_pal_pressed, when=False)

    def set_hsv_callback(self, cb):
        self._hsv_cb = cb

    def _on_ld_pal_pressed(self, evt):
        filename = pymui.GetApp().get_filename('Select palette filename for loading', parent=self, pat='#?.pal')
        if filename:
            # Reset palette
            for bt in self._pal_bt:
                bt.rgb = None
                
            # Load and set
            with open(filename, 'r') as fd:
                for line in fd.readlines():
                    i, rgb = line.split(':')
                    try:
                        self._pal_bt[int(i)].rgb = [ int(x)/255. for x in rgb.split() ]
                    except IndexError:
                        pass
        
    def _on_sv_pal_pressed(self, evt):
        filename = pymui.GetApp().get_filename('Select palette filename for saving', parent=self, pat='#?.pal', read=False)
        if filename:
            with open(filename, 'w') as fd:
                for i, bt in enumerate(self._pal_bt):
                    if bt.rgb is None: continue
                    fd.write("%u: %u %u %u\n" % ((i,)+tuple(int(x*255) for x in bt.rgb)))

    def _on_palbt(self, evt):
        bt = evt.Source
        if bt.rgb is not None:
            self.rgb = bt.rgb
        else:
            bt.rgb = self.rgb

    def _set_hsv_channel(self, value, index):
        hsv = list(self.colorwheel.hsv)
        hsv[index] = value
        self.hsv = hsv

    def _set_rgb_channel(self, value, index):
        rgb = list(hsv_to_rgb(*self.colorwheel.hsv))
        rgb[index] = value
        self.rgb = rgb

    def _get_hsv(self):
        return (self.hue.Value.value/360., self.sat.Value.value/100., self.value.Value.value/100.)

    def _set_hsv(self, hsv):
        self.hue.NNSet('Value', int(hsv[0]*360.))
        self.sat.NNSet('Value', int(hsv[1]*100.))
        self.value.NNSet('Value', int(hsv[2]*100.))
        
        rgb = hsv_to_rgb(*hsv)
        self.colorbox.rgb = rgb
        rgb = [ int(x*255.) for x in rgb ]
        self.red.NNSet('Value', rgb[0])
        self.green.NNSet('Value', rgb[1])
        self.blue.NNSet('Value', rgb[2])
        
        self.colorwheel.hsv = hsv
        self._hsv_cb(hsv)

    def _get_rgb(self):
        return (self.red.Value.value/255., self.green.Value.value/255., self.blue.Value.value/255.)

    def _set_rgb(self, rgb):
        self.hsv = rgb_to_hsv(*rgb)

    hsv = property(fget=_get_hsv, fset=_set_hsv)
    rgb = property(fget=_get_rgb, fset=_set_rgb)


class ColorHarmoniesWindowMediator(utils.Mediator):
    NAME = "ColorHarmoniesWindowMediator"

    #### Private API ####

    __mode = 'idle'
    __brush = None
    _appmediator = None

    def __init__(self, component):
        assert isinstance(component, ColorHarmoniesWindow)
        super(ColorHarmoniesWindowMediator, self).__init__(ColorHarmoniesWindowMediator.NAME, component)

        self._appmediator = self.facade.retrieveMediator(view.ApplicationMediator.NAME)

        component.colorwheel.add_watcher('mouse-button', self._on_mouse_button, component.colorwheel)
        component.colorwheel.add_watcher('mouse-motion', self._on_mouse_motion, component.colorwheel)
        component.widgets['AsBgBt'].Notify('Pressed', self._on_color_as_bg, when=False)
        component.set_hsv_callback(self._set_hsv)
        
    def _set_hsv(self, hsv):
        model.DocumentProxy.get_active().set_brush_color_hsv(*hsv)

    def _on_mouse_button(self, evt, widget):
        rawkey = evt.RawKey
        if rawkey == IECODE_LBUTTON:
            if evt.Up:
                if self.__mode == 'idle': return
                widget.enable_mouse_motion(False)
                self.__mode = 'idle'
                hsv = widget.hsv
            else:
                if not evt.InObject: return
                pos = widget.mouse_to_user(evt.MouseX, evt.MouseY)
                if widget.hit_hue(*pos):
                    hsv = widget.set_hue_pos(*pos)
                    widget.enable_mouse_motion(True)
                    self.__mode = 'hue-move'
                elif widget.hit_square(*pos):
                    hsv = widget.set_square_pos(*pos)
                    widget.enable_mouse_motion(True)
                    self.__mode = 'square-move'
                else:
                    return
                    #hsv = widget.hit_harmony(*pos)
                    #if hsv is None: return

            self.viewComponent.hev = hsv
            model.DocumentProxy.get_active().set_brush_color_hsv(*hsv)
            return pymui.MUI_EventHandlerRC_Eat

    def _on_mouse_motion(self, evt, widget):
        pos = widget.mouse_to_user(evt.MouseX, evt.MouseY)
        if self.__mode == 'hue-move':
            hsv = widget.set_hue_pos(*pos)
        else:
            hsv = widget.set_square_pos(*pos)
        self.viewComponent.hsv = hsv
        model.DocumentProxy.get_active().set_brush_color_hsv(*hsv)
        return pymui.MUI_EventHandlerRC_Eat

    def _on_color_as_bg(self, evt):
        self._appmediator.set_background_rgb(self.viewComponent.rgb)

    ### notification handlers ###

    @mvcHandler(main.Gribouillis.DOC_ACTIVATE)
    def _on_activate_document(self, docproxy):
        self.__brush = docproxy.document.brush
        self.viewComponent.hsv = self.__brush.hsv

    @mvcHandler(main.Gribouillis.BRUSH_PROP_CHANGED)
    def _on_brush_prop_changed(self, brush, name):
        if self.__brush is brush and name == 'color':
            self.viewComponent.hsv = brush.hsv
