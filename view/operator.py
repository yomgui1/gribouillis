###############################################################################
# Copyright (c) 2009-2012 Guillaume Roguez
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

import utils

__all__ = ["Operator", "eventoperator",
           "execoperator", "get_translation"]


class Operator:
    __exec_op = {}
    __event_op = {}

    get_exec_op = __exec_op.get
    get_event_op = __event_op.get

    @classmethod
    def execoperator(cls, name):
        """operator(name): add a new exec operator.
    
        Add decorated func to the global list of exec operators.
        Funciotn arguments are optional and purpose dependent.
        """

        def decorator(func):
            assert func.__name__ not in cls.__exec_op
            cls.__exec_op[func.__name__] = func
            func.__trans = name
            return func

        return decorator

    @classmethod
    def eventoperator(cls, name):
        """eventoperator(name): add a new event operator.
    
        Add decorated func to the global list of event operators.
        Decorated function must accept an event objet as first argument.
        Others arguments are optional and purpose dependent.
        """

        def decorator(func):
            assert func.__name__ not in cls.__event_op
            cls.__event_op[func.__name__] = func
            func.__trans = name
            return func

        return decorator

    @staticmethod
    def get_translation(func):
        return func.__trans


execoperator = Operator.execoperator
eventoperator = Operator.eventoperator
get_translation = Operator.get_translation
