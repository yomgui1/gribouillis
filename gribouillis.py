#!python
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

if __name__ == '__main__':
    import sys, os, shutil

    sys.setrecursionlimit(100)
    sys.path.append('libs')
    
    import main
    
    # XXX: change me before any public release
    main.version_str = "$VER: Gribouillis 3.0.0 (dd.mm.yyyy) Guillaume Roguez"
    
    data = main.version_str.split()
    main.VERSION = float('.'.join(data[2].split('.')[:2]))
    main.BUILD = int(data[2].split('.')[-1])
    main.DATE = data[3][1:-1]
    del data
    
    import view
    
    # Creating the application and run it
    app = view.app = view.Application()
    
    gribouillis = main.Gribouillis(os.getcwd())
    gribouillis.sendNotification(main.Gribouillis.STARTUP, app)
    app.run()
