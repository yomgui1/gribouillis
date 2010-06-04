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
import os.path, lcms, _pixarray
from PIL.Image import open as OpenImage

__all__ = ('CMSPrefsWindow',)

class CMSPreview(Area):
    MCC = True
    SIZE = 196

    def __init__(self):
        im = OpenImage("MOSSYS:Prefs/Gfx/Monitors/Photo.png")
        im = im.convert('RGB')
        _, _, w, h = im.getbbox()
        self._bufsrc = _pixarray.PixelArray(w, h, _pixarray.PIXFMT_RGB_8)
        self._bufsrc.from_string(im.tostring())
        self._bufdst = self._bufsrc.copy()

        super(CMSPreview, self).__init__(FillArea=False)

    def MCC_AskMinMax(self):
        self.DoSuperMethod(cl, msg)
        minmax = msg.MinMaxInfo.contents

        w = minmax.MinWidth.value + self.SIZE
        h = minmax.MinHeigh.value + self.SIZE

        minmax.MinWidth = w
        minmax.DefWidth = w
        minmax.MaxWidth = w
        minmax.MinHeight = h
        minmax.DefHeight = h
        minmax.MaxHeight = h

    @muimethod(MUIM_Draw)
    def MCC_Draw(self, msg):
        msg.DoSuper()
        if msg.flags.value & MADF_DRAWOBJECT == 0: return
        self._rp.ScaledBlit8(self._bufdst, self._bufdst.Width, self._bufdst.Height,
                             self.MLeft, self.MTop, self.SIZE, self.SIZE)

    def Tranform(self, in_p, out_p, intent, flags):
        trans = lcms.Transform(in_p, lcms.TYPE_RGB_8, out_p, lcms.TYPE_RGB_8, intent, flags)
        trans(self._bufsrc, self._bufdst, self._bufdst.Width * self._bufdst.Height)


class CMSPrefsWindow(Window):
    def __init__(self, title):
        super(CMSPrefsWindow, self).__init__(title, ID=0, LeftEdge='centered', TopEdge='centered', CloseOnReq=True)

        self.last_load_dir = None   
        self._ok_cb = []
        self._groups = {}
        self._cycles = {}
        sRGBProfile = lcms.CreateBuiltinProfile('sRGB')
        self._profiles = { 'RGB': [["sRGB (built-in)", sRGBProfile],
                                   ["From file...", None]],
                           'CMYK': [["None", None],
                                    ["From file...", None]],
                           'mon': [["sRGB (built-in)", sRGBProfile],
                                   ["From file...", None]],
                         }
        self._intents = {'Perceptual': lcms.INTENT_PERCEPTUAL,
                         'Relative colorimetric': lcms.INTENT_RELATIVE_COLORIMETRIC,
                         'Absolute colorimetric': lcms.INTENT_ABSOLUTE_COLORIMETRIC,
                         'Saturation': lcms.INTENT_SATURATION,
                        }

        self._options = {'RGB': 0, 'CMYK': 0, 'mon': 0,
                         'intent': 'Perceptual',
                         'bpcomp': False}

        top = VGroup()
        g = HGroup()
        bt_g = HGroup()
        top.AddChild(g, HBar(0), bt_g)
        self.RootObject = top

        o = SimpleButton("Close"); o.CycleChain = True
        o.Notify('Pressed', self.CloseWindow, when=False)
        bt_g.AddChild(o)
        
        top = VGroup()
        self._preview = CMSPreview()
        g.AddChild(self._preview, top)

        enable = CheckMark()
        enable.CycleChain = True
        enable.Notify('Selected', self.OnEnableCMS, MUIV_TriggerValue)
        g = HGroup()
        g.AddChild(enable, LLabel("Activate Color Management"), HSpace(0))
        top.AddChild(g)

        self._groups['cms'] = cms = VGroup()
        top.AddChild(cms)

        g = ColGroup(2, GroupTitle="Working Surfaces Profiles")
        cms.AddChild(g)

        for name in ('RGB', 'CMYK'):
            self._groups[name] = Group()
            g.AddChild(Label("%s:" % name), self._groups[name])
            self._create_choices(name, (n for n, _ in self._profiles[name]))

        rg = VGroup(GroupTitle="Rendering")
        cms.AddChild(rg)

        g = ColGroup(2)
        rg.AddChild(g)
        self._groups['mon'] = Group()
        g.AddChild(Label("Monitor profile:"), self._groups['mon'])
        self._create_choices('mon', (n for n, _ in self._profiles['mon']))

        l = self._intents_entries = sorted(self._intents.keys())
        o = Cycle(l, CycleChain=True, Active=l.index(self._options['intent']))
        o.Notify('Active', self.OnIntentChanged, MUIV_TriggerValue)
        g.AddChild(Label("Intent:"), o)

        g = HGroup()
        rg.AddChild(g)
        o = CheckMark(selected=self._options['bpcomp'])
        o.Notify('Selected', self.OnOptionChanged,
                 'bpcomp', MUIV_TriggerValue)
        g.AddChild(HSpace(0), o, LLabel("Black Point Compensation"))

        self.OnEnableCMS(False)

    def _create_choices(self, name, entries, active=0):
        if name in self._cycles:
            self._groups[name].RemChild(self._cycles[name])
        o = self._cycles[name] = Cycle(tuple(entries), CycleChain=True, Active=active)
        o.Notify('Active', self.OnCycleProfile, MUIV_TriggerValue, name)
        self._groups[name].AddChild(o, lock=True)

    def OnEnableCMS(self, state):
        self._groups['cms'].Disabled = not state
        #self.ApplicationObject.value.EnableCMS(state)

    def OnCycleProfile(self, active, name):
        plist = self._profiles[name]
        # From file?
        if active == len(plist)-1:
            fn = GetFilename(self, "Choose %s color profile" % name,
                             self.last_load_dir, "#?.icc",
                             save=False)
            if fn is not None and os.path.isfile(fn):
                profile = lcms.Profile(fn)
                self.last_load_dir = os.path.dirname(fn)
                plist.insert(active, [os.path.splitext(os.path.basename(fn))[0], profile])
                self._create_choices(name, (n for n, _ in plist), active)
            else:
                return
            
        print "[*DBG*] profile set for %s" % name
        self._options[name] = active
        
        if name in ('mon', 'RGB'):
            self._do_preview()

    def OnIntentChanged(self, active):
        self._options['intent'] = self._intents_entries[active]
        self._do_preview()

    def OnOptionChanged(self, name, value):
        self._options[name] = value
        self._do_preview()

    def _do_preview(self):
        in_p = self._profiles['RGB'][self._options['RGB']][1]
        out_p = self._profiles['mon'][self._options['mon']][1]
        flags = (lcms.FLAGS_BLACKPOINTCOMPENSATION if self._options['bpcomp'] else 0)
        self._preview.Tranform(in_p, out_p, self._intents[self._options['intent']], flags)
        self._preview.Redraw()

    @property
    def options(self):
        return self._options
