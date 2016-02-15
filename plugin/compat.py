from Screens.MessageBox import MessageBox as OrigMessageBox
from . import _

# taken from IPTVPlayer
class eConnectCallbackObj:
    def __init__(self, obj=None, connectHandler=None):
        self.connectHandler = connectHandler
        self.obj = obj
    
    def __del__(self):
        if 'connect' not in dir(self.obj):
            if 'get' in dir(self.obj):
                self.obj.get().remove(self.connectHandler)
            else:
                self.obj.remove(self.connectHandler)
        else:
            del self.connectHandler
        self.connectHandler = None
        self.obj = None

# taken from IPTVPlayer
def eConnectCallback(obj, callbackFun):
    if 'connect' in dir(obj):
        return eConnectCallbackObj(obj, obj.connect(callbackFun))
    else:
        if 'get' in dir(obj):
            obj.get().append(callbackFun)
        else:
            obj.append(callbackFun)
        return eConnectCallbackObj(obj, callbackFun)
    return eConnectCallbackObj()

# this function is not the same accross different images
def LanguageEntryComponent(file, name, index):
    from Tools.Directories import resolveFilename, SCOPE_CURRENT_SKIN
    from Tools.LoadPixmap import LoadPixmap
    png = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, 'countries/' + index + '.png'))
    if png == None:
        png = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, 'countries/' + file + '.png'))
        if png == None:
            png = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, 'countries/missing.png'))
    res = (index, name, png)
    return res


# there is no simple MessageBox in DMM images
SimpleMessageBox = False
try:
    OrigMessageBox("", "", simple=True)
    SimpleMessageBox = True
except TypeError:
    pass

class MessageBox(OrigMessageBox):
    def __init__(self, *args, **kwargs):
        if kwargs.get('simple') is not None and not SimpleMessageBox:
            del kwargs['simple']
        OrigMessageBox.__init__(self, *args, **kwargs)