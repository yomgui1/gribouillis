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

from __future__ import with_statement

import os, pymui
import xml.etree.ElementTree as ET
from pymui.mcc.betterbalance import BetterBalance

import main, view
from utils import _T, resolve_path
from view import contexts, viewport
from model.prefs import *

from .eventparser import _KEYVALS
from .widgets import Ruler

__all__ = [ 'AppPrefWindow' ]

cal_text = """Measure the length of this bar and report the result in the next string gadget.
You can select unit of the measurement using the cycle gadget on top.
"""

MUI_MAPS = { 'mouse_left': 'mouse_leftpress',
             'mouse_middle': 'mouse_middlepress',
             'mouse_right': 'mouse_rightpress' 
             }

CALIBRATION_UNITS = [ 'in', 'cm', 'dpi' ]

def convert2mui(key):
    try:
        mod, key = key.split()
    except ValueError:
        return MUI_MAPS.get(key, key)
        
    if mod == "*":
        mod = 'any'
    else:
        mod = ' '.join(mod[1:-1].split('|'))
        
    return mod + ' ' + MUI_MAPS.get(key, key)

class _BindingsPrefHandler(PrefHandlerInterface):        
    def parse(self, prefs, element):
        bd = prefs['bindings'] = {}
        
        evtcls = map(str, contexts.ALL_EVENT_TYPES)
        for bind_el in element:
            ctx_name = bind_el.get('context')
            if ctx_name in bd:
                bind_list = bd[ctx_name]
            else:
                bd[ctx_name] = bind_list = []
                
            evtcl = bind_el.get('event').strip()
            if evtcl:
                action = bind_el.get('action').strip()
                try:
                    action = getattr(contexts.ALL_CONTEXTS[ctx_name], action)
                except:
                    print "[*DBG*] Bindings: Unknown action for context '%s': '%s'" % (ctx_name, action)
                else:
                    if action:
                        key = bind_el.get('key', '').strip()
                        any = bind_el.get('any', '').strip().lower() not in ['', 'false', '0', 'no']
                        repeat = bind_el.get('repeat', '').strip().lower() not in ['', 'false', '0', 'no']
                        data = dict(evtcl=contexts.ALL_EVENT_TYPES[evtcls.index(evtcl)], key=key, action=action, any=any, repeat=repeat)
                        
                        # Prefs
                        bind_list.append(data)
                        
    def save_data(self, prefs, root):
        binds = prefs['bindings']
        for ctx_name in sorted(contexts.ALL_CONTEXTS.keys()):
            for bind in sorted(binds[ctx_name], cmp=lambda x, y: cmp(x['action'].__name__, y['action'].__name__)):
                ET.SubElement(root, 'bind', {},
                              context=ctx_name,
                              event=bind['evtcl'].NAME,
                              key=bind['key'],
                              any=str(bind['any']),
                              repeat=str(bind['repeat']),
                              action=bind['action'].__name__)

class _ToolsWheelPrefHandler(PrefHandlerInterface):
    def parse(self, prefs, element):
        icons_names = prefs['view-icons-names']
        binds = prefs['view-toolswheel-binding']
        prefs['view-icons-path'] = element.get('icons_path', prefs['view-icons-path'])
        
        for bind_el in element:
            i = bind_el.get('index')
            if i is not None:
                i = int(i)
                if i in range(8):
                    name = bind_el.get('command')
                    cmd = None
                    for k,v in contexts.ALL_COMMANDS.iteritems():
                        if v.__name__ == name:
                            cmd = k
                            
                    if cmd is None:
                        print "[*DBG*] ToolsWheel: Unknown command: '%s'" % name
                        continue
                        
                    binds[i] = cmd
                    
                    name = bind_el.get('icon_normal', None)
                    if name:
                        icons_names[i] = name
                        
                    name = bind_el.get('icon_selected', None)
                    if name:
                        icons_names[8+i] = name

    def save_data(self, prefs, root):
        icons_names = prefs['view-icons-names']
        for i, cmd in enumerate(prefs['view-toolswheel-binding']):
            cmd = contexts.ALL_COMMANDS[cmd].__name__
            ET.SubElement(root, 'bind', {},
                          index=str(i),
                          icon_normal=icons_names[i],
                          icon_selected=icons_names[8+i],
                          command=cmd)
        
class _MetricsPrefHandler(PrefHandlerInterface):
    def parse(self, prefs, metrics):
        unit = metrics.get('unit', prefs['view-metrics-unit'])
        x = float(metrics.get('x', prefs['view-metrics-x']))
        y = float(metrics.get('y', prefs['view-metrics-y']))
        if unit in CALIBRATION_UNITS:
            # Update prefs
            prefs['view-metrics-unit'] = unit
            prefs['view-metrics-x'] = x
            prefs['view-metrics-y'] = y

    def save_data(self, prefs, root):
        root.set('unit', prefs['view-metrics-unit'])
        root.set('x', str(prefs['view-metrics-x']))
        root.set('y', str(prefs['view-metrics-y']))
                
class _RenderingPrefHandler(PrefHandlerInterface):
    MAPS = {
        'background': 'view-color-bg',
        'outlines': 'view-color-ol',
        'text': 'view-color-text',
        'handler_bg': 'view-color-handler-bg',
        'handler_ol': 'view-color-handler-ol',
        'wheel_bg': 'view-color-wheel-bg',
        'wheel_ol': 'view-color-wheel-ol',
        'wheel_sel': 'view-color-wheel-sel',
        'pp': 'view-color-passepartout',
        }
        
    def parse(self, prefs, rendering):
        prefs['view-filter-threshold'] = max(0, min(int(rendering.get('filter_threshold', prefs['view-filter-threshold'])), viewport.DocumentViewPort.MAX_SCALE))
        
        def convert(n, d):
            return max(0.0, min(float(color.get(n, d)), 1.0))
            
        def parse_color(color):
            name = self.MAPS.get(color.get('name'))
            if name:
                rgba = prefs[name]
                prefs[name] = ( convert('red', rgba[0]),
                                convert('green', rgba[1]),
                                convert('blue', rgba[2]),
                                convert('alpha', rgba[3]) )
        
        # Update prefs
        for color in rendering:
            parse_color(color)
            
        prefs['pymui-ruler-bg-pen'] = max(0, min(int(rendering.get('pymui_ruler_bg_pen', prefs['pymui-ruler-bg-pen'])), 255))
        prefs['pymui-ruler-fg-pen'] = max(0, min(int(rendering.get('pymui_ruler_fg_pen', prefs['pymui-ruler-fg-pen'])), 255))

    def save_data(self, prefs, root):
        for k, v in self.MAPS.iteritems():
            r,g,b,a = map(str, prefs[v])
            ET.SubElement(root, 'color', {}, name=k, red=r, green=g, blue=b, alpha=a)
            
        root.set('pymui_ruler_bg_pen', str(prefs['pymui-ruler-bg-pen']))
        root.set('pymui_ruler_fg_pen', str(prefs['pymui-ruler-fg-pen']))
        root.set('filter_threshold', str(prefs['view-filter-threshold']))
        
class _InterfacePrefHandler(PrefHandlerInterface):
    def parse(self, prefs, interface):
        avail_maps = pymui.GetApp().startup_windows
        win_list = interface.get('pymui_startup_win_list', ','.join(prefs['pymui-window-open-at-startup']))
        win_list = tuple(name for name in map(lambda x: x.strip().lower(), win_list.split(',')) if name in avail_maps)
        
        # Update prefs and MUI now
        prefs['pymui-window-open-at-startup'] = win_list

    def save_data(self, prefs, root):
        root.set('pymui_startup_win_list', ','.join(prefs['pymui-window-open-at-startup']))
        
class CalibrationBar(pymui.Rectangle):
    _MCC_ = True
    
    SIZE = 400
    HEIGHT = 12
    
    def __init__(self, default, string, horiz=True, **kwds):
        kwds['InnerSpacing'] = 0
        super(CalibrationBar, self).__init__(**kwds)
        
        self._string = string
        
        self.value = default
        self._horiz = horiz
        
        self.size = CalibrationBar.SIZE
    
    @pymui.muimethod(pymui.MUIM_AskMinMax)
    def _mcc_AskMinMax(self, msg):
        msg.DoSuper()
        mmi = msg.MinMaxInfo.contents
        
        if self._horiz:
            mmi.MaxWidth = CalibrationBar.SIZE
            mmi.MinWidth = CalibrationBar.SIZE
            mmi.MaxHeight = CalibrationBar.HEIGHT
            mmi.MinHeight = CalibrationBar.HEIGHT
        else:
            mmi.MaxWidth = CalibrationBar.HEIGHT
            mmi.MinWidth = CalibrationBar.HEIGHT
            mmi.MaxHeight = CalibrationBar.SIZE
            mmi.MinHeight = CalibrationBar.SIZE
            
    @pymui.muimethod(pymui.MUIM_Draw)
    def _mcc_Draw(self, msg):
        msg.DoSuper()
        if not (msg.flags.value & pymui.MADF_DRAWOBJECT): return

        left, top, right, bottom = self.MBox
        
        rp = self._rp
        rp.APen = 2
        
        if self._horiz:
            rp.Move(left, top)
            rp.Draw(left, bottom)
            rp.Move(right, top)
            rp.Draw(right, bottom)
        
            y = (top + bottom) / 2
            rp.Rect(rp.APen, left, y, right, y+1)
            
            self.size = self.MWidth
        else:
            rp.Move(left, top)
            rp.Draw(right, top)
            rp.Move(left, bottom)
            rp.Draw(right, bottom)
        
            x = (left + right) / 2
            rp.Rect(rp.APen, x, top, x+1, bottom)
            
            self.size = self.MHeight
            
    def set_value(self, value):
        value = max(1.0, min(float(value), 1000.0))
        self._value = value
        self._string.Contents = str(value)
        
    def set_calibration(self, value):
        self.value = self.size / value
        
    value = property(fget=lambda self: self._value, fset=set_value)
    calibration = property(fget=lambda self: self.size / self._value, fset=set_calibration)

class AppPrefWindow(pymui.Window):
    def __init__(self):
        super(AppPrefWindow, self).__init__(_T("Application Preferences"), ID='PREFS',
                                            CloseOnReq=True, NoMenus=True)
        
        top = pymui.VGroup()
        self.RootObject = top
        
        g = pymui.HGroup()
        top.AddChild(g)
        
        lister = pymui.Listview(List=pymui.List(SourceArray=[_T("Rendering"),
                                                             _T("Events binding"),
                                                             _T("Tools wheel"),
                                                             _T("Calibration"),
                                                             _T("Miscellaneous")],
                                                Frame='ReadList',
                                                CycleChain=True,
                                                AdjustWidth=True),
                                Input=False)
        g.AddChild(lister)
        
        self._pager = pymui.VGroup(PageMode=True)
        g.AddChild(self._pager)
        
        # Fill pages
        self._do_page_rendering(self._pager)
        self._do_page_inputs(self._pager)
        self._do_page_toolswheel(self._pager)
        self._do_page_calibration(self._pager)
        self._do_page_misc(self._pager)
        
        # Bottom buttons
        top.AddChild(pymui.HBar(4))
        grp = pymui.HGroup()
        top.AddChild(grp)
        
        bt_save = pymui.SimpleButton(_T("Save and close"), CycleChain=True)
        bt_apply = pymui.SimpleButton(_T("Apply"), CycleChain=True)
        bt_def = pymui.SimpleButton(_T("Reset to Defaults"), CycleChain=True)
        bt_revert = pymui.SimpleButton(_T("Revert"), CycleChain=True)
        grp.AddChild(bt_save, bt_apply, bt_def, bt_revert)
        
        bt_save.Notify('Pressed', self._on_save, when=False)
        bt_apply.Notify('Pressed', self.apply_config, when=False)
        bt_def.Notify('Pressed', self.use_defaults, when=False)
        bt_revert.Notify('Pressed', self.init_from_prefs, when=False)
        
        def callback(evt):
            self._pager.ActivePage = evt.value.value
            
        lister.Notify('Active', callback)
        lister.Active = 0
        
        # Register prefs handlers
        reg_pref_handler('bindings', _BindingsPrefHandler())
        reg_pref_handler('toolswheel', _ToolsWheelPrefHandler())
        reg_pref_handler('metrics', _MetricsPrefHandler())
        reg_pref_handler('rendering', _RenderingPrefHandler())
        reg_pref_handler('interface', _InterfacePrefHandler())
            
    def init_from_prefs(self, *a):
        self.Sleep = True
        try:
            # Events bindings
            self.clear_bindings()
            for ctx_name, bind_list in prefs['bindings'].iteritems():
                page = self._ctx_pages.get(ctx_name)
                page.vgp.InitChange()
                try:
                    for data in bind_list:
                        self.add_bind(page, **data)
                finally:
                    page.vgp.ExitChange()
            del ctx_name, bind_list, page, data
                    
            # ToolsWheel
            icons_path = resolve_path(prefs['view-icons-path'])
            for i, cmd in enumerate(prefs['view-toolswheel-binding']):
                self._toolswheel_strings[i].Contents = cmd
                
            for i, name in enumerate(prefs['view-icons-names'][:8]):
                self._popup[i].name = name
                self._popup[i].Button.object.Name = os.path.join(icons_path, name+'.png')
                
            for i, name in enumerate(prefs['view-icons-names'][8:]):
                self._popup[8+i].name = name
                self._popup[8+i].Button.object.Name = os.path.join(icons_path, name+'.png')
                
            del i, name, icons_path
                
            # Metrics
            unit = prefs['view-metrics-unit']
            self.cal_unit.Active = CALIBRATION_UNITS.index(unit)

            if unit == 'dpi':
                self.cal_bar_x.value = prefs['view-metrics-x']
                self.cal_bar_y.value = prefs['view-metrics-y']
            else:
                self.cal_bar_x.calibration = prefs['view-metrics-x']
                self.cal_bar_y.calibration = prefs['view-metrics-y']
                
            del unit
            
            # Rendering
            self._filter_threshold.Value = prefs['view-filter-threshold']
            
            for k, v in _RenderingPrefHandler.MAPS.iteritems():
                r,g,b,a = prefs[v]
                field, alpha = self._colors[k]
                field.Red = int(r * 255) * 0x01010101
                field.Green = int(g * 255) * 0x01010101
                field.Blue = int(b * 255) * 0x01010101
                alpha.Value = int(a * 100)
            
            self._ruler_bg_pen.Value = prefs['pymui-ruler-bg-pen']
            self._ruler_fg_pen.Value = prefs['pymui-ruler-fg-pen']
            
            del k, v
            
            # Interface
            win_list = prefs['pymui-window-open-at-startup']
            for key, bt in self._startup_win_bt.iteritems():
                bt.Selected = key in win_list
        finally:
            self.Sleep = False
                        
    def clear_bindings(self):
        for page in self._ctx_pages.itervalues():
            page.vgp.InitChange()
            try:
                for child in page.bindings:
                    page.vg.RemChild(child, lock=True)
            finally:
                page.vgp.ExitChange()
            page.bindings.clear()
            
    def save_config(self, filename='config.xml'):
        self.apply_config()
        save_preferences(filename)

    def apply_config(self, *a):
        # Events bindings
        for page in self._ctx_pages.itervalues():
            name = page.ctx.NAME
            page.ctx.reset_bindings()
            bind_list = prefs['bindings'][name] = []
            for bind in page.bindings.itervalues():
                data = bind.data
                if data:
                    bind_list.append(data)
                    key = data['evtcl'].encode(data['key'])
                    if data['any']: key |= contexts.EVENT_TAG_ANY
                    if data['repeat']: key |= contexts.EVENT_TAG_REPEAT
                    page.ctx.BINDINGS[key] = data['action']
                
        # Tools wheel
        icons_names = prefs['view-icons-names']
        binds = prefs['view-toolswheel-binding']
        for i, string in enumerate(self._toolswheel_strings):
            binds[i] = string.Contents.contents
            icons_names[i] = self._popup[i].name
            icons_names[8+i] = self._popup[8+i].name
        
        # Metrics
        unit = CALIBRATION_UNITS[self.cal_unit.Active.value]
        prefs['view-metrics-unit'] = unit
        
        if unit == 'dpi':
            unit = 'in'
            x = self.cal_bar_x.value
            y = self.cal_bar_y.value
        else:
            x = self.cal_bar_x.calibration # pixels per unit
            y = self.cal_bar_y.calibration # pixels per unit
            
        prefs['view-metrics-x'] = x
        prefs['view-metrics-y'] = y
        
        def set_ruler(unit, n, off):
            if unit == 'cm':
                Ruler.METRICS['cm'][2+off] = n
                Ruler.METRICS['in'][2+off] = n * 2.54
            elif unit == 'in':
                Ruler.METRICS['in'][2+off] = n
                Ruler.METRICS['cm'][2+off] = n / 2.54
            else:
                raise NotImplementedError("Metrics unit '%s' is not supported" % unit)
        
        set_ruler(unit, x, 0)
        set_ruler(unit, y, 1)
        
        # Rendering
        prefs['view-filter-threshold'] = self._filter_threshold.Value.value
        
        def apply_color(field, alpha):
            col = [ float(x.value) / 0xffffffff for x in field.RGB ]
            col.append(alpha.Value.value / 100.)
            return tuple(col)
            
        for k, v in _RenderingPrefHandler.MAPS.iteritems():
            prefs[v] = apply_color(*self._colors[k])
        
        prefs['pymui-ruler-bg-pen'] = self._ruler_bg_pen.Value.value
        prefs['pymui-ruler-fg-pen'] = self._ruler_fg_pen.Value.value
        
        # Interface
        win_list = []
        for key, bt in self._startup_win_bt.iteritems():
            if bt.Selected.value:
                win_list.append(key)
        prefs['pymui-window-open-at-startup'] = win_list
        del win_list
        
        # Redraw all windows
        # TODO: change that for a MVC notification as prefs is a model unit
        try:
            pymui.GetApp().mediator.document_mediator.refresh_all()
        except:
            pass
        
    def use_defaults(self, *a):
        set_to_defaults()
        self.init_from_prefs()
    
    def _do_page_misc(self, reg):
        top = pymui.VGroup()
        reg.AddChild(pymui.HCenter(pymui.VCenter(top)))
        
        grp = pymui.ColGroup(2, GroupTitle=_T("Interface"))
        grp.AddChild(pymui.Label(_T("Windows to open at startup")+':', ))
        box = pymui.ColGroup(2, Frame='Group')
        self._startup_win_bt = {}
        win_list = prefs['pymui-window-open-at-startup']
        d = pymui.GetApp().startup_windows
        for key in sorted(d.keys(), cmp=lambda x,y: cmp(d[x].name, d[y].name)):
            bt = self._startup_win_bt[key] = pymui.CheckMark(key in win_list, CycleChain=True)
            box.AddChild(bt)
            box.AddChild(pymui.Label(pymui.MUIX_L + d[key].name))
        grp.AddChild(box)
        top.AddChild(grp)
        
    def _do_page_rendering(self, reg):
        top = pymui.VGroup(SameWidth=True)
        reg.AddChild(pymui.HCenter(pymui.VCenter(top)))
        
        grp = pymui.ColGroup(2, GroupTitle=_T("Antialiasing"))
        grp.AddChild(pymui.Label(_T("Filter level threshold")+':'))
        self._filter_threshold = pymui.Slider(Min=0, Max=viewport.DocumentViewPort.MAX_SCALE,
                                              Default=viewport.DocumentViewPort.DEFAULT_FILTER_THRESHOLD,
                                              Value=prefs['view-filter-threshold'],
                                              CycleChain=True)
        grp.AddChild(self._filter_threshold)
        top.AddChild(grp)
        
        def new_color(parent, label, color):
            rgb = pymui.c_ULONG.ArrayType(3)(*tuple(int(x*255)*0x01010101 for x in color[:3]))
            field = pymui.Colorfield(CycleChain=True,
                                     InputMode='RelVerify',
                                     Frame='ImageButton',
                                     FixWidth=64,
                                     RGB=rgb)
            cadj = pymui.Coloradjust(CycleChain=True, RGB=rgb)
            bt = pymui.SimpleButton(_T("Close"), CycleChain=True)
            grp = pymui.VGroup(Frame='Group')
            grp.AddChild(cadj)
            grp.AddChild(bt)
            popup = pymui.Popobject(Button=field, Object=grp)
            alpha = pymui.Numericbutton(CycleChain=True,
                                        Min=0, Max=100, Default=100,
                                        Value=int(color[3]*100),
                                        Format="%lu%%",
                                        ShortHelp=_T("Transparency level"))
            cadj.Notify('RGB', lambda evt: field.SetAttr('RGB', evt.value))
            bt.Notify('Pressed', lambda evt: popup.Close(0), when=False)
            
            parent.AddChild(pymui.Label(_T(label)+':'))
            parent.AddChild(popup)
            parent.AddChild(alpha)
            return field, alpha
            
        self._colors = {}
        grp = pymui.ColGroup(3, GroupTitle=_T("Tools colors"))
        self._colors['background'] = new_color(grp, "Text background", prefs['view-color-bg'])
        self._colors['outlines'] = new_color(grp, "Text outlines", prefs['view-color-ol'])
        self._colors['text'] = new_color(grp, "Text color", prefs['view-color-text'])
        self._colors['handler_bg'] = new_color(grp, "Handler background", prefs['view-color-handler-bg'])
        self._colors['handler_ol'] = new_color(grp, "Handler outlines", prefs['view-color-handler-ol'])
        self._colors['wheel_bg'] = new_color(grp, "Wheel background", prefs['view-color-wheel-bg'])
        self._colors['wheel_ol'] = new_color(grp, "Wheel outlines", prefs['view-color-wheel-ol'])
        self._colors['wheel_sel'] = new_color(grp, "Wheel selection", prefs['view-color-wheel-sel'])
        self._colors['pp'] = new_color(grp, "PassePartout", prefs['view-color-passepartout'])
        top.AddChild(grp)
        
        grp = pymui.ColGroup(2, GroupTitle=_T("Rulers"))
        grp.AddChild(pymui.Label(_T("Background pen")+':'))
        self._ruler_bg_pen = pymui.Slider(CycleChain=True,
                                          Min=0, Max=255, Default=1,
                                          Value=prefs['pymui-ruler-bg-pen'])
        grp.AddChild(self._ruler_bg_pen)
        grp.AddChild(pymui.Label(_T("Foreground pen")+':'))
        self._ruler_fg_pen = pymui.Slider(CycleChain=True,
                                          Min=0, Max=255, Default=1,
                                          Value=prefs['pymui-ruler-fg-pen'])
        grp.AddChild(self._ruler_fg_pen)
        top.AddChild(grp)
        
    def _do_page_calibration(self, reg):
        top = pymui.VGroup()
        reg.AddChild(pymui.HCenter(pymui.VCenter(top)))
        
        # Contents automatically controled by the CalibrationBar object
        cal_result_x = pymui.String(Frame='String',
                                    Accept="0123456789.",
                                    FixWidthTxt="######",
                                    Format=pymui.MUIV_String_Format_Right,
                                    CycleChain=True)
        cal_result_y = pymui.String(Frame='String',
                                    Accept="0123456789.",
                                    FixWidthTxt="######",
                                    Format=pymui.MUIV_String_Format_Right,
                                    CycleChain=True)
                                  
        self.cal_bar_x = CalibrationBar(prefs['view-metrics-x'], cal_result_x, horiz=True, ShortHelp=_T(cal_text))
        self.cal_bar_y = CalibrationBar(prefs['view-metrics-y'], cal_result_y, horiz=False, ShortHelp=_T(cal_text))
        
        self.cal_unit = pymui.Cycle(CALIBRATION_UNITS,
                                    Active=CALIBRATION_UNITS.index(prefs['view-metrics-unit']),
                                    CycleChain=True)
        
        grp = pymui.ColGroup(2, Frame='Group', Child=(pymui.Label(_T("Calibration unit")+':'), self.cal_unit,
                                                      pymui.Label(_T("Horizontal axis")+':'), cal_result_x,
                                                      pymui.Label(_T("Vertical axis")+':'), cal_result_y))
        top.AddChild(self.cal_bar_x)
        top.AddChild(pymui.HGroup(Child=(self.cal_bar_y, pymui.HCenter(grp))))
                
        def callback(evt, wd):
            wd.value = evt.value.contents
            
        cal_result_x.Notify('Acknowledge', callback, self.cal_bar_x)
        cal_result_y.Notify('Acknowledge', callback, self.cal_bar_y)
                
    def _do_page_inputs(self, reg):
        self._event_types = map(str, contexts.ALL_EVENT_TYPES)
        top = self._grp_inputs = pymui.HGroup()
        reg.AddChild(self._grp_inputs)
                
        # List of contexts
        self._ctx_names = sorted(contexts.ALL_CONTEXTS.keys())
        self._list_ctx = o = pymui.List(Title=pymui.MUIX_B+_T('Contexts'),
                                        SourceArray=self._ctx_names,
                                        Frame='ReadList',
                                        CycleChain=True,
                                        AdjustWidth=True)
        top.AddChild(pymui.Listview(List=o, Input=False))

        # List of currents bindings
        g = pymui.VGroup(GroupTitle=pymui.MUIX_B+_T('Bindings on selected context'))
        top.AddChild(g)
                        
        self._bt_new = pymui.SimpleButton(_T('Add binding'), CycleChain=True)
        g.AddChild(self._bt_new)
        
        self._ctx_page_grp = pymui.VGroup(PageMode=True)
        g.AddChild(self._ctx_page_grp)
        
        self._ctx_pages = {}
        
        def add_ctx_page(name):
            page = pymui.VGroup(GroupTitle=name)
            page.vg = pymui.VGroupV()
            page.vg.AddChild(pymui.HVSpace())
            page.vgp = pymui.Scrollgroup(Contents=page.vg, FreeHoriz=False)
            page.ctx = contexts.ALL_CONTEXTS[name]
            page.bindings = {}
            
            page.AddChild(page.vgp)
            
            self._ctx_page_grp.AddChild(page)
            self._ctx_pages[name] = page
                        
        for name in self._ctx_names:
            add_ctx_page(name)
        
        # Notifications
        self._list_ctx.Notify('Active', self._on_ctx_active)
        self._bt_new.Notify('Pressed', self._on_new_bind, when=False)
    
    def _do_page_toolswheel(self, reg):
        top = pymui.VGroup()
        reg.AddChild(top)
        
        colg = pymui.ColGroup(4)
        top.AddChild(colg)
                
        self._toolswheel_strings = [None]*8
        self._popup = [None]*16
        
        all_commands = sorted(contexts.ALL_COMMANDS.keys())
        
        def new_entry(label, idx):
            icons_path = resolve_path(prefs['view-icons-path'])
            def get_icons(off):
                icons = pymui.ColGroup(4, Frame='Group')
                for name in sorted(contexts.ICONS.keys()):
                    obj = pymui.Dtpic(Name=os.path.join(icons_path, name+'.png'),
                                      InputMode='RelVerify',
                                      LightenOnMouse=True)
                    icons.AddChild(obj)
                    obj.Notify('Pressed', self._on_popup_icon_sel, when=False, name=name, idx=idx, off=off)
                return icons
                
            colg.AddChild(pymui.Label(label+':'))
            
            icons_names = prefs['view-icons-names']
            bt = pymui.Dtpic(Name=os.path.join(icons_path, icons_names[idx]+'.png'),
                             Frame='ImageButton',
                             InputMode='RelVerify')
            popup = pymui.Popobject(Button=bt, Object=get_icons(0), Light=True)
            popup.name = icons_names[idx]
            colg.AddChild(popup)
            self._popup[idx] = popup
            
            bt = pymui.Dtpic(Name=os.path.join(icons_path, icons_names[8+idx]+'.png'),
                             Frame='ImageButton',
                             InputMode='RelVerify')
            popup = pymui.Popobject(Button=bt, Object=get_icons(8), Light=True)
            popup.name = icons_names[8+idx]
            colg.AddChild(popup)
            self._popup[8+idx] = popup
            
            string = pymui.String(Frame='String', CycleChain=True,
                                  Contents=prefs['view-toolswheel-binding'][idx] or '',
                                  ShortHelp=_T("Command to execute when tool region selected"))
            self._toolswheel_strings[idx] = string
            
            popup = pymui.Poplist(Array=all_commands,
                                  String=string,
                                  Button=pymui.Image(Frame='ImageButton',
                                                     Spec=pymui.MUII_PopUp,
                                                     InputMode='RelVerify'))
            colg.AddChild(popup)
            
        new_entry(_T('N'), 6)
        new_entry(_T('NE'), 7)
        new_entry(_T('E'), 0)
        new_entry(_T('SE'), 1)
        new_entry(_T('S'), 2)
        new_entry(_T('SO'), 3)
        new_entry(_T('O'), 4)
        new_entry(_T('NO'), 5)
        
        top.AddChild(pymui.HVSpace())
        
    def _on_popup_icon_sel(self, evt, name, idx, off):
        popup = self._popup[off+idx]
        popup.name = name
        popup.Button.object.Name = os.path.join(resolve_path(prefs['view-icons-path']), name+'.png')
        popup.Close(0)

    def _on_save(self, evt):
        self.save_config()
        self.Open = False
        
    def new_bind(self, evtcl, action=None):
        page = self._ctx_pages[self._ctx_names[self._ctx_page_grp.ActivePage.value]]
        self.add_bind(page)
        
    def add_bind(self, page, **extras):
        # Delete bind button
        del_bt = pymui.Image(Frame='ImageButton', Spec=pymui.MUII_Close, InputMode='RelVerify',
                             ShortHelp=_T("Remove this binding."))

        # Event type cycle
        event_type = pymui.Cycle(self._event_types, Weight=0, CycleChain=True,
                                 ShortHelp=_T("Event type to listen to."))
        
        # Key adjustment (disabled by default)
        key_adj = pymui.Keyadjust(AllowMouseEvents=True, AllowMultipleKeys=False, Disabled=True, CycleChain=True,
                                  ShortHelp=_T("Key that trigs the specified action."))
                                  
        # Any toggle button
        any_bt = pymui.CheckMark(CycleChain=True,
                                 ShortHelp=_T("Doesn't take care of any modificators when key is pressed to trig the action."))
                 
        # Repeat toggle button
        repeat_bt = pymui.CheckMark(CycleChain=True,
                                    InnerRight=4,
                                    ShortHelp=_T("If selected, only the first occurance of an event is used, repeated ones are discarded."))
        
        class Bind:
            def __init__(self, key_adj, event_type, any_bt, repeat_bt, action_str):
                self.key_adj = key_adj
                self.event_type = event_type
                self.any_bt = any_bt
                self.repeat_bt = repeat_bt
                self.action_str = action_str
                
            @property
            def data(self):
                # Convert MUI gadgets states into binding prefs data
                evtcl = contexts.ALL_EVENT_TYPES[self.event_type.Active.value]
                key = self.key_adj.Contents.contents.strip()
                any = self.any_bt.Selected.value
                repeat = self.repeat_bt.Selected.value
                action = page.ctx.AVAIL_ACTIONS.get(self.action_str.Contents.contents)
                if action:
                    return dict(evtcl=evtcl, action=action, key=key, any=any, repeat=repeat)
                
        str_action = pymui.String(Frame='String', CycleChain=True,
                                  ShortHelp=_T("Action to execute.\nAvailable actions depend on current context."))
        action_popup = pymui.Poplist(Array=page.ctx.AVAIL_ACTION_NAMES,
                                     Button=pymui.Image(Frame='ImageButton',
                                                        Spec=pymui.MUII_PopUp,
                                                        InputMode='RelVerify'),
                                     String=str_action)
        bind = Bind(key_adj, event_type, any_bt, repeat_bt, str_action)
        
        page.vgp.InitChange()
        try:
            grp = pymui.HGroup(Child=[ del_bt,
                                       pymui.Label(_T('Action')+':'), action_popup,
                                       pymui.Label(_T('When')+':'),event_type,
                                       pymui.Label(_T('Key')+':'), key_adj,
                                       pymui.Label(_T('Any')+':'), any_bt, 
                                       pymui.Label(_T('Repeat')+':'), repeat_bt ],
                               SameHeight=True)
            page.vg.AddChild(grp, lock=True)
            page.vg.MoveMember(grp, -2) # MUI magic to replace the space at the bottom
        finally:
            page.vgp.ExitChange()
        
        page.bindings[grp] = bind
        
        event_type.Notify('Active', self._on_evt_active, key_adj)
        del_bt.Notify('Pressed', self._on_del_bind, page, grp, when=False)
        any_bt.Notify('Selected', self._on_any_bt, key_adj)
        
        if extras:
            event_type.Active = self._event_types.index(extras.get('evtcl', 0).NAME)
            key_adj.Contents = extras.get('key', '')
            any_bt.Selected = extras.get('any', False)
            repeat_bt.Selected = extras.get('repeat', False)
            str_action.Contents = extras.get('action', '')._act_name
             
    def _on_ctx_active(self, evt):
        n = evt.value.value
        if n >= 0:
            self._ctx_page_grp.ActivePage = n
            
    def _on_new_bind(self, evt):
        evt = contexts.ALL_EVENT_TYPES[0]
        self.new_bind(evt)

    def _on_del_bind(self, evt, page, child):
        page.vg.RemChild(child, lock=True)
        del page.bindings[child]
        
    def _on_evt_active(self, evt, key_adj):
        n = evt.value.value
        if n <= 2: # tricky! To replace with a more robust method.
            key_adj.Disabled = True
        else:
            key_adj.Disabled = False

    def _on_any_bt(self, evt, key_adj):
        if evt.value.value:
            key = key_adj.Contents.contents.strip()
            if key:
                key_adj.Contents = key.split()[-1]
                