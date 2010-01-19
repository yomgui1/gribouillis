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

__all__ = [ 'DrawWindow' ]

from pymui import *

POINTERTYPE_NORMAL = 0
POINTERTYPE_AIMING = 6

class DrawWindow(Window):
    def __init__(self, title, raster, fullscreen=False):
        self.fullscreen = fullscreen
        kwds = {}
        if fullscreen:
            kwds['WidthScreen'] = 100
            kwds['HeightScreen'] = 100
            kwds['Borderless'] = True
            kwds['Backdrop'] = True
            #kwds['ID'] = 'DRWF'
            # Note: if I use the same ID for each FS mode, the FS window will take data
            # of the non FS window... that's render very bad ;-)
        else:
            kwds['Width'] = 800
            kwds['Height'] = 600
            kwds['LeftEdge'] = 64
            kwds['TopEdge'] = 64
            kwds['ID'] = 'DRW0'

        super(DrawWindow, self).__init__(title,
                                         RootObject=raster,
                                         TabletMessages=True, # enable tablet events support
                                         **kwds)

        self.Notify('Activate', MUIV_EveryTime, self.OnActivate)

    def OnActivate(self, evt):
        if evt.value:
            self.pointer = POINTERTYPE_AIMING
        else:
            self.pointer = POINTERTYPE_NORMAL
