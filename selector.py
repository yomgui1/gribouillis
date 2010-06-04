import pymui as mui

from languages import lang_dict
lang = lang_dict['default']

class Selector(mui.Window):
    def __init__(self):
        mui.Window.__init__(lang.SaveImageWinTitle)

        top = self.RootObject = mui.VGroup()

        dl = mui.DirList(CycleChain=True)
        top.AddChild(dl)

        dl.Notify('DoubleClick', self.OnDoubleClick, when=True)

        self.dl = dl

    def OnDoubleClick(self):
        root = self.dl.Directory or os.getcwd()
        path = os.path.join(root, self.dl.Path)
        if os.path.isdir(path):
            self.dl.Directory = path
        else:
            self.path = path
            self.Confirm()

    def OnActive(self, active):
        pass

    def Confirm(self):
        self.Close()
