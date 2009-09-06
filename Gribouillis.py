#!/usr/bin/env python

import os
from application import Gribouillis

app = Gribouillis(os.getcwd())
app.Run()
del app # better!
