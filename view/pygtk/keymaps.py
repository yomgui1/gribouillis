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

from gi.repository.IBus import keyval_from_name
from view.keymap import Keymap

RALT_MASK = 'mod5-mask'
LALT_MASK = 'mod1-mask'

AND = lambda *a: "(%s) and (%s)" % a
OR = lambda *a: "(%s) or (%s)" % a
KEY_PRESS_VAL = lambda k: "(evt_type=='key-press') and (evt.keyval==%u)" % k
KEY_RELEASE_VAL = lambda k: "(evt_type=='key-release') and (evt.keyval==%u)" % k
KEY_PRESS_NAME = lambda s: KEY_PRESS_VAL(keyval_from_name(s))
KEY_RELEASE_NAME = lambda s: KEY_RELEASE_VAL(keyval_from_name(s))

cursor_enter = "evt_type=='enter-notify'"
cursor_leave = "evt_type=='leave-notify'"
cursor_motion = "evt_type=='motion-notify'"
scroll_up = "(evt_type=='scroll') and (evt.direction.value_nick=='up')"
scroll_down = "(evt_type=='scroll') and (evt.direction.value_nick=='down')"
button_press = "evt_type=='button-press'"
button_release = "evt_type=='button-release'"
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
shift_mod = "'shift-mask' in evt.state.value_nicks"


Keymap('Application', {
    AND(KEY_RELEASE_VAL(ord('z')), ctrl_mod): 'hist_undo(ctx, event)', # ctrl-z
    AND(KEY_RELEASE_VAL(ord('y')), AND(ctrl_mod, shift_mod)): 'hist_redo(ctx, event)', # ctrl-shift-z
})

Keymap('Viewport', {
    # View motions/transforms
    AND(button_press, button2): 'vp_scroll_start(ctx, event)',
    scroll_down: 'vp_scale_down(ctx, event)',
    scroll_up: 'vp_scale_up(ctx, event)',
    KEY_PRESS_NAME('Left'): 'vp_scroll_left(ctx)',
    KEY_PRESS_NAME('Right'): 'vp_scroll_right(ctx)',
    KEY_PRESS_NAME('Up'): 'vp_scroll_up(ctx)',
    KEY_PRESS_NAME('Down'): 'vp_scroll_down(ctx)',
    KEY_PRESS_NAME('x'): 'vp_swap_x(ctx)',
    KEY_PRESS_NAME('y'): 'vp_swap_y(ctx)',
    KEY_PRESS_NAME('equal'): 'vp_reset_all(ctx)',

    # Cursor related
    cursor_enter: 'vp_enter(ctx)',
    cursor_leave: 'vp_leave(ctx)',
    cursor_motion: 'vp_move_cursor(ctx, event)',

    # Drawing
    AND(button_press, button1): 'vp_stroke_start(ctx, event)',
    KEY_RELEASE_VAL(ord(' ')): 'vp_clear_layer(ctx)', # space
})

Keymap('Brush-Stroke', {
    AND(cursor_motion, button1_mod): 'vp_stroke_append(ctx, event)',
    AND(button_release, button1): 'vp_stroke_confirm(ctx, event)',
})

Keymap('Viewport-Scroll', {
    AND(cursor_motion, button2_mod): 'vp_scroll_delta(ctx, event)',
    AND(button_release, button2): 'vp_scroll_confirm(ctx, event)',
})
