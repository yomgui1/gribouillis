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
    def __init__(self):
        im = OpenImage("MOSSYS:Prefs/Gfx/Monitors/Photo.png")
        im = im.convert('RGB')
        _, _, w, h = im.getbbox()
        self._buf = _pixarray.PixelArray(w, h, PIXFMT_RGB_8)
        self._buf.from_string(im.tostring())

        super(CMSPreview, self).__init__(MCC=True, FillArea=False)

    def MCC_AskMinMax(self, minx, defx, maxx, minh, defh, maxh):
        w = minx+self._buf.Width
        h = miny+self._buf.Height
        return w, w, w, h, h, h

    def MCC_Draw(self, flags):
        if flags != MADF_DRAWOBJECT:
            return

        w = self._buf.Width
        h = self._buf.Height
        self._rp.ScaledBlit8(self._buf, w, h, self.MLeft, self.MTop, w, h)

    def Tranform(self, in_p, out_p, intent, flags):
        trans = lcms.Tranform(in_p, lcms.TYPE_RGB_8, out_p, lcms.TYPE_RGB_8, intent, flags)
        tmpbuf = self._buf.copy()
        self._buf.from_pixarray(trans(self._buf, tmpbuf, self._buf.Width * self._buf.Height))


class CMSPrefsWindow(Window):
    def __init__(self, title):
        super(CMSPrefsWindow, self).__init__(title, ID=0, LeftEdge='centered', TopEdge='centered')

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

        self.Notify('CloseRequest', True, self.Close)

        top = VGroup()
        g = HGroup()
        bt_g = HGroup()
        top.AddChild(g, HBar(0), bt_g)
        self.RootObject = top

        o = SimpleButton("Close"); o.CycleChain = True
        o.Notify('Pressed', False, self.Close)
        bt_g.AddChild(o)
        
        top = VGroup()
        self._preview = CMSPreview()
        g.AddChild(self._preview, top)

        enable = CheckMark()
        enable.CycleChain = True
        enable.Notify('Selected', MUIV_EveryTime, self.OnEnableCMS, MUIV_TriggerValue)
        g = HGroup()
        g.AddChild(enable, LLabel("Activate Color Management"), HSpace(0))
        top.AddChild(g)

        self._groups['cms'] = cms = VGroup()
        top.AddChild(cms)

        g = ColGroup(2, Title="Working Surfaces Profiles")
        cms.AddChild(g)

        for name in ('RGB', 'CMYK'):
            self._groups[name] = Group()
            g.AddChild(Label("%s:" % name), self._groups[name])
            self._create_choices(name, (n for n, _ in self._profiles[name]))

        rg = VGroup(Title="Rendering")
        cms.AddChild(rg)

        g = ColGroup(2)
        rg.AddChild(g)
        self._groups['mon'] = Group()
        g.AddChild(Label("Monitor profile:"), self._groups['mon'])
        self._create_choices('mon', (n for n, _ in self._profiles['mon']))

        l = self._intents_entries = sorted(self._intents.keys())
        o = Cycle(l, CycleChain=True, Active=l.index(self._options['intent']))
        o.Notify('Active', MUIV_EveryTime, self.OnIntentChanged, MUIV_TriggerValue)
        g.AddChild(Label("Intent:"), o)

        g = HGroup()
        rg.AddChild(g)
        o = CheckMark(Selected=self._options['bpcomp'])
        o.Notify('Selected', MUIV_EveryTime,
                 self.OnOptionChanged,
                 'bpcomp', MUIV_TriggerValue)
        g.AddChild(HSpace(0), o, LLabel("Black Point Compensation"))

        self.OnEnableCMS(False)

    def _create_choices(self, name, entries, active=0):
        if name in self._cycles:
            self._groups[name].RemChild(self._cycles[name])
        o = self._cycles[name] = Cycle(entries, CycleChain=True, Active=active)
        o.Notify('Active', MUIV_EveryTime, self.OnCycleProfile, MUIV_TriggerValue, name)
        self._groups[name].AddChild(o, lock=True)

    def OnEnableCMS(self, state):
        self._groups['cms'].Disabled = not state
        self.ApplicationObject.EnableCMS(state)

    def OnCycleProfile(self, active, name):
        plist = self._profiles[name]
        # From file?
        if active == len(plist)-1:
            fn = getfilename(self, "Choose %s color profile" % name,
                             self.last_load_dir, "#?.icc",
                             False)
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

    @property
    def options(self):
        return self._options
