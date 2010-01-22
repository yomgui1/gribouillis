from surface import Surface
from itertools import islice

class Command:
    def execute(self, *args):
        return 0 # to be overloaded by subclass


class DrawSlice(object):
    """DrawSlice() -> instance.

    Define a time slice of drawing by cummulate
    some initial pixels buffers and an time orderd list of commands
    to apply on them to obtain a final result.

    Without changing initial buffers, we can linearly navigate
    into the commands list to do undo operation.
    Each time a full rendering is done by waking throught the list.
    """
    def __init__(self, src, cmds=[]):
        assert isinstance(src, Surface)
        self._src = src # source surface
        self.result = src.copy()
        self._cmds = list(cmds) # the command stack
        self._last = 0
        self.dirty = True # False when result is up-to-date
        self.weight = 0

    def __nonzero__(self):
        return len(self._cmds) > 0

    def execute(self):
        """Process commands stack on the sources until the topcmd index.

        Instance is marked as non-dirty after.
        """

        # Start with a copy of sources
        self.result = self._src.copy()

        # Process commands on this copy
        w = 0
        for cmd in self.cmds:
            w += cmd.execute(self.result)
        self.weight = w

        # Mark the instance as up-to-date
        self.dirty = False

    def append(self, cmd, astop=True):
        if astop:
            self.flush()
            self._cmds.append(cmd)
            self._last = len(self._cmds)-1
            self.dirty = True
        else:
            self._cmds.append(cmd)

    def pop(self, idx=-1):
        cmd = self._cmds.pop(idx)

        # Re-executing needed?
        if idx <= self._last:
            self._last -= 1
            self.dirty = True
        return cmd

    def flush(self):
        self._cmds = self._cmds[:self._last+1]

    def setTopCmd(self, idx):
        assert self._cmds[idx]
        self._last = idx
        self.dirty = True

    cmds = property(doc="iterator on commands until topcmd (included)",
                    fget=lambda self: islice(self._cmds, self._last))
    topcmd = property(doc="last command to execute in the list",
                      fget=lambda self: self._last,
                      fset=setTopCmd)
