# -*- coding: latin-1 -*-
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


import pymui, os, sys, string, gc, glob, random

import main
import view
import view.context as ctx

from utils import _T
from model.document import LASTS_FILENAME
from model import prefs

from .layermgr import LayerMgr
from .cmdhistoric import *
from .colorharmonies import *
from .brushhouse import *
from .brusheditor import *
from .cms import *
from .prefwin import *
from .docinfo import *
from .docviewer import FullscreenDocWindow, FramedDocWindow

__all__ = ['Application']

prefs.add_default('pymui-window-open-at-startup', ['splash'])

BASE = "Gribouillis"
COPYRIGHT = "\xa92009-2012, Guillaume Roguez"
DESCRIPTION = "Painting program for MorphOS"

about_msg = string.Template(
    _T(
        """\033b$base-3\033n
$description

version $version.$build ($date)

$copyright

$base uses following technologies:

\033bPython2\033n
\033bPureMVC\033n
\033bLittleCMS 2\033n
\033bLayGroup.mcc\033n

\033c\033b~~~ Extras ~~~\033n\033l

* \033bVisiBone2\033n palette from \033ihttp://www.visibone.com/swatches/\033n
* \033bHighlander icons and splash image by Christophe Delorme\033n
* \033bExtras icons, splash image and header text by Sébastien Poelz\033n
* \033bBoomy icons by Milosz Wlazlo\033n

\033c\033b~~~ Alpha testing, icons and design suggestions ~~~\033n\033l

    Christophe 'highlander' Delorme
    Sébastien Poelzl
    Neal Roguez (my son, 4 years old, the first tester!)

\033c\033b~~~ Thanks to ~~~\033n\033l

    My familly for its patience.
    The MorphOS Team to continue the dream.
    Nicholai Benalal for Scribble (specially the Frankfur tennis club).
    Dennis Ritchie (1941-2011) for the C.
    Internet for the knownledge database.
"""
    )
)


class Application(pymui.Application, view.mixin.ApplicationMixin):
    _open_doc = None  # last open document filename

    def __init__(self):
        super(Application, self).__init__(
            Title="Gribouillis",
            Version="$VER: Gribouillis %s.%d (%s)" % (main.VERSION, main.BUILD, main.DATE),
            Copyright=COPYRIGHT,
            Author="Guillaume ROGUEZ",
            Description=DESCRIPTION,
            Base=BASE,
            Menustrip=self._create_menustrip(),
        )

        self.fullscreen_win = FullscreenDocWindow()
        self.AddChild(self.fullscreen_win)

        self.windows = dwin = {}

        dwin['LayerMgr'] = LayerMgr(_T("Layer Manager"))
        dwin['CmdHist'] = CommandsHistoryList(_T("Commands History"))
        dwin['ColorMgr'] = ColorHarmoniesWindow(_T("Color Manager"))
        dwin['BrushEditor'] = BrushEditorWindow(_T("Brush Editor"))
        dwin['BrushHouse'] = BrushHouseWindow(_T("Brush House"))
        # self.cms_assign_win = AssignICCWindow()
        # self.cms_conv_win = ConvertICCWindow()

        dwin['Splash'] = Splash(_T("Splash"))
        dwin['About'] = AboutWindow()
        dwin['DocInfo'] = DocInfoWindow(_T("Document Information"))

        # List of window that can be automatically open at startup
        self.startup_windows = ['LayerMgr', 'CmdHist', 'ColorMgr', 'BrushEditor', 'BrushHouse', 'Splash']

        # Should be created after startup-open-window list
        # self.appprefwin = AppPrefWindow()

        for win in dwin.values():
            self.AddChild(win)

    def _create_menustrip(self):
        menu_def = {
            _T('Application'): (
                (_T('New document'), 'N', 'new-doc'),
                (_T('Load document...'), 'O', 'load-doc'),
                (_T('Save document'), 'S', 'save-doc'),
                (_T('Save as document...'), None, 'save-as-doc'),
                None,  # Separator
                (_T('Load image as layer...'), None, 'load-layer-image'),
                None,  # Separator
                ('About', '?', lambda *a: self.about.OpenWindow()),
                ('Quit', 'Q', 'quit'),
            ),
            _T('Edit'): (
                (_T('Undo'), 'Z', 'undo'),
                (_T('Redo'), 'Y', 'redo'),
                (_T('Flush'), None, 'flush'),
            ),
            _T('View'): (
                (_T('Reset'), '=', 'reset-view'),
                (_T('Load background...'), None, 'load-background'),
                (_T('Toggle rulers'), 'R', 'toggle-rulers'),
                (_T('Rotate clockwise'), None, 'rotate-clockwise'),
                (_T('Rotate anti-clockwise'), None, 'rotate-anticlockwise'),
                (_T('Mirror X axis'), 'X', 'mirror-x'),
                (_T('Mirror Y axis'), 'Y', 'mirror-y'),
                # (_T('Split horizontally'), None, 'split-viewport-horiz'),
                # (_T('Split vertically'), None, 'split-viewport-vert'),
                # (_T('Remove'), None, 'remove-viewport'),
            ),
            _T('Layers'): ((_T('Clear active'), 'K', 'clear_layer'),),
            _T('Color'): (
                (_T('Lighten of 10%'), None, 'color-lighten'),
                (_T('Darken of 10%'), None, 'color-darken'),
                (_T('Saturate of 10%'), None, 'color-saturate'),
                (_T('Desaturate of 10%'), None, 'color-desaturate'),
                # (_T('Assign Color Profile...'), None, lambda *a: self.cms_assign_win.OpenWindow()),
                # (_T('Convert to Color Profile...'), None, lambda *a: self.cms_conv_win.OpenWindow()),
            ),
            _T('Tools'): (
                (_T('Toggle line guide'), '1', 'toggle-line-guide'),
                (_T('Toggle ellipse guide'), '2', 'toggle-ellipse-guide'),
            ),
            _T('Windows'): (
                (_T('Document Information'), None, lambda evt: self.open_window('DocInfo')),
                (_T('Layers'), 'L', lambda evt: self.open_window('LayerMgr')),
                (_T('Color Harmonies'), 'C', lambda evt: self.open_window('ColorMgr')),
                (_T('Commands historic'), 'H', lambda evt: self.open_window('CmdHist')),
                (_T('Brush Editor'), 'B', lambda evt: self.open_window('BrushEditor')),
                (_T('Brush House'), None, lambda evt: self.open_window('BrushHouse')),
                (_T('Application Preferences'), 'P', lambda evt: self.open_window('Prefs')),
                (_T('Splash'), None, lambda evt: self.open_window('Splash')),
            ),
            _T('Debug'): ((_T('GC Collect'), None, lambda *a: self._do_gc_collect()),),
        }

        self.menu_items = {}
        menustrip = pymui.Menustrip()
        order = (
            _T('Application'),
            _T('Edit'),
            _T('View'),
            _T('Layers'),
            _T('Color'),
            _T('Tools'),
            _T('Windows'),
            _T('Debug'),
        )
        for k in order:
            v = menu_def[k]
            menu = pymui.Menu(k)
            menustrip.AddTail(menu)

            for t in v:
                if t is None:
                    menu.AddTail(pymui.Menuitem('-'))  # Separator
                    continue
                elif t[0][0] == '#':  # toggled item
                    title = t[0][1:]
                    item = pymui.Menuitem(title, t[1], Checkit=True)
                    item.title = title
                else:
                    item = pymui.Menuitem(t[0], t[1])
                if callable(t[2]):
                    item.Bind(*t[2:])
                self.menu_items[t[2]] = item
                menu.AddTail(item)

        return menustrip

    # Internal API
    #

    def _do_gc_collect(self):
        gc.set_debug(gc.DEBUG_LEAK)
        print("=> %u collected" % gc.collect())
        gc.set_debug(0)

    # Public API
    #
    # (Could be used by any other view components)
    #

    def run(self):
        # self.appprefwin.init_from_prefs()
        # self.appprefwin.apply_config()

        # Auto-open, usefull only if MUI remembers window position
        wins_to_open = prefs['pymui-window-open-at-startup']
        for name in wins_to_open:
            if name != 'splash':
                self.open_window(name)

        self.windows['Splash'].Open = 'splash' in wins_to_open
        self.Run()

    def get_filename(self, title, parent=None, read=True, pat='#?', **kwds):
        filename = pymui.GetFilename(
            parent, title, kwds.get('drawer', self._open_doc and os.path.dirname(self._open_doc)), pat, not read
        )
        if filename:
            self._open_doc = filename[0]
            return self._open_doc

    def get_image_filename(self, pat="#?.(png|jpeg|jpg|targa|tga|gif|ora)", *a, **k):
        return self.get_filename(_T("Select image to load"), pat=pat, *a, **k)

    def get_document_filename(self, pat="#?.(png|jpeg|jpg|targa|tga|gif|ora)", *a, **k):
        return self.get_filename(_T("Select document filename"), pat=pat, *a, **k)

    def get_new_document_type(self, alltypes, parent=None):
        return 'RGB'

    def open_window(self, name):
        self.windows[name].Open = True

    def toggle_window(self, name):
        self.windows[name].Open = not self.windows[name].Open.value

    def close_all_non_drawing_windows(self):
        for win in self.windows.values():
            win.Open = False

    def show_drawroot(self, root):
        if self.fullscreen:
            win = self.fullscreen_win
        else:
            win = FramedDocWindow()
            self.AddChild(win)
        win.contents = root
        root.show_splited()
        win.Open = True

    def toggle_fullscreen(self, framed_win):
        fsw = self.fullscreen_win

        if self.fullscreen:
            fsw.Open = False
            fsw.link.contents = fsw.set_contents()
            FramedDocWindow.open_all()
            fsw.link = None

        else:
            FramedDocWindow.open_all(False)
            fsw.link = framed_win
            fsw.contents = framed_win.set_contents()
            fsw.Open = True

    @property
    def fullscreen(self):
        return self.fullscreen_win.Open.value


class MyRoot(pymui.Group):
    _MCC_ = True

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
        self.WindowObject.object.CloseWindow()

    def __init__(self, *a, **k):
        super(MyRoot, self).__init__(Horiz=False, *a, **k)
        self._ev = pymui.EventHandler()


class Splash(pymui.Window):
    def __init__(self, name):
        super(Splash, self).__init__(
            ID=0,
            CloseOnReq=True,
            Borderless=True,
            DragBar=False,
            CloseGadget=False,
            SizeGadget=False,
            DepthGadget=False,
            Opacity=230,
            Position=('centered', 'centered'),
        )
        self.name = name

        # Special root group with window auto-close on any events
        root = MyRoot(Frame='None', Background='2:00000000,00000000,00000000', InnerSpacing=(0,) * 4)
        self.RootObject = root

        top_bar = pymui.HGroup(Frame='None', Background='5:PROGDIR:data/internal/splash_header.png')
        self.bottom_bar = bottom_bar = pymui.VGroup(Frame='None', InnerBottom=6)

        top_bar.AddChild(pymui.Dtpic('PROGDIR:data/internal/app_logo.png', InnerLeft=6, InnerRight=6))
        top_bar.AddChild(pymui.HSpace(0))
        top_bar.AddChild(
            pymui.Text(
                Frame='None',
                HorizWeight=0,
                PreParse=pymui.MUIX_C + pymui.MUIX_PH,
                Font=pymui.MUIV_Font_Tiny,
                Contents='v%.1f.%d\n%s' % (main.VERSION, main.BUILD, main.STATUS),
            )
        )

        # hg = pymui.HGroup(InnerLeft=6, InnerRight=6)
        # bottom_bar.AddChild(hg)

        # hg.AddChild(pymui.Text(Frame='None', InnerLeft=6,
        #                       SetMax=True, PreParse=pymui.MUIX_PH,
        #                       Contents=_T('Interaction')+':'))
        # cycle = pymui.Cycle(['User', 'Default'], HorizWeight=0)

        # hg.AddChild(cycle)
        # hg.AddChild(pymui.HSpace(0))

        recent_gp = pymui.VGroup(InnerLeft=6, InnerRight=6)
        bottom_bar.AddChild(recent_gp)

        self.lasts_bt = []
        if os.path.isfile(LASTS_FILENAME):
            recent_gp.AddChild(
                pymui.Text(
                    Frame='None',
                    InnerLeft=6,
                    InnerRight=6,
                    PreParse=pymui.MUIX_L + pymui.MUIX_PH,
                    Contents=_T('Recent') + ':',
                )
            )
            with open(LASTS_FILENAME) as fd:
                for i in range(5):
                    path = fd.readline()[:-1]
                    if path:
                        logo = pymui.Dtpic('SYS:Prefs/Presets/Deficons/image/default.info', Scale=32, InnerLeft=20)
                        text = pymui.Text(
                            Frame='None', PreParse=pymui.MUIX_PH, InputMode='RelVerify', Contents=os.path.basename(path)
                        )
                        text.path = path

                        hg = pymui.HGroup()
                        hg.AddChild(logo)
                        hg.AddChild(text)
                        recent_gp.AddChild(hg)

                        self.lasts_bt.append(text)

        bottom_bar.AddChild(pymui.HBar(1))

        bt = pymui.SimpleButton(_T('About'), Weight=0, InnerRight=6)
        bt.Notify('Pressed', lambda *a: pymui.GetApp().about.OpenWindow(), when=False)
        bottom_bar.AddChild(pymui.HGroup(Child=(pymui.HSpace(0), bt)))

        all_logos = glob.glob('data/internal/app_intro*.png')
        logo = pymui.Dtpic(random.choice(all_logos), Frame="Group")

        root.AddChild(top_bar)
        root.AddChild(logo)
        root.AddChild(bottom_bar)


class AboutWindow(pymui.Window):
    def __init__(self):
        super(AboutWindow, self).__init__(
            'GB3 - ' + _T('About'), ID=0, Position=('centered', 'centered'), CloseOnReq=True  # no position remembering
        )
        root = pymui.VGroup()
        self.RootObject = root

        top = pymui.HGroup()
        root.AddChild(top)

        root.AddChild(pymui.HBar(0))

        okbt = pymui.SimpleButton(_T('Ok'))
        okbt.Notify('Pressed', lambda *a: self.CloseWindow(), when=False)
        root.AddChild(pymui.HCenter(okbt))

        top.AddChild(pymui.Dtpic('PROGDIR:data/internal/app_logo.png', InnerLeft=6, InnerRight=6))
        top.AddChild(
            pymui.Text(
                about_msg.safe_substitute(
                    base=BASE,
                    description=DESCRIPTION,
                    version=main.VERSION,
                    build=main.BUILD,
                    date=main.DATE,
                    copyright=COPYRIGHT,
                ),
                Frame='Text',
            )
        )
