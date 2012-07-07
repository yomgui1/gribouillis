###############################################################################
# Copyright (c) 2009-2011 Guillaume Roguez
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

import _lcms

from model import prefs
from utils import _T

__all__ = [ 'Profile', 'Transform', 'INTENTS' ]

INTENTS = { _T("Perceptual"):            _lcms.INTENT_PERCEPTUAL,
            _T("Relative Colorimetric"): _lcms.INTENT_RELATIVE_COLORIMETRIC,
            _T("Saturation"):            _lcms.INTENT_SATURATION,
            _T("Absolute Colorimetric"): _lcms.INTENT_ABSOLUTE_COLORIMETRIC,
          }

class Profile(_lcms.Profile):
    __all = []

    @classmethod
    def iter_all(cls):
        return iter(cls.__all)

    @classmethod
    def get_all(cls):
        return tuple(cls.__all)

    @classmethod
    def add_file(cls, filename):
        p = cls(filename)
        cls.__all.append(p)
        return p

    def __str__(self):
        if len(self.Description) > 50:
            return self.Description[:50]+' (...)'
        else:
            return self.Description

    def __repr__(self):
        return self.Description

class Transform(_lcms.Transform):
    def __new__(cl, src_profile, dst_profile,
                 src_type=_lcms.TYPE_ARGB_8, dst_type=_lcms.TYPE_ARGB_8,
                 intent=_lcms.INTENT_ABSOLUTE_COLORIMETRIC, flags=0):
        return super(Transform, cl).__new__(cl,
                                            src_profile, src_type,
                                            dst_profile, dst_type,
                                            intent, flags)

    def __call__(self, src, dst):
        assert src.size == dst.size
        super(Transform, self).__call__(src, dst, src.width * src.height)


if not Profile.get_all():
    import os, main, glob

    for filename in glob.glob(os.path.join(prefs['profiles-path'], '*.icc')):
        Profile.add_file(filename)

