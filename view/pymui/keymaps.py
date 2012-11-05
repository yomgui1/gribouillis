###############################################################################
# Copyright (c) 2009-2012 Guillaume Roguez
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

from view.keymap import KeymapManager

KeymapManager.register_keymap("Viewport", {
        # UI
        "f-press": "toggle_fullscreen",
        
        # Brush related
        "cursor-enter": "vp_enter",
        "cursor-leave": "vp_leave",
        "cursor-motion": "vp_move_cursor",

        # Drawing
        "mouse_left-press": "vp_stroke_start",
        "backspace-press": "vp_clear_layer",

        # View motions
        "mouse_middle-press": "vp_scroll_start",
        "wheel_down-press": "scale_down_at_cursor",
        "wheel_up-press": "scale_up_at_cursor",
        "bracketright-press": ("vp_rotate_right", None),
        "bracketleft-press": ("vp_rotate_left", None),
        "x-press": "vp_swap_x",
        "y-press": "vp_swap_y",
        "equal-press": "vp_reset_all",
        "plus-press": ("vp_reset_rotation", None),
        "Left-press": "vp_scroll_left",
        "Right-press": "vp_scroll_right",
        "Up-press": "vp_scroll_up",
        "Down-press": "vp_scroll_down",
        })

KeymapManager.register_keymap("Stroke", {
        "cursor-motion": "vp_stroke_append",
        "mouse_left-release": "vp_stroke_confirm",
        })
        
KeymapManager.register_keymap("Scroll", {
        "cursor-motion": "vp_scroll_on_motion",
        "mouse_middle-release": "vp_scroll_confirm",
        "esc-press": "vp_scroll_cancel",
        "mouse_left-press": "vp_scroll_cancel",
        "mouse_right-press": "vp_scroll_cancel",
        "space-press": "vp_scroll_cancel",
        })
