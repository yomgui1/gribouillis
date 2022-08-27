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

IECODE_UP_PREFIX = 0x80
IECODE_LBUTTON = 0x68
IECODE_RBUTTON = 0x69
IECODE_MBUTTON = 0x6A

IEQUALIFIER_LSHIFT = 0x0001
IEQUALIFIER_RSHIFT = 0x0002
IEQUALIFIER_CAPSLOCK = 0x0004
IEQUALIFIER_CONTROL = 0x0008
IEQUALIFIER_LALT = 0x0010
IEQUALIFIER_RALT = 0x0020
IEQUALIFIER_LCOMMAND = 0x0040
IEQUALIFIER_RCOMMAND = 0x0080
IEQUALIFIER_REPEAT = 0x0200

IEQUALIFIER_SHIFT = IEQUALIFIER_LSHIFT | IEQUALIFIER_RSHIFT

ALL_QUALIFIERS = IEQUALIFIER_LSHIFT | IEQUALIFIER_RSHIFT | IEQUALIFIER_CONTROL
ALL_QUALIFIERS |= IEQUALIFIER_LALT | IEQUALIFIER_RALT | IEQUALIFIER_LCOMMAND
ALL_QUALIFIERS |= IEQUALIFIER_RCOMMAND

NM_WHEEL_UP = 0x7A
NM_WHEEL_DOWN = 0x7B
TABLET_PAD_BTN00 = 0x4000

TABLETA_ToolType = pymui.TABLETA_Dummy + 20
TABLETA_StripX = pymui.TABLETA_Dummy + 24
TABLETA_StripY = pymui.TABLETA_Dummy + 25
TABLETA_StripXMax = pymui.TABLETA_Dummy + 26
TABLETA_StripYMax = pymui.TABLETA_Dummy + 27

TABLET_TOOLTYPE_UNKNOWN = 0
TABLET_TOOLTYPE_MOUSE = 1
TABLET_TOOLTYPE_STYLUS = 2
TABLET_TOOLTYPE_ERASER = 3
TABLET_TOOLTYPE_AIRBRUSH = 4
TABLET_TOOLTYPE_TOUCH = 5
TABLET_TOOLTYPE_PAD = 6
