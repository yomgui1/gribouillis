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
import os.path, lcms

class CMSPrefsWindow(Window):
    def __init__(self, title):
        super(CMSPrefsWindow, self).__init__(title, ID=0, LeftEdge='centered', TopEdge='centered')

        self.last_load_dir = None   
        self._ok_cb = []
        self._groups = {}
        self._cycles = {}
        self._profiles = { 'RGB': [["sRGB (built-in)", None],
                                   ["From file...", None]],
                           'CMYK': [["None", None],
                                    ["From file...", None]],
                           'mon': [["sRGB (built-in)", None],
                                   ["From file...", None]],
                         }
        self._intents = {'Perceptual': lcms.INTENT_PERCEPTUAL,
                         'Relative colorimetric': lcms.INTENT_RELATIVE_COLORIMETRIC,
                         'Absolute colorimetric': lcms.INTENT_ABSOLUTE_COLORIMETRIC,
                         'Saturation': lcms.INTENT_SATURATION,
                        }

        self.Notify('CloseRequest', True, self.Close)
        
        g = HGroup()
        self.RootObject = g

        top = VGroup()
        g.AddChild(Dtpic("MOSSYS:Prefs/Gfx/Monitors/Photo.png"), top)

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

        l = sorted(self._intents.keys())
        o = Cycle(l, CycleChain=True, Active=l.index('Perceptual'))
        g.AddChild(Label("Intent:"), o)

        g = HGroup()
        rg.AddChild(g)
        o = CheckMark()
        g.AddChild(HSpace(0), o, LLabel("Black Point Compensation"))

        self.OnEnableCMS(False) 

    def _create_choices(self, name, entries, active=0):
        if name in self._cycles:
            self._groups[name].RemChild(self._cycles[name])
        o = self._cycles[name] = Cycle(entries, CycleChain=True, Active=active)
        o.Notify('Active', MUIV_EveryTime, self.OnCycleProfile, MUIV_TriggerValue, name)
        self._groups[name].AddChild(o, lock=True)

    def Open(self):
        #self._str_in.Contents = self._in_profile
        #self._str_out.Contents = self._out_profile
        super(CMSPrefsWindow, self).Open()

    def OnEnableCMS(self, status):
        self._groups['cms'].Disabled = not status
        #self.ApplicationObject.EnableCMS(status)

    def OnCycleProfile(self, active, name):
        plist = self._profiles[name]
        # From file?
        if active == len(plist)-1:
            fn = getfilename(self, "Choose %s color profile" % name,
                             self.last_load_dir, "#?.icc",
                             False)
            if fn is not None and os.path.isfile(fn):
                self.last_load_dir = os.path.dirname(fn)
                plist.insert(active, [os.path.splitext(os.path.basename(fn))[0], None])
                self._create_choices(name, (n for n, _ in plist), active)
            else:
                return
        
        _, p = plist[active]
        print "[*DBG*] profile for %s:" % name, p

        #self.ApplicationObject.SetProfile(name, p)
        
