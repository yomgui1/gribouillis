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

import os
from functools import wraps
from time import time

import puremvc.interfaces
import puremvc.patterns.mediator
import puremvc.patterns.proxy
import puremvc.patterns.command

__all__ = [ 'VirtualCalledError', 'virtualmethod',
            'Mediator', 'UndoableCommand', 'mvcHandler',
            'MetaSingleton', 'idle_cb', '_T', 'delayedmethod' ]

idle_cb = lambda *a, **k: None

def _T(s):
    # TODO: auto translation function
    return s

class VirtualCalledError(SyntaxError):
    def __init__(self, instance, func):
        self.__cls_name = instance.__class__.__name__
        self.__func_name = func.__name__

    def __str__(self):
        return "class %s doesn't implement virtual method %s" % (self.__cls_name, self.__func_name)


def virtualmethod(wrapped_func):
    @wraps(wrapped_func)
    def wrapper(self, *args, **kwds):
        raise VirtualCalledError(self, wrapped_func)
    return wrapper


def delayedmethod(delay):
    def wrapper(func):
        func.__delay = delay
        func.__lastcall = 0.
        @wraps(func)
        def _func(*a, **k):
            t = time()
            if t-func.__lastcall >= func.__delay:
                func.__lastcall = t
                return func(*a, **k)
        return _func
    return wrapper


class MetaMediator(type):
    def __new__(metacls, name, bases, dct):
        d = {}
        dct['__mvc_handlers'] = d
        for v in dct.itervalues():
            if hasattr(v, '_mvc_signals'):
                for sig in v._mvc_signals:
                    d[sig] = v
                del v._mvc_signals
        return type.__new__(metacls, name, bases, dct)


class MetaSingleton(type):
    def __init__(cls, name, bases, dict):
        super(MetaSingleton, cls).__init__(name, bases, dict)
        cls.instance = None

    def __call__(cls, *args, **kw):
        if cls.instance is None:
            cls.instance = super(MetaSingleton, cls).__call__(*args, **kw)
        return cls.instance


class Mediator(puremvc.patterns.mediator.Mediator, puremvc.interfaces.IMediator):
    """
    Base class to create Mediator classes.

    This class exists because it's better to use mapping design pattern
    than if ... elif ... in Python.
    """

    __metaclass__ = MetaMediator

    @classmethod
    def listNotificationInterests(cls):
        return getattr(cls, '__mvc_handlers').keys()

    def handleNotification(self, note):
        func = getattr(self,  '__mvc_handlers')[note.getName()]
        data = note.getBody()
        if isinstance(data, (tuple, list)):
            func(self, *data)
        else:
            func(self, data)


def mvcHandler(signal):
    def decorator(func):
        if hasattr(func, '_mvc_signals'):
            func._mvc_signals.append(signal)
        else:
            func._mvc_signals = [signal]
        return func
    return decorator


def join_area(a1, a2):
    # TODO: make a C version
    x1 = min(a1[0], a2[0])
    y1 = min(a1[1], a2[1])
    x2 = max(a1[0]+a1[2], a2[0]+a2[2])
    y2 = max(a1[1]+a1[3], a2[1]+a2[3])
    return x1,y1,x2-x1,y2-y1

##
## PureMVC extention implemented from "PureMVC AS3 Utility - Undo"
##

__all__ += [ "CommandsHistoryProxy", "IUndoableCommand", "UndoableCommand",
             "RECORDABLE_COMMAND", "NON_RECORDABLE_COMMAND" ]

RECORDABLE_COMMAND     = "RecordableCommand"
NON_RECORDABLE_COMMAND = "NonRecordableCommand"

class CommandsHistoryProxy(puremvc.patterns.proxy.Proxy, puremvc.interfaces.IProxy):
    """The model that keeps track of the commands.
    It provides methods to get the next or the previous command from the history.

    In order to record a command into the history, you must set the type of its notification
    to C{RECORDABLE_COMMAND}

    @author dragos
    """

    # The name of the proxy.
    NAME = "CommandsHistoryProxy"

    CMD_HIST_ADD     = 'hist-add'
    CMD_HIST_FLUSHED = 'hist-flushed'
    CMD_HIST_UNDO    = 'undo-done'
    CMD_HIST_REDO    = 'redo-done'

    __instances = []
    __active = None

    def __init__(self, name, data=None):
        super(CommandsHistoryProxy, self).__init__( name, data )

        self.__undoStack = []
        self.__redoStack = []

    #### Public API ####

    def onRegister(self):
        CommandsHistoryProxy.__instances.append(self)
        if CommandsHistoryProxy.__active is None:
            CommandsHistoryProxy.__active = self

    def onRemove(self):
        # Unregistering the proxy flushes it.
        self.__undoStack = []
        self.__redoStack = []

        CommandsHistoryProxy.__instances.remove(self)
        if CommandsHistoryProxy.__active is self:
            CommandsHistoryProxy.__active = None

    def getPrevious(self):
        """Returns the UNDO command.

        Returns the latest command within the undo commands stack

        @return The undoable command of type C{IUndoableCommand}

        @see IUndoableCommand
        """

        if self.__undoStack:
            cmd = self.__undoStack.pop(-1)
            self.__redoStack.append(cmd)

            self.sendNotification( CommandsHistoryProxy.CMD_HIST_UNDO, (self, cmd) )

            return cmd

    def canUndo(self):
        """Indicates if there is an undo command into the history
        @return Return a Boolean value indication if there is an undo command into the history
        """

        return bool(self.__undoStack)

    def getNext(self):
        """Returns the REDO command
        @return The instance of the command
        """

        if self.__redoStack:
            cmd = self.__redoStack.pop(-1)
            self.__undoStack.append(cmd)

            self.sendNotification( CommandsHistoryProxy.CMD_HIST_REDO, (self, cmd) )

            return cmd

    def canRedo(self):
        """Indicates if there is a redo command in the history
        @return True if you can redo, false otherwise
        """

        return bool(self.__redoStack)

    def putCommand(self, cmd):
        """Saves a command into the history.

        UndoableCommand calls this method to save its instance into the history,
        if the type of the notification is C{RECORDABLE_COMMAND}

        @param cmd The instance of the command of type C{IUndoableCommand}

        @see IUndoableCommand
        """

        self.__redoStack = []
        self.__undoStack.append( cmd )

        self.sendNotification( CommandsHistoryProxy.CMD_HIST_ADD, (self, cmd))

    def flush(self):
        # Flush redo stack first
        for cmd in self.__redoStack:
            cmd.flush()
        self.__redoStack = []

        # Then undo stack
        for cmd in self.__undoStack:
            cmd.flush()
        self.__undoStack = []

        # Notify listeners
        self.sendNotification( CommandsHistoryProxy.CMD_HIST_FLUSHED, self)

    def activate(self):
        self.active = self

    @staticmethod
    def get_active():
        return CommandsHistoryProxy.__active

    @staticmethod
    def set_active(proxy):
        assert isinstance(proxy, CommandsHistoryProxy)
        assert proxy in CommandsHistoryProxy.__instances
        CommandsHistoryProxy.__active = proxy

    ### Properties ###

    active = property(fget=lambda self: self.get_active(),
                      fset=lambda self, v: self.set_active(v))

    @property
    def undo_stack(self): return tuple(self.__undoStack)

    @property
    def redo_stack(self): return tuple(self.__redoStack)


class IUndoableCommand(puremvc.interfaces.ICommand, puremvc.interfaces.INotification):
    def getNote(self):
        raise NotImplemented

    def undo(self):
        raise NotImplemented

    def redo(self):
        raise NotImplemented

    def flush(self):
        raise NotImplemented

    def executeCommand(self):
        raise NotImplemented


class UndoableCommand(puremvc.patterns.command.SimpleCommand, IUndoableCommand):

    _note = None
    __undoCmdClass = None

    def execute(self, note):
        """Saves the command into the C{CommandHistoryProxy} class
        and calls the C{executeCommand} method.

        @param note: The C{Notification} instance
        """

        self._note = note
        self.executeCommand()

        if note.getType() == RECORDABLE_COMMAND:
            CommandsHistoryProxy.get_active().putCommand(self)

    def registerUndoCommand(self, cmdClass):
        """Registers the undo command

        @param cmdClass: The class to be executed on undo
        """

        self.__undoCmdClass = cmdClass

    def getNote(self):
        """Returns the notification sent to this command

        @return The notification
        """

        return self._note

    def setNote(self, value):
        """Sets the value for the note

        @param value: The notification of type C{Notification}
        """

        self._note = value

    def executeCommand(self):
        """This method must be overriden in the super class.
        Place here the code for the command to execute.
        """

        raise NotImplemented

    def redo(self):
        """Calls C{executeCommand}
        """

        self.executeCommand()

    def undo(self):
        """Calls the undo command setting its note type to
        C{NON_RECORDABLE_COMMAND} so that it won't get recorded into the history
        since it is already in the history
        """

        if self.__undoCmdClass is None:
            raise RuntimeError("Undo command not set. Could not undo. Use 'registerUndoCommand' to register an undo command")

        ##
        # The type of the notification is used as a flag,
        # indicating wheather to save the command into the history, or not.
        # The undo command, should not be recorded into the history,
        # and its notification type is set to C{NON_RECORDABLE_COMMAND}
        ##
        oldType = self._note.getType()
        self._note.setType( NON_RECORDABLE_COMMAND )

        commandInstance = self.__undoCmdClass()
        commandInstance.execute( self._note )

        self._note.setType( oldType )

    def flush(self):
        pass

    def getCommandName(self):
        """Returns a display name for the undoable command.

        By default, the name of the command is the name of the notification.
        You must override this method when ever you want to set a different name.

        @return The name of the undoable command
        """

        return self.getNote().getName()

##
## Should be located at the end of the file
##

from model.prefs import prefs
from string import Template

class _MyTemplate(Template): idpattern = '[_a-z][_a-z0-9\-]*'

def resolve_path(path):
    path = path.replace('/', os.path.sep)
    old_path = None
    while path != old_path:
        old_path = path
        path = _MyTemplate(path).safe_substitute(prefs)
    return path