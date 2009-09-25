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

class BaseLanguage:
    AppliDescription       = "Simple Painting program for MorphOS"
    DrawWinTitle           = "Draw Area"
    ColorChooserWinTitle   = "Color Selection"
    BrushSelectWinTitle    = "Brush Selection"
    CMSWinTitle            = "Color Management Profiles Preferences"
    DataWinTitle           = "Project Preferences"
    MenuProject            = "Project"
    MenuProjectLoadImage   = "Load Image..."
    MenuProjectSaveImage   = "Save Image..."
    MenuProjectSetupData   = "Setup data..."
    MenuProjectQuit        = "Quit"
    MenuEdit               = "Edit"
    MenuEditClearAll       = "Clear all"
    MenuEditUndo           = "Undo"
    MenuEditRedo           = "Redo"
    MenuView               = "View"
    MenuViewIncreaseZoom   = "Increase Zoom"
    MenuViewDecreaseZoom   = "Decrease Zoom"
    MenuViewResetZoom      = "Reset Zoom"
    MenuViewSetCMSProfile  = "Set CMS Profiles..."
    MenuViewFullscreen     = "Fullscreen"
    MenuWindows            = "Windows"
    MenuWindowDraw         = "Draw Surface"
    MenuWindowColorChooser = "Color Chooser"
    MenuWindowBrushSel     = "Brush Selection"
    MenuWindowMiniBGSel    = "Mini Background Selection"
    MenuDebug              = "Debug"
    MenuDegugRaster        = "Raster"
    LoadImageReqTitle      = "Select image to load"
    SaveImageReqTitle      = "Select a filename to save your image"
    
# BEGIN - LANGUAGES

# To add a new language support, don't make a copy yourself.
# Create a new class like this:
#
# class MyLanguage(BaseLanguage):
#    string_to_stranslate = "New string in my language"
#    ...
#
# Then append a new entry in dict 'lang_dict' at the end of this file
#

class English(BaseLanguage):
    pass # nothing to translate as it's the default language

# END - LANGUAGES

lang_dict = {
    'default': English, # TODO: shall be changed at startup
    'english': English,
    }

__all__ = ('lang_dict', )
