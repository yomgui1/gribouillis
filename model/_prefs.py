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

# 2.5 only


import os
import main

from xml.etree import ElementTree as ET
from utils import _T


class Preferences(dict):
    DEFAULTS = {
        'bindings': {},
        'data-path': 'data',
        'profiles-path': '${data-path}/profiles',
        'backgrounds-path': '${data-path}/backgrounds',
        'view-icons-path': '${data-path}/icons/highlander',
        'view-metrics-unit': 'dpi',
        'view-metrics-x': 96,
        'view-metrics-y': 96,
        'view-color-bg': (0.8, 0.8, 0.9, 0.7),
        'view-color-text': (0.0, 0.0, 0.0, 1.0),
        'view-color-ol': (0.4, 0.6, 0.9, 0.9),
        'view-color-wheel-bg': (0, 0, 0, 0.35),
        'view-color-wheel-ol': (1, 1, 1, 0.80),
        'view-color-wheel-sel': (1, 0, 0, 0.80),
        'view-color-handler-bg': (0.9, 0.9, 1.0, 0.8),
        'view-color-handler-ol': (0.0, 0.2, 0.4, 0.8),
    }

    def __init__(self):
        dict.__init__(self)
        self.handlers = {}
        self.set_to_defaults()

    def add_default(self, key, value):
        Preferences.DEFAULTS.setdefault(key, value)
        self.setdefault(key, value)

    def register_tag_handler(self, tag, handler):
        self.handlers[tag] = handler

    def set_to_defaults(self):
        self.clear()
        self.update(Preferences.DEFAULTS)

    def load(self, filename=None, alternative='data/internal/config_default.xml'):
        if not (filename and os.path.isfile(filename)) and alternative is not None:
            filename = alternative

        faulty_elmt = []

        with open(filename, 'r') as fd:
            config = ET.fromstring(fd.read())
            self['version'] = float(config.get('version', 0))
            for element in config:
                handler = self.handlers.get(element.tag)
                if handler:
                    try:
                        handler.parse(self, element)
                    except:
                        pass  # faulty_elmt.append(str(element))

        if faulty_elmt:
            raise KeyError(_T("Following elements causes errors:%s)") % '\n'.join(faulty_elmt))

    def save_preferences(self, filename):
        with open(filename, 'w') as fd:
            config = ET.Element('config', {}, version=str(main.VERSION))

            for tag, handler in self.handlers.items():
                element = ET.Element(tag)
                try:
                    handler.save(self, element)
                    if element.attrib or len(element) > 0:
                        config.append(element)
                except:
                    pass  # silent errors

            # Write XML tree as file
            xml = ET.tostring(config, encoding='UTF-8')
            fd.write(xml)


prefs = Preferences()


class IPrefHandler:
    def parse(self, prefs, element):
        """parse(prefs, element) -> None

        This function should parse ElemenTree object 'element' data and modify
        accordingly the preference dictionnary 'prefs'.
        """
        pass

    def save(self, prefs, root):
        """save(prefs, root) -> dict

        Function should setup and add SubElement to the given root element,
        using data from prefs.
        """
        pass
