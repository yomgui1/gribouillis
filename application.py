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

from __future__ import with_statement
import os, sys, thread, time

# TODO: dynamic selection
from languages import lang_dict    
lang = lang_dict['default']

from pymui import *
from pymui.mcc.busy import Busy

from brush import Brush
from DrawWindow import DrawWindow
from ColorChooser import ColorChooser
from brush_ui import BrushSelectWindow
from BGSelect import MiniBackgroundSelect
from CMSPrefs import CMSPrefsWindow
from model_ui import ModelInfoWindow
from raster import Raster
from model import SimpleTiledModel
from controler import DrawControler

class Gribouillis(Application):
    VERSION = 0.1
    DATE    = "05/09/2009"

    def __init__(self, datapath, userpath=None):
        if userpath is None:
            userpath = datapath

        self.paths = dict(data=datapath, user=userpath) 
        self.last_loaded_dir = 'RAM:'
        self.last_saved_dir = 'RAM:'

        # Create the MVC object
        model = SimpleTiledModel()
        view = Raster()
        self.controler = DrawControler(view, model, self)

        # Create Windows
        self.win_Draw = None
        self.win_Draw_Normal = DrawWindow(lang.DrawWinTitle, False)
        self.win_Draw_Full = DrawWindow(lang.DrawWinTitle, True)
        self.win_Color = ColorChooser(lang.ColorChooserWinTitle)
        self.win_BSel = BrushSelectWindow(lang.BrushSelectWinTitle)
        self.win_MiniBGSel = MiniBackgroundSelect()
        self.win_CMSPrefs = CMSPrefsWindow(lang.CMSWinTitle)
        self.win_ModelInfo = ModelInfoWindow(lang.ModelInfoWinTitle)

        # Create Menus
        menu_def = { lang.MenuProject: ((lang.MenuProjectLoadImage,   'L', self.OnLoadImage),
                                        (lang.MenuProjectSaveImage,   'S', self.OnSaveImage),
                                        None, # Separator
                                        (lang.MenuProjectSetupData,   'ctrl d', self.ShowModelInfo),
                                        None,
                                        (lang.MenuProjectQuit,        'Q', self.OnQuitRequest),
                                        ),
                     lang.MenuEdit:    ((lang.MenuEditClearAll,       'K', self.ClearAll),
                                        (lang.MenuEditUndo,           'Z', self.Undo),
                                        (lang.MenuEditRedo,           'Y', self.Redo),
                                        ),
                     lang.MenuView:    ((lang.MenuViewIncreaseZoom,   '+', None),
                                        (lang.MenuViewDecreaseZoom,   '-', None),
                                        (lang.MenuViewResetZoom,      '=', self.ResetZoom),
                                        (lang.MenuViewCenter,         '*', self.Center),
                                        ('#'+lang.MenuViewFullscreen, 'F', self.ToggleFullscreen),
                                        None,
                                        (lang.MenuViewSetCMSProfile,  'P', self.win_CMSPrefs.OpenWindow),
                                        ),
                     lang.MenuWindows: ((lang.MenuWindowDraw,         'D', self.OpenDrawWindow),
                                        (lang.MenuWindowColorChooser, 'C', self.win_Color.OpenWindow),
                                        (lang.MenuWindowBrushSel,     'B', self.win_BSel.OpenWindow),
                                        (lang.MenuWindowMiniBGSel,    'G', self.win_MiniBGSel.OpenWindow),
                                        ),
                     lang.MenuDebug:   (('#'+lang.MenuDegugRaster,    None, self.SetDebug, 'raster'),
                                        ),
                     }

        strip = Menustrip()   
        order = (lang.MenuProject, lang.MenuEdit, lang.MenuView, lang.MenuWindows, lang.MenuDebug)
        for k in order:
            v = menu_def[k]
            menu = Menu(k)
            strip.AddTail(menu)

            for t in v:
                if t is None:
                    menu.AddTail(Menuitem('-')) # Separator
                    continue
                elif t[0][0] == '#': # toggled item
                    title = t[0][1:]
                    item = Menuitem(title, t[1], Checkit=True)
                    item.title = title
                else:
                    item = Menuitem(t[0], t[1])
                if t[2]:
                    item.Bind(*t[2:])
                menu.AddTail(item)
 
        # Create Application object
        super(Gribouillis, self).__init__(
            Title       = "Gribouillis",
            Version     = "$VER: Gribouillis %s (%s)" % (self.VERSION, self.DATE),
            Copyright   = "\xa92009, Guillaume ROGUEZ",
            Author      = "Guillaume ROGUEZ",
            Description = lang.AppliDescription,
            Base        = "Gribouillis",
            Menustrip   = strip,
        )

        # We can't open a window if it has not been attached to the application
        self.AddChild(self.win_Color)
        self.AddChild(self.win_Draw_Normal)
        self.AddChild(self.win_Draw_Full)
        self.AddChild(self.win_BSel)
        self.AddChild(self.win_MiniBGSel)
        self.AddChild(self.win_CMSPrefs)
        self.AddChild(self.win_ModelInfo)

        # Create draw window
        self.InitDrawWindow()

        # Init brushes
        self.init_brushes()

        # Init color
        self.win_Color.add_watcher(self.OnColorChanged)
        self.set_active_brush(self.brushes[0])
        self.set_color(1.0, 1.0, 1.0)

        # Init backgrounds selection window
        self.win_MiniBGSel.add_watcher(self.LoadBackground)
        bg_dir ="backgrounds"
        if os.path.isdir(bg_dir):
            for name in sorted(os.listdir(bg_dir)):
                if name.endswith('.png'):
                    self.win_MiniBGSel.AddImage(os.path.join(bg_dir, name))

        # Open windows now
        self.win_BSel.OpenWindow()
        self.win_Color.OpenWindow()
        self.win_Draw.OpenWindow()

    def OpenDrawWindow(self):
        self.win_Draw.OpenWindow()

    def InitDrawWindow(self, fullscreen=False):
        if self.win_Draw: return
        self.win_Draw = (self.win_Draw_Full if fullscreen else self.win_Draw_Normal)
        self.win_Draw.attach_raster(self.controler.view)

    def TermDrawWindow(self):
        if not self.win_Draw: return
        win = self.win_Draw
        win.dettach_raster()
        self.win_Draw = None

    def init_brushes(self):
        self._draw_brush = self.win_BSel.brush
        self._brush = None
        
        self.paths['builtins_brushes'] = os.path.join(self.paths['data'], 'brushes')
        self.paths['user_brushes'] = os.path.join(self.paths['user'], 'brushes')

        def listbrushes(path):
            return [fn[:-4] for fn in os.listdir(path) if fn.endswith('.myb')]

        builtins_brushes = listbrushes(self.paths['builtins_brushes'])
        user_brushes = listbrushes(self.paths['user_brushes'])

        # remove duplicates from builtins
        builtins_brushes = [name for name in builtins_brushes if name not in user_brushes]

        # sorting brushes
        unsorted_brushes = user_brushes + builtins_brushes
        sorted_brushes = []
        for path in (self.paths['user_brushes'], self.paths['builtins_brushes']):
            fn = os.path.join(path, 'order.conf')
            if not os.path.exists(fn): continue
            with open(fn) as f:
                for line in f:
                    name = line.strip()
                    if name not in unsorted_brushes: continue
                    unsorted_brushes.remove(name)
                    sorted_brushes.append(name)

        self.brushes_names = unsorted_brushes + sorted_brushes

        self._all_paths = (self.paths['user_brushes'], self.paths['builtins_brushes'])
        self.brushes = []
        for name in self.brushes_names[:3]:
            self._add_brush(name)
            
        self.win_BSel.SetBrushes(self.brushes)

    def _add_brush(self, name):
        b = Brush()
        b.load(self._all_paths, name)
        b.Notify(MUIA_Selected, self.OnSelectBrush)
        self.brushes.append(b)
        return b

    def set_color(self, *rgb):
        self.win_Color.color = rgb # Coloradjust object will call OnColorChanged method

    def OnColorChanged(self, color): # Called by the ColorChooser window
        self.brush.color = color

    def OnSelectBrush(self, evt):
        if self._brush is not evt.source:
            self.brush = evt.source
        else:
            evt.source.NNSet(MUIA_Selected, True)

    def set_active_brush(self, brush):
        self.brush.copy(brush)
        if self._brush:
            self._brush.NNSet(MUIA_Selected, False)
        self._brush = brush
        brush.NNSet(MUIA_Selected, True)
        self.controler.model.UseBrush(self.brush)

    brush = property(fget=lambda self: self._draw_brush, fset=set_active_brush)

    def LoadBackground(self, bg):
        self.controler.LoadBackground(bg.Name.value)

    def OnLoadImage(self, evt):
        filename = GetFilename(self.win_Draw, lang.LoadImageReqTitle,
                               self.last_loaded_dir, "#?.(png|jpeg|jpg|targa|tga|gif|ora)",
                               save=False)[0]
        if filename:
            self.last_loaded_dir = os.path.dirname(filename)
            self.controler.LoadImage(filename)

    def OnSaveImage(self, evt):
        if not getattr(self, 'win_SaveWin', None):
            o_text = Text(Frame='String', Background='TextBack')
            g1 = ColGroup(2, Child=(Label("Image size:"), o_text))
            
            b_ok = KeyButton(lang.ButtonOkLabel, lang.ButtonOkKey, CycleChain=True)
            b_cancel = KeyButton(lang.ButtonCancelLabel, lang.ButtonCancelKey, CycleChain=True)
            g2 = HGroup(Child=(b_ok, b_cancel))

            o_busy = Busy(ShowMe=False, FixHeight=8)
            top = VGroup(Child=(g1, o_busy, HBar(3), g2))

            self.win_SaveWin = Window("Saving Image",
                                      RootObject=top,
                                      DefaultObject=b_ok, CloseOnReq=True)
            self.win_SaveWin.text = o_text
            self.win_SaveWin.busy = o_busy
            self.win_SaveWin.bt_group = g2
            
            self.win_SaveWin.Notify('Open', self.SaveImageFinalize, when=False)
            b_ok.Notify('Pressed', self.OkSaveImage, when=False)
            b_cancel.Notify('Pressed', self.SaveImageFinalize, when=False)

            self.AddChild(self.win_SaveWin)
        else:
            self.win_SaveWin.CloseWindow()
            
        _, _, w, h = self.controler.model.bbox
        self.win_SaveWin.text.Contents = "%u x %u" % (w, h)
        self.win_Draw.Sleep = True
        self.win_SaveWin.RefWindow=self.win_Draw
        self.win_SaveWin.OpenWindow()

    @Event.noevent
    def OkSaveImage(self):
        filename = GetFilename(self.win_Draw, lang.SaveImageReqTitle,
                               self.last_saved_dir, "#?.(png|jpeg|jpg|targa|tga|gif|ora)",
                               save=True)[0]
        if filename:
            self.last_saved_dir = os.path.dirname(filename)
            self.win_SaveWin.bt_group.Disabled = True
            self.win_SaveWin.busy.ShowMe = True
            
            thread.start_new_thread(self.SaveImageJob, (time, filename))

    def SaveImageFinalize(self, evt):
        self.win_SaveWin.bt_group.Disabled = False
        self.win_SaveWin.busy.ShowMe = False
        self.win_SaveWin.Open = False
        self.win_Draw.Sleep = False

    def SaveImageJob(self, time, filename):
        try:
            start = time.time()
            self.controler.SaveImage(filename)
            print "[*DBG*]: Saved %s in" % filename, time.time() - start, "seconds"
        finally:
            self.PushMethod(self.win_SaveWin, 3, MUIM_Set, MUIA_Window_Open, False)

    def OnQuitRequest(self, evt):
        self.Quit()

    def ToggleFullscreen(self, evt):
        state = self.win_Draw.fullscreen
        self.TermDrawWindow()
        self.InitDrawWindow(not state)
        self.win_Draw.Open = True

    def OnChangedCMSProfiles(self, prefs):
        if prefs.in_profile and prefs.out_profile:
            self.controler.view.CMS_SetInputProfile(prefs.in_profile)
            self.controler.view.CMS_SetOutputProfile(prefs.out_profile)
            self.controler.view.CMS_InitTransform()
            self.controler.view.EnableCMS()
        else:
            self.controler.view.EnableCMS(False)
        self.controler.view.RedrawFull()

    def SetDebug(self, evt, what):
        if what == 'raster':
            self.controler.view.debug = not self.controler.view.debug
            self.controler.view.RedrawFull()

    def ClearAll(self, evt):
        self.controler.Clear()

    def Cleanup(self, model=None):
        self.controler.Cleanup()

    def Undo(self, evt):
        self.controler.Undo()
        
    def Redo(self, evt):
        self.controler.Redo()

    def ResetZoom(self, evt):
        self.controler.ResetZoom()

    def Center(self, evt):
        self.controler.Center()

    def ShowModelInfo(self, evt):
        self.win_ModelInfo.ShowModel(self.controler.model)

    def EnableCMS(self, state=True):
        self.controler.view.EnableCMS(state)

    def SetRGBProfile(self, name, profile):
        pass

    def CopyBrush(self, brush):
        b = self._add_brush(brush.Name)
        b.copy(brush)
        self.win_BSel.AddBrush(b)
        self.brush = b
        return b

    def EnterPickMode(self):
        self.controler.EnterPickMode()
