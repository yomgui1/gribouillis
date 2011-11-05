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

import gtk, gobject

from model.profile import Profile
from utils import _T

__all__ = [ 'AssignCMSDialog', 'ConvertDialog' ]

class AssignCMSDialog(gtk.Dialog):
    def __init__(self, docproxy, parent=None):
        super(AssignCMSDialog, self).__init__(_T("Assign Profile"), parent,
                                              gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                                              (gtk.STOCK_OK, gtk.RESPONSE_OK,
                                               gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL))

        self._bt = []
        self._current = docproxy.profile
        self._profiles = Profile.get_all()
        
        frame = gtk.Frame(_T("Assign Profile")+':')
        self.vbox.pack_start(frame, False, False)

        vbox = gtk.VBox()
        frame.add(vbox)

        # Nothing
        bt1 = gtk.RadioButton(None, _T("No color management on this document"))
        self._bt.append(bt1)
        vbox.pack_start(bt1, False, False)

        # Current
        if docproxy.profile:
            bt2 = gtk.RadioButton(bt1, _T("Working")+': %s' % docproxy.profile)
            bt2.set_active()
            self._bt.append(bt2)
            vbox.pack_start(bt2, False, False)
        else:
            self._bt.append(None)

        # New one
        bt3 = gtk.RadioButton(bt1, _T("Profile")+': ')
        self._bt.append(bt3)

        cb = gtk.combo_box_new_text()
        for profile in self._profiles:
            cb.append_text(str(profile))
        cb.set_active(0)
        self._cb = cb

        hbox = gtk.HBox()
        hbox.pack_start(bt3, False, False)
        hbox.pack_start(cb)

        vbox.pack_start(hbox, False, False)
        
        self.show_all()

    def get_profile(self):
        for i, bt in enumerate(self._bt):
            if bt and bt.get_active():
                if i == 0:
                    return None
                elif i == 1:
                    return self._current
                else:
                    return self._profiles[self._cb.get_active()]


class ConvertDialog(gtk.Dialog):
    def __init__(self, docproxy, parent=None):
        super(ConvertDialog, self).__init__(_T("Convert to Profile"), parent,
                                              gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                                              (gtk.STOCK_OK, gtk.RESPONSE_OK,
                                               gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL))

        self._profiles = Profile.get_all()
        
        frame = gtk.Frame(_T("Source")+':')
        self.vbox.pack_start(frame, False, False)

        hbox = gtk.HBox()
        frame.add(hbox)

        label = gtk.Label(_T("Profile")+': %s' % docproxy.profile)
        label.set_justify(gtk.JUSTIFY_LEFT)
        hbox.pack_start(label, False, False)

        frame = gtk.Frame(_T("Destination")+':')
        self.vbox.pack_start(frame, False, False)

        self._dest = cb = gtk.combo_box_new_text()
        for profile in self._profiles:
            cb.append_text(str(profile))
        cb.set_active(0)

        hbox = gtk.HBox()
        frame.add(hbox)

        hbox.pack_start(gtk.Label(_T("Profile")+': '), False, False)
        hbox.pack_start(cb, False, False)

        frame = gtk.Frame(_T("Options")+':')
        self.vbox.pack_start(frame, False, False)

        vbox = gtk.VBox()
        frame.add(vbox)

        cb = gtk.combo_box_new_text()
        cb.append_text(_T("Perceptual"))
        cb.append_text(_T("Relative Colorimetric"))
        cb.append_text(_T("Saturation"))
        cb.append_text(_T("Absolute Colorimetric"))
        cb.set_active(0)

        hbox = gtk.HBox()
        vbox.pack_start(hbox)

        hbox.pack_start(gtk.Label(_T("Intent")+': '), False, False)
        hbox.pack_start(cb, False, False)

        bt1 = gtk.CheckButton(_T("Use Black Point Compensation")+': ')
        bt2 = gtk.CheckButton(_T("Use Dither")+': ')
        bt3 = gtk.CheckButton(_T("Flatten Image")+': ')
        if len(docproxy.document.layers) == 1:
            bt3.set_sensitive(False)

        vbox.pack_start(bt1)
        vbox.pack_start(bt2)
        vbox.pack_start(bt3)

        self.show_all()

    def get_destination(self):
        return self._profiles[self._dest.get_active()]
