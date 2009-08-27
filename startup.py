import os
from application import Application

def start():
    return Application(os.getcwd())
