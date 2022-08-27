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

# Python 2.5 compatibility


import pymui, cairo, os, glob, array
from math import *
from colorsys import hsv_to_rgb, rgb_to_hsv

import model, view, main, utils
from utils import _T

__all__ = [ 'ColorHarmoniesWindow' ]

pi2 = pi*2
IECODE_LBUTTON = 0x68

PAL_PAT = '|'.join(ext[1:] for ext in model.palette.SUPPORTED_EXTENSIONS)
if PAL_PAT:
    PAL_PAT = '.(%s)' % PAL_PAT
PAL_PAT = '#?' + PAL_PAT

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
        for i in range(12):
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

    __hue_ring = None
    __hsv = [0., 0., 0.]
    __pos = (0., 0.)
    __rect = None

    HARMONIES_RADIUS = 20
    HARMONIES_PADDING = 10
    
    WHEEL_HUE_RING_RADIUS = 128
    WHEEL_HUE_RING_WIDTH = 16
    WHEEL_HUE_RING_RADIUS_OUT = WHEEL_HUE_RING_RADIUS+WHEEL_HUE_RING_WIDTH
    
    WHEEL_RADIUS = WHEEL_HUE_RING_RADIUS * 2

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
        r = self.__hue_ring.get_width()/2
        x -= self.MLeft+r
        y -= self.MTop+r
        return x,y

    def hit_square(self, x, y):
        return x < self.__rmax and x >= -self.__rmax \
            and y < self.__rmax and y >= -self.__rmax
        
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

        rect = self.draw_rect()
        c = hue_ring.get_width() / 2
        cr.translate(c, c)
        self.__rmax = rect.get_width() / 2 + 1
        w = -self.__rmax+1
        cr.set_source_surface(rect, w, w)
        cr.paint()
        
        # Draw current HUE position as two circles
        x, y = get_pos(self.WHEEL_HUE_RING_RADIUS+self.WHEEL_HUE_RING_WIDTH/2, -self.__hsv[0]*pi2)
        
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
        
        # Position inside the rect represented by two circles also
        s = self.__hsv[1]
        v = self.__hsv[2]
        w = -w-1
        
        if v >= .5:
            x = s
            y = (v-1)*(s-2)
        else:
            x = 2*v*(s-1) + 1
            y = -v*s + 1
        
        x = (x*2-1)*w
        y = (y*2-1)*w
        
        cr.set_source_rgb(1,1,1)
        cr.arc(x, y, 6, 0, pi2)
        cr.stroke()
        
        cr.set_source_rgb(0,0,0)
        cr.arc(x, y, 5, 0, pi2)
        cr.stroke()
        
        cr.move_to(x-.5, y)
        cr.line_to(x+.5, y)
        cr.stroke()

        return

        # Draw harmonies
        da = (get_angle(*self.__pos) or 0.)-pi/12.
        for i in range(12):
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
        if self.__hue_ring:
            return self.__hue_ring
            
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
        self.__hue_ring = img
        return img
    
    def draw_rect(self):
        if self.__rect:
            return self.__rect
            
        w = int(self.WHEEL_HUE_RING_RADIUS*2/sqrt(2)-4)
        self.__rect = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, w)
        cr = cairo.Context(self.__rect)

        h,s,v = self.__hsv
        w -= 1
        for y in range(w+1):
            i = float(y) / w
            pat = cairo.LinearGradient(0, 0, w, 0)
            pat.add_color_stop_rgb(0,*hsv_to_rgb(h,0,1-i/2))
            pat.add_color_stop_rgb(1,*hsv_to_rgb(h,1,1-i))
            cr.move_to(0, y)
            cr.line_to(w, y)
            cr.set_source(pat)
            cr.stroke()
            
        return self.__rect

    def DEPRECATED_set_pos(self, x, y):
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
        self.Redraw()
        return self.__hsv
        
    def set_square_pos(self, x, y):
        w = self.__rmax-1
        x = max(-w, min(x, w))
        y = max(-w, min(y, w))
        
        self.__pos = x, y
        
        x = float(x)/(2*w) + .5
        y = float(y)/(2*w) + .5
        
        if (1-x)*(1-y) <= 0.1:
            v = (1-x)*.5 - y + 1
            s = ((1-y)/v if v else 0)
        else:
            s = x
            v = y / (s - 2) + 1
            
        self.hsv = self.__hsv[0], s, v
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
        obj = msg.obj.object
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
        super(DropColorBox, self).__init__(Frame='None',
                                           InnerSpacing=(0,)*4,
                                           Selected=False,
                                           Dropable=True,
                                           Draggable=True,
                                           FixWidth=width, FixHeight=height,
                                           InputMode='RelVerify')
                                            
    @pymui.muimethod(pymui.MUIM_DragQuery)
    def _mcc_DragQuery(self, msg):
        msg.DoSuper()
        obj = msg.obj.object
        return hasattr(obj, 'rgb') and obj.rgb is not None
                                            
    @pymui.muimethod(pymui.MUIM_DragDrop)
    def _mcc_Drop(self, msg):
        msg.DoSuper()
        obj = msg.obj.object
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
    __palettes = {'default': model.palette.DefaultPalette}
    _current_pal = None
    _predefpal_list = ['default']
    _predefpallister = None
    
    def __init__(self, name):
        super(ColorHarmoniesWindow, self).__init__(ID='CHRM',
                                                   Title=name,
                                                   CloseOnReq=True)
        self.name = name

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
        
        toggle_pal = pymui.Text(_T("Toggle Palette panel"),
                                InputMode='Toggle',
                                Frame='Button',
                                Background='ButtonBack',
                                Font=pymui.MUIV_Font_Button,
                                PreParse=pymui.MUIX_C,
                                Selected=True)
        top.AddChild(toggle_pal)
        
        grp = pymui.VGroup(GroupTitle=_T('Palette'))
        top.AddChild(grp)
        
        toggle_pal.Notify('Selected', lambda evt: grp.SetAttr('ShowMe', evt.value.value))
        
        ld_pal = pymui.SimpleButton(_T("Load"), CycleChain=True)
        sv_pal = pymui.SimpleButton(_T("Save"), CycleChain=True)
        del_pal = pymui.SimpleButton(_T("Delete"), CycleChain=True)
        grp.AddChild(pymui.HGroup(Child=(ld_pal, sv_pal, del_pal)))
        
        self._predefpallister = pymui.List(SourceArray=self.palettes_list)
        pal_name_bt = pymui.Text(Frame='Text', CycleChain=True, ShortHelp=_T('Predefined palettes'))
        popup = pymui.Popobject(Object=pymui.Listview(List=self._predefpallister),
                                String=pal_name_bt,
                                Button=pymui.Image(Frame='ImageButton',
                                                   Spec=pymui.MUII_PopUp,
                                                   InputMode='RelVerify',
                                                   CycleChain=True))
                                                     
        grp.AddChild(pymui.HGroup(Child=(pymui.Label(_T('Avails')+':'), popup)))
        sort_luma = pymui.SimpleButton(_T('Luminance'), CycleChain=True)
        sort_hue = pymui.SimpleButton(_T('Hue'), CycleChain=True)
        sort_sat = pymui.SimpleButton(_T('Saturation'), CycleChain=True)
        sort_value = pymui.SimpleButton(_T('Value'), CycleChain=True)
        grp.AddChild(pymui.HGroup(Child=(pymui.Label(_T('Sort by')+':'), sort_luma, sort_hue, sort_sat, sort_value)))
        grp.AddChild(pymui.HBar(0))
        
        vgrp = pymui.VGroup(SameSize=True, Columns=16, Spacing=1, HorizWeight=100, Horiz=False, Background='2:00000000,00000000,00000000')
        grp.AddChild(pymui.HCenter(vgrp))
        self._pal_bt = []
        for i in range(256):
            bt = DropColorBox(12, 12)
            vgrp.AddChild(bt)
            bt.Notify('Pressed', self._on_palbt, when=False)
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
        del_pal.Notify('Pressed', self._on_del_pal_pressed, when=False)

        self._predefpallister.Notify('DoubleClick', self._on_popup_predef_sel, popup)
        self._predefpallister.Notify('Active', self._on_predef_list_active, pal_name_bt, del_pal)
        
        sort_luma.Notify('Pressed', lambda evt, cmp: self.sort_palette(cmp), self._cmp_luma, when=False)
        sort_hue.Notify('Pressed', lambda evt, cmp: self.sort_palette(cmp), self._cmp_hue, when=False)
        sort_sat.Notify('Pressed', lambda evt, cmp: self.sort_palette(cmp), self._cmp_sat, when=False)
        sort_value.Notify('Pressed', lambda evt, cmp: self.sort_palette(cmp), self._cmp_value, when=False)
        
        # final setup
        self._use_palette('default')
        
        toggle_pal.Selected = False # start in no palette mode

    def _load_palette(self, filename):
        name = os.path.splitext(os.path.basename(filename))[0]
        ColorHarmoniesWindow.__palettes[name] = model.Palette(name, filename)
                            
        def icmp(x,y):
            return cmp(x.lower(), y.lower())
            
        keys = ColorHarmoniesWindow.__palettes.keys()
        keys.remove('default')
        self._predefpal_list = sorted(keys, cmp=icmp)
        self._predefpal_list.insert(0, 'default')
        
        if self._predefpallister:
            self._predefpallister.Clear()
            map(lambda x: self._predefpallister.InsertSingleString(x), self._predefpal_list)
        
        return name
                    
    def _use_palette(self, name):
        if name not in ColorHarmoniesWindow.__palettes:
            return
            
        # Set buttons
        for i, data in enumerate(ColorHarmoniesWindow.__palettes[name]):
            self._pal_bt[i].rgb = data.rgb
            
        # Reset the rest
        for i in range(i+1, 256):
            self._pal_bt[i].rgb = None

        self._predefpallister.Active = self._predefpal_list.index(name)
        self._current_pal = name
    
    def set_hsv_callback(self, cb):
        self._hsv_cb = cb

    def _on_ld_pal_pressed(self, evt):
        filename = pymui.GetApp().get_filename(_T('Select palette filename for loading'), parent=self, pat=PAL_PAT)
        if filename:
            name = self._load_palette(filename)
            self._use_palette(name)
            
    def _on_sv_pal_pressed(self, evt):
        filename = pymui.GetApp().get_filename(_T('Select palette filename for saving'), parent=self, pat=PAL_PAT, read=False)
        if filename:
            palette = model.Palette(os.path.splitext(os.path.basename(filename))[0])
            for i, bt in enumerate(self._pal_bt):
                if bt.rgb is not None:
                    palette[i].rgb = bt.rgb
                
            try:
                palette.savetofile(filename)
            except NotImplementedError:
                pymui.DoRequest(app=pymui.GetApp(), title="Error", format="Unkown palette file type", gadgets='*_Ok')

    def _on_del_pal_pressed(self, evt):
        i = self._predefpallister.Active.value
        name = self._predefpal_list[i]
        if name == "default":
            return # not possible to remove the default palette
            
        self._predefpal_list.pop(i)
        self._predefpallister.Remove(i)
        self._use_palette("default")
    
    def _on_palbt(self, evt):
        bt = evt.Source
        if bt.rgb is not None:
            self.rgb = bt.rgb
        else:
            bt.rgb = self.rgb

    def _on_popup_predef_sel(self, evt, popup):
        popup.Close(0)
        i = self._predefpallister.Active.value
        self._use_palette(self._predefpal_list[i])
        
    def _on_predef_list_active(self, evt, bt, del_bt):
        name = self._predefpal_list[evt.value.value]
        del_bt.Disabled = name == 'default'
        bt.Contents = name
        self._use_palette(name)
            
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

    def sort_palette(self, cmp):
        for i, rgb in enumerate(sorted((data.rgb for data in self.palette if data.rgb is not None), cmp=cmp)):
            self._pal_bt[i].rgb = rgb

    @staticmethod
    def _cmp_luma(c1, c2):
        l1 = 0.2126*c1[0] + 0.7152*c1[1] + 0.0722*c1[2]
        l2 = 0.2126*c2[0] + 0.7152*c2[1] + 0.0722*c2[2]
        return cmp(l1, l2)
        
    @staticmethod
    def _cmp_hue(c1, c2):
        return cmp(rgb_to_hsv(*c1)[0], rgb_to_hsv(*c2)[0])
        
    @staticmethod
    def _cmp_sat(c1, c2):
        return cmp(rgb_to_hsv(*c1)[1], rgb_to_hsv(*c2)[1])
        
    @staticmethod
    def _cmp_value(c1, c2):
        return cmp(rgb_to_hsv(*c1)[2], rgb_to_hsv(*c2)[2])

    @property
    def palettes_list(self):
        path = 'PROGDIR:palettes'
        res = []
        for x in (glob.glob(os.path.join(path, '*'+ext)) for ext in model.palette.SUPPORTED_EXTENSIONS):
            res += x
        for filename in res:
            self._load_palette(filename)
            
        return self._predefpal_list

    @property
    def palette(self):
        return self.__palettes[self._current_pal]
        
    hsv = property(fget=_get_hsv, fset=_set_hsv)
    rgb = property(fget=_get_rgb, fset=_set_rgb)

