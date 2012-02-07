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

from __future__ import with_statement

import os
from xml.etree import ElementTree as ET

import main

__all__ = [ 'prefs',
            'defaults',
            'reg_pref_handler',
            'load_preferences',
            'save_preferences',
            'PrefHandlerInterface',
            'set_to_defaults',
            'load_defaults',
            ]

defaults = {
    'bindings': {},
    'data-path': 'data',
    'profiles-path': '${data-path}/profiles',
    'backgrounds-path': '${data-path}/backgrounds',
    'view-icons-path': '${data-path}/icons/highlander',
    'view-metrics-unit': 'dpi',
    'view-metrics-x': 96,
    'view-metrics-y': 96,
    'view-color-bg': (.8, .8, .9,  .7),
    'view-color-text': (.0, .0, .0, 1.0),
    'view-color-ol': (.4, .6, .9,  .9),
    'view-color-wheel-bg': (0, 0, 0, .35),
    'view-color-wheel-ol': (1, 1, 1, .80),
    'view-color-wheel-sel': (1, 0, 0, .80),
    'view-color-handler-bg': (.9, .9, 1.0, .8),
    'view-color-handler-ol': (.0, .2,  .4, .8),
}

prefs = {}

_hdl_dict = {}

def reg_pref_handler(tag, handler):
    _hdl_dict[tag] = handler
    
def set_to_defaults():
    global prefs
    prefs = defaults.copy()
    
set_to_defaults()

def load_preferences(filename=None, alternative='data/internal/config_default.xml'):
    if not (filename and os.path.isfile(filename)) and alternative is not None:
        filename = alternative
        
    with open(filename, 'r') as fd:
        config = ET.fromstring(fd.read())
        prefs['version'] = v = float(config.get('version', 0))
        for element in config:
            if element.tag in _hdl_dict:
                handler = _hdl_dict[element.tag]
                try:
                    handler.parse(prefs, element)
                except:
                    raise
                        
def load_defaults(): load_preferences()

load_defaults()

def save_preferences(filename):
    with open(filename, 'w') as fd:
        config = ET.Element('config', {}, version=str(main.VERSION))
        
        for tag, handler in _hdl_dict.iteritems():
            element = ET.Element(tag)
            handler.save_data(prefs, element)
            if  element.attrib or len(element) > 0:
                config.append(element)

        # Write XML tree as file
        xml = ET.tostring(config, encoding='UTF-8')
        fd.write(xml)
        
class PrefHandlerInterface:
    def parse(self, prefs, element):
        """parse(prefs, element) -> None
        
        This function should parse ElemenTree object 'element' data and modify
        accordingly the preference dictionnary 'prefs'.
        """
        pass
        
    def save_data(self, prefs, root):
        """save_data(prefs, root) -> dict
        
        Function should setup and add SubElement to the given root element,
        using data from prefs.
        Should return True if any data need to be saved.
        """
        pass