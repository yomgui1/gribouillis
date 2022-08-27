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

import cairo
import math
import random

from math import floor, ceil

import main

from model import _pixbuf, _cutils, prefs, surface
from utils import virtualmethod, resolve_path


SCALES = [
    1 / 20.0,
    1 / 10.0,
    1 / 6.0,
    1 / 5.0,
    1 / 4.0,
    1 / 3.0,
    1 / 2.0,
    1.0,
    4 / 3.0,
    2.0,
    3.0,
    4.0,
    5.0,
    6.0,
    10.0,
    20.0,
]
SCALES.reverse()

MAX_SCALE = len(SCALES) - 1


class ViewState(object):
    """Class to store and manipulate how a document is
    represented into an euclidian space.
    This class doesn't manipulate the document property,
    just a "state" used later by a Render instance.
    """

    # States = how a model point is transformed to be displayed
    _tx = _ty = 0.0  # translation factor
    _scale_idx = 0  # scaling factor
    _mox = _moy = 0.0  # mirror center
    _mx = _my = 1.0  # mirror factor
    _rot = 0.0  # rotation angle (radians)
    _rx = _ry = 0.0  # rotation center

    # Generated matrices from states
    _m2v_mat = None  # model to view matrix
    _v2m_mat = None  # view to model matrix
    _rot_mat = None  # rotation matrix
    _rot_imat = None  # invert of _rot_mat
    _mirror_mat = None  # mirror matrix
    _mirror_imat = None  # invert of _mirror_mat
    _w = 0
    _h = 0

    __STATES = "_tx _ty _mox _moy _mx _my _scale_idx _rot _rx _ry".split()

    def __init__(self):
        self.reset()
        self._update_matrices()  # for aliases

    def _gen_rot_mat(self):
        _ = self._mirror_imat * cairo.Matrix(x0=self._rx, y0=self._ry)
        _.rotate(self._rot)
        _.translate(-self._rx, -self._ry)
        _ = self._mirror_mat * _
        self._rot_mat = _
        _ = cairo.Matrix(*_)
        _.invert()
        self._rot_imat = _

    def _gen_mirror_mat(self):
        self._mirror_mat = cairo.Matrix(
            self._mx, 0, 0, self._my, self._mox * (1 - self._mx), self._moy * (1 - self._my)
        )
        self._mirror_imat = cairo.Matrix(self._mirror_mat)
        self._mirror_imat.invert()

    def _update_matrices(self):
        _ = SCALES[self._scale_idx]
        self._m2v_mat = cairo.Matrix(_, 0, 0, _, self._tx, self._ty)
        if self._rot:
            if not self._rot_mat:
                self._gen_rot_mat()
            self._m2v_mat *= self._rot_mat
        if self._mx < 0 or self._my < 0:
            if not self._mirror_mat:
                self._gen_mirror_mat()
            self._m2v_mat *= self._mirror_mat
        self._v2m_mat = cairo.Matrix(*self._m2v_mat)
        self._v2m_mat.invert()

        # Update aliases
        self.get_view_point = self._m2v_mat.transform_point
        self.get_view_distance = self._m2v_mat.transform_distance
        self.get_model_point = self._v2m_mat.transform_point
        self.get_model_distance = self._v2m_mat.transform_distance

    def like(self, other):
        "Copy viewing properties from an other ViewState instance"

        assert isinstance(other, ViewState)
        for name in ViewState.__STATES:
            setattr(self, name, getattr(other, name))
        self._rot_mat = None
        self._mirror_mat = None
        self._update_matrices()

    def set_size(self, width, height):
        width = int(width)
        height = int(height)
        assert width > 0 and height > 0

        self._w = width
        self._h = height
        self._rx = width / 2.0
        self._ry = height / 2.0

    def reset(self):
        return self.reset_translation() or self.reset_scale() or self.reset_rotation() or self.reset_mirror()

    def reset_translation(self):
        _ = self._tx or self._ty
        self._tx = self._ty = 0.0
        if _:
            self._m2v_mat = None
            return True

    def reset_scale(self):
        _ = self._scale_idx
        self._scale_idx = SCALES.index(1.0)
        if _ != self._scale_idx:
            self._m2v_mat = None
            return True

    def reset_mirror(self):
        _ = self._mox or self._moy or self._mx or self._my
        self._sox = self._soy = 0.0
        self._mx = self._my = 1.0
        if _:
            self._m2v_mat = None
            return True

    def reset_rotation(self, angle=0):
        _ = self._rot
        self._rot = angle % 360
        self._rot_mat = self._rot_imat = None
        if _ != self._rot:
            self._m2v_mat = None
            return True

    def scroll(self, x, y):
        if x or y:
            # we multiply by mirror coeffiscient to get the right direction
            x *= self._mx
            y *= self._my
            if self._rot_imat:
                x, y = self._rot_imat.transform_distance(x, y)
            self._tx += x
            self._ty += y
            self._m2v_mat = None
            return True

    def scale_up(self):
        if self._scale_idx < MAX_SCALE:
            self._scale_idx += 1
            self._m2v_mat = None
            return True

    def scale_down(self):
        if self._scale_idx > 0:
            self._scale_idx -= 1
            self._m2v_mat = None
            return True

    def mirror_x(self, x=0.0):
        self._mox = x
        self._mx = -self._mx
        self._m2v_mat = None
        return True

    def mirror_y(self, y=0.0):
        self._moy = y
        self._my = -self._my
        self._m2v_mat = None
        return True

    def rotate(self, angle):
        angle %= 360
        if angle:
            self._rot = (self._rot + angle) % 360
            self._mat = None
            return True

    @property
    def view_matrix(self):
        if self._m2v_mat is None:
            self._update_matrices()
        return self._m2v_mat

    @property
    def model_matrix(self):
        if self._m2v_mat is None:
            self._update_matrices()
        return self._v2m_mat

    def get_view_point_pos(self, pos):
        return self.get_view_point(*pos)

    def get_view_area(self, *area):
        """Transform a given area from model to view coordinates.
        This function uses the full matrix coefficients.

        WARNING: returns integer area values, not clipped
        on viewport bounds (possible negative values!).
        """
        return _cutils.Area(*area).transform_in(self.get_view_point)

    def get_offset(self):
        return self._tx, self._ty

    def set_offset(self, offset):
        self._tx, self._ty = offset

    offset = property(get_offset, set_offset)

    @property
    def scale_factor(self):
        return SCALES[self._scale_idx]

    @property
    def scale_idx(self):
        pass

    offset = property(get_offset, set_offset)


prefs.add_default('view-filter-threshold', 7)
prefs.add_default('view-color-passepartout', (0.33, 0.33, 0.33, 1.0))
