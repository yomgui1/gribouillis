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

from math import exp


class DeviceState(object):
    __slots__ = "cpos vpos spos pressure xtilt ytilt angle time".split()

    ## cpos = (x, y) is device position in view coordinates
    ## vpos = like cpos but after possible filtering
    ## spos = (sx, sy) is device position in document coordinates

    def __repr__(self):
        return "(%d, %d)" % self.cpos


class InputDevice(object):
    """InputDevice()

    - Store raw events from the input device, used by the program, like motion and pressure.
    - Apply filters to modify the response curve of these inputs.
    """

    def __init__(self):
        self.previous = None
        self.current = None

    def add_state(self, state):
        self.previous = self.current
        self.current = state

    @property
    def view_motion(self):
        return [a - b for a, b in zip(self.current.vpos, self.previous.vpos)]

    @property
    def delta_time(self):
        return self.current.time - self.previous.time
