
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

import document
from utils import _T

__all__ = [ 'DocumentConfigVO', 'FileDocumentConfigVO',
            'EmptyDocumentConfigVO', 'LayerConfigVO',
            'LayerCommandVO' ]

class GenericVO(dict):
    def __getattribute__(self, name):
        try:
            return self[name]
        except KeyError:
            return dict.__getattribute__(self, name)

    def __setattr__(self, name, value):
        if name in self.__dict__:
            return dict.__setattr__(self, name, value)
        else:
            self[name] = value


class DocumentConfigVO(GenericVO):
    """
    Instance of this class is used to communicate document
    configuration when system needs to create a new docucment.
    """

    def __init__(self, name='', **k):
        super(DocumentConfigVO, self).__init__(name=name, **k)


class FileDocumentConfigVO(DocumentConfigVO):
    def __init__(self, filename, docproxy=None, **k):
        super(FileDocumentConfigVO, self).__init__(filename,
                                                   docproxy=docproxy,
                                                   **k)


class EmptyDocumentConfigVO(DocumentConfigVO):
    def __init__(self, colorspace='RGB', **k):
        super(EmptyDocumentConfigVO, self).__init__(colorspace=colorspace, **k)


class LayerCmdVO(GenericVO):
    def __init__(self, layer, **k):
        super(LayerCmdVO, self).__init__(layer=layer, **k)
