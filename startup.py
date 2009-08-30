print dir()

import os
from application import App

def start():
    app = App(os.getcwd())
    app.mainloop()
