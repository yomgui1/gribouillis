import os
from application import Application

app = None

def start():
    global app
    app = Application(os.getcwd())
    return app
