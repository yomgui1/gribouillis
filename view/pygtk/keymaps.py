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

from view.keymap import Keymap


RALT_MASK = 'mod5-mask'
LALT_MASK = 'mod1-mask'

AND = lambda *a: "(%s) and (%s)" % a
OR = lambda *a: "(%s) or (%s)" % a
KEY_PRESS_VAL = lambda k: "(evt.type.value_nick=='key-press') and (evt.keyval==%u)" % k
KEY_RELEASE_VAL = lambda k: "(evt.type.value_nick=='key-release') and (evt.keyval==%u)" % k
cursor_enter = "evt.type.value_nick=='enter-notify'"
cursor_leave = "evt.type.value_nick=='leave-notify'"
cursor_motion = "evt.type.value_nick=='motion-notify'"
scroll_up = "(evt.type.value_nick=='scroll') and (evt.direction.value_nick=='up')"
scroll_down = "(evt.type.value_nick=='scroll') and (evt.direction.value_nick=='down')"
button_press = "evt.type.value_nick=='button-press'"
button_release = "evt.type.value_nick=='button-release'"
button1 = "evt.button==1"
button2 = "evt.button==2"
button3 = "evt.button==3"
button1_mod = "'button1-mask' in evt.state.value_nicks"
button2_mod = "'button2-mask' in evt.state.value_nicks"
button3_mod = "'button3-mask' in evt.state.value_nicks"
button1_mod_ex = "['button1-mask'] == evt.state.value_nicks"
button2_mod_ex = "['button2-mask'] == evt.state.value_nicks"
button3_mod_ex = "['button3-mask'] == evt.state.value_nicks"
ctrl_mod = "'control-mask' in evt.state.value_nicks"


Keymap('DocWindow', {
        AND(KEY_RELEASE_VAL(ord('z')), ctrl_mod): 'hist_undo', # ctrl-z
        })

Keymap('Viewport', {
        # View motions
        AND(button_press, button2): 'vp_scroll_start',
        scroll_down: 'vp_scale_down',
        scroll_up: 'vp_scale_up',

        # Cursor related
        cursor_enter: 'vp_enter',
        cursor_leave: 'vp_leave',
        cursor_motion: 'vp_move_cursor',

        # Drawing
        AND(button_press, button1): 'vp_stroke_start',
        KEY_RELEASE_VAL(ord(' ')): 'vp_clear_layer', # space
        })

Keymap('Brush-Stroke', {
        AND(cursor_motion, button1_mod): 'vp_stroke_append',
        AND(button_release, button1): 'vp_stroke_confirm',
       })

Keymap('Viewport-Scroll', {
        AND(cursor_motion, button2_mod): 'vp_scroll_delta',
        AND(button_release, button2): 'vp_scroll_confirm',
       })

'''
KeymapManager.register_keymap("Viewport", {
        # View motions
        "key-press-bracketright": ("vp_rotate_right", None),
        "key-press-bracketleft": ("vp_rotate_left", None),
        "key-press-x": "vp_swap_x",
        "key-press-y": "vp_swap_y",
        "key-press-equal": "vp_reset_all",
        "key-press-plus": ("vp_reset_rotation", None),
        "key-press-Left": "vp_scroll_left",
        "key-press-Right": "vp_scroll_right",
        "key-press-Up": "vp_scroll_up",
        "key-press-Down": "vp_scroll_down",
        "key-press-b": ("open_brush_editor", None),

        # Layer operators
        "key-press-plus": ("vp_insert_layer", ["shift-mask", "control-mask"])
        })
'''


