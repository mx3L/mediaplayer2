import os

from Components.ActionMap import ActionMap
from Components.ConfigList import ConfigListScreen
from Components.FileList import FileList
from Components.Sources.StaticText import StaticText
from Components.config import config, getConfigListEntry, ConfigSubsection, \
    ConfigYesNo, ConfigOnOff, ConfigDirectory, ConfigSelection, ConfigNothing, \
    ConfigInteger
from Screens.HelpMenu import HelpableScreen
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen

from . import _
from enigma import eEnv

config.plugins.mediaplayer2 = ConfigSubsection()
config.plugins.mediaplayer2.subtitles = ConfigSubsection()
config.plugins.mediaplayer2.repeat = ConfigYesNo(default=False)
config.plugins.mediaplayer2.savePlaylistOnExit = ConfigYesNo(default=True)
config.plugins.mediaplayer2.saveDirOnExit = ConfigYesNo(default=False)
config.plugins.mediaplayer2.defaultDir = ConfigDirectory()
config.plugins.mediaplayer2.sortPlaylists = ConfigYesNo(default=False)
config.plugins.mediaplayer2.alwaysHideInfoBar = ConfigYesNo(default=True)
config.plugins.mediaplayer2.hideInfobarAndClose = ConfigYesNo(default=False)
config.plugins.mediaplayer2.extensionsMenu = ConfigYesNo(default=False)
config.plugins.mediaplayer2.mainMenu = ConfigYesNo(default=False)
config.plugins.mediaplayer2.cueSheetForServicemp3 = ConfigOnOff(default=True)
config.plugins.mediaplayer2.saveLastPosition = ConfigYesNo(default=True)
config.plugins.mediaplayer2.onMovieStart = ConfigSelection(default = "resume", choices = [
        ("ask yes", _("Ask user") + " " + _("default") + " " + _("yes")),
        ("ask no", _("Ask user") + " " + _("default") + " " + _("no")),
        ("resume", _("Resume from last position")),
        ("beginning", _("Start from the beginning"))])

SERVICEMP3          = 4097
SERVICE_EPLAYER3    = 4099
SERVICE_GSTPLAYER   = 5001
SERVICE_EXTEPLAYER3 = 5002

LIBMEDIA_CHOICES = {SERVICEMP3:_('Gstreamer')}

config.plugins.mediaplayer2.useLibMedia = ConfigYesNo(default = False)
fname = "/proc/%d/maps" % os.getpid()
libMediaTest = False

with open(fname) as f:
    for line in f:
        if 'libeplayer3' in line:
            libMediaTest = True
            LIBMEDIA_CHOICES[SERVICE_EPLAYER3] = _('Eplayer3')
            break

try:
    from Plugins.Extensions.ServiceApp import serviceapp_client
except ImportError:
    pass
else:
    if serviceapp_client.isGstPlayerAvailable():
        libMediaTest = True
        LIBMEDIA_CHOICES[SERVICE_GSTPLAYER] = _('Gstreamer(App)')
    if serviceapp_client.isExtEplayer3Available():
        libMediaTest = True
        LIBMEDIA_CHOICES[SERVICE_EXTEPLAYER3] =  _('ExtEplayer3(App)')

sinkChoices = []
if (os.path.isfile(eEnv.resolve("$libdir/gstreamer-1.0/libgstdvbvideosink.so")) and
    os.path.isfile(eEnv.resolve("$libdir/gstreamer-1.0/libgstdvbaudiosink.so"))):
	sinkChoices.append("original")
if (os.path.isfile(eEnv.resolve("$libdir/gstreamer-1.0/libgstdvbvideosinkexp.so")) and
    os.path.isfile(eEnv.resolve("$libdir/gstreamer-1.0/libgstdvbaudiosinkexp.so"))):
	sinkChoices.append("experimental")

config.plugins.mediaplayer2.serviceGstPlayer = ConfigSubsection()
config.plugins.mediaplayer2.serviceGstPlayer.sink = ConfigSelection(default = 'original', choices=sinkChoices)
config.plugins.mediaplayer2.serviceGstPlayer.subtitles = ConfigYesNo(default=True)
config.plugins.mediaplayer2.serviceGstPlayer.bufferSize = ConfigInteger(8192, (1024, 1024 * 64))
config.plugins.mediaplayer2.serviceGstPlayer.bufferDuration = ConfigInteger(0, (0, 100))

if libMediaTest:
    if config.plugins.mediaplayer2.useLibMedia.getValue() == False:
        config.plugins.mediaplayer2.useLibMedia.value = True
        config.plugins.mediaplayer2.useLibMedia.save()
else:
    if config.plugins.mediaplayer2.useLibMedia.getValue() == True:
        config.plugins.mediaplayer2.useLibMedia.value = False
        config.plugins.mediaplayer2.useLibMedia.save()

config.plugins.mediaplayer2.libMedia = ConfigSelection(default=str(SERVICEMP3), choices=[(str(k), v) for k,v in LIBMEDIA_CHOICES.items()])
config.plugins.mediaplayer2.lcdOnVideoPlayback = ConfigSelection(default='default', choices=[
        ('default', _("Default")),
        ('remaining', _("shows remaining time")),
        ('position', _("shows current position"))])
config.plugins.mediaplayer2.contextMenuType = ConfigSelection(default='intermediate', choices=[
        ("simple", _("Simple")),
        ("intermediate", _("Intermediate")),
        ("expert", _("Expert")) ])


try:
    import sqlite3
except ImportError:
    sqlite3 = None
    config.plugins.mediaplayer2.cueSheetForServicemp3.value = False


def ServiceGstPlayerApplySettings():
    if config.plugins.mediaplayer2.serviceGstPlayer.sink.value == "original":
        videoSink, audioSink = ("dvbvideosink", "dvbaudiosink")
    else:
        videoSink, audioSink = ("dvbvideosinkexp", "dvbaudiosinkexp")
    subtitleEnabled = config.plugins.mediaplayer2.serviceGstPlayer.subtitles.value
    bufferSize = config.plugins.mediaplayer2.serviceGstPlayer.bufferSize.value
    bufferDuration = config.plugins.mediaplayer2.serviceGstPlayer.bufferDuration.value
    serviceapp_client.setGstreamerPlayerSettings(serviceapp_client.OPTIONS_USER, videoSink, audioSink, subtitleEnabled, bufferSize, bufferDuration)
    serviceapp_client.setUseUserSettings()

class DirectoryBrowser(Screen, HelpableScreen):

    def __init__(self, session, currDir):
        Screen.__init__(self, session)
        # for the skin: first try MediaPlayerDirectoryBrowser, then FileBrowser, this allows individual skinning
        self.skinName = ["MediaPlayerDirectoryBrowser", "FileBrowser" ]

        HelpableScreen.__init__(self)

        self["key_red"] = StaticText(_("Cancel"))
        self["key_green"] = StaticText(_("Use"))

        self.filelist = FileList(currDir, matchingPattern="")
        self["filelist"] = self.filelist

        self["FilelistActions"] = ActionMap(["SetupActions", "ColorActions"],
            {
                "green": self.use,
                "red": self.exit,
                "ok": self.ok,
                "cancel": self.exit
            })
        self.onLayoutFinish.append(self.layoutFinished)

    def layoutFinished(self):
        self.setTitle(_("Directory browser"))

    def ok(self):
        if self.filelist.canDescent():
            self.filelist.descent()

    def use(self):
        if self["filelist"].getCurrentDirectory() is not None:
            if self.filelist.canDescent() and self["filelist"].getFilename() and len(self["filelist"].getFilename()) > len(self["filelist"].getCurrentDirectory()):
                self.filelist.descent()
                self.close(self["filelist"].getCurrentDirectory())
        else:
                self.close(self["filelist"].getFilename())

    def exit(self):
        self.close(False)

class MediaPlayerSettings(Screen,ConfigListScreen):

    def __init__(self, session, parent):
        Screen.__init__(self, session)
        # for the skin: first try MediaPlayerSettings, then Setup, this allows individual skinning
        self.skinName = ["MediaPlayerSettings", "Setup" ]
        self.setup_title = _("Edit settings")
        self.onChangedEntry = [ ]

        self["key_red"] = StaticText(_("Cancel"))
        self["key_green"] = StaticText(_("Save"))

        ConfigListScreen.__init__(self, [], session = session, on_change = self.changedEntry)
        self.parent = parent
        self.removeAllPositionsCfg = ConfigNothing()
        self.initConfigList()
        config.plugins.mediaplayer2.saveDirOnExit.addNotifier(self.initConfigList)
        config.plugins.mediaplayer2.libMedia.addNotifier(self.initConfigList)

        self["setupActions"] = ActionMap(["SetupActions", "ColorActions"],
        {
            "green": self.save,
            "red": self.cancel,
            "cancel": self.cancel,
            "ok": self.ok,
        }, -2)
        self.onClose.append(self.removeNotifiers)

    def layoutFinished(self):
        self.setTitle(self.setup_title)

    def removeNotifiers(self):
        config.plugins.mediaplayer2.libMedia.notifiers.remove(self.initConfigList)

    def initConfigList(self, element=None):
        try:
            self.list = []
            self.list.append(getConfigListEntry(_("context menu"), config.plugins.mediaplayer2.contextMenuType))
            self.list.append(getConfigListEntry(_("repeat playlist"), config.plugins.mediaplayer2.repeat))
            self.list.append(getConfigListEntry(_("save playlist on exit"), config.plugins.mediaplayer2.savePlaylistOnExit))
            self.list.append(getConfigListEntry(_("save last directory on exit"), config.plugins.mediaplayer2.saveDirOnExit))
            if not config.plugins.mediaplayer2.saveDirOnExit.getValue():
                self.list.append(getConfigListEntry(_("start directory"), config.plugins.mediaplayer2.defaultDir))
            self.list.append(getConfigListEntry(_("sorting of playlists"), config.plugins.mediaplayer2.sortPlaylists))
            self.list.append(getConfigListEntry(_("always hide infobar"), config.plugins.mediaplayer2.alwaysHideInfoBar))
            self.list.append(getConfigListEntry(_("hide infobar and close"), config.plugins.mediaplayer2.hideInfobarAndClose))
            if sqlite3 is None:
                self.list.append(getConfigListEntry(_("sqlite3 library is missing!, cuesheets for servicemp3 disabled"), ConfigNothing()))
            else:
                self.list.append(getConfigListEntry(_("cuesheets for servicemp3 (restart plugin)"), config.plugins.mediaplayer2.cueSheetForServicemp3))
                if config.plugins.mediaplayer2.cueSheetForServicemp3.value:
                    self.list.append(getConfigListEntry(_("remove all saved positions"), self.removeAllPositionsCfg))
            self.list.append(getConfigListEntry(_("save last position (restart plugin)"), config.plugins.mediaplayer2.saveLastPosition))
            self.list.append(getConfigListEntry(_("on movie start (restart plugin)"), config.plugins.mediaplayer2.onMovieStart))
            self.list.append(getConfigListEntry(_("LCD on video playback"), config.plugins.mediaplayer2.lcdOnVideoPlayback))
            self.list.append(getConfigListEntry(_("show in extensions menu"), config.plugins.mediaplayer2.extensionsMenu))
            self.list.append(getConfigListEntry(_("show in main menu"), config.plugins.mediaplayer2.mainMenu))
            if config.plugins.mediaplayer2.useLibMedia.getValue() == True:
                self.list.append(getConfigListEntry(_("media framework"), config.plugins.mediaplayer2.libMedia))
                if int(config.plugins.mediaplayer2.libMedia.value) == SERVICE_GSTPLAYER:
                    self.list.append(getConfigListEntry(_("sink"), config.plugins.mediaplayer2.serviceGstPlayer.sink))
                    self.list.append(getConfigListEntry(_("subtitles"), config.plugins.mediaplayer2.serviceGstPlayer.subtitles))
            self["config"].setList(self.list)
        except KeyError:
            print "keyError"

    def changedConfigList(self):
        self.initConfigList()

    def keyRight(self):
        ConfigListScreen.keyRight(self)
        if self["config"].getCurrent()[1] == config.plugins.mediaplayer2.cueSheetForServicemp3:
            self.initConfigList()

    def keyLeft(self):
        ConfigListScreen.keyLeft(self)
        if self["config"].getCurrent()[1] == config.plugins.mediaplayer2.cueSheetForServicemp3:
            self.initConfigList()

    def ok(self):
        if self["config"].getCurrent()[1] == config.plugins.mediaplayer2.defaultDir:
            self.session.openWithCallback(self.DirectoryBrowserClosed, DirectoryBrowser, self.parent.filelist.getCurrentDirectory())
        elif self["config"].getCurrent()[1] == self.removeAllPositionsCfg:
            message = _("Do you really want to delete all saved positions?")
            self.session.openWithCallback(self.removeDbCB, MessageBox, message, type=MessageBox.TYPE_YESNO)

    def removeDbCB(self, answer):
        if answer:
            from util import CueSheetDAO
            try:
                CueSheetDAO.instance.clean_db()
            except Exception as e:
                print str(e)

    def DirectoryBrowserClosed(self, path):
        print "PathBrowserClosed:" + str(path)
        if path != False:
            config.plugins.mediaplayer2.defaultDir.setValue(path)

    def save(self):
        for x in self["config"].list:
            x[1].save()
        self.close()

    def cancel(self):
        self.close()

    # for summary:
    def changedEntry(self):
        for x in self.onChangedEntry:
            x()

    def getCurrentEntry(self):
        return self["config"].getCurrent()[0]

    def getCurrentValue(self):
        return str(self["config"].getCurrent()[1].getText())

    def createSummary(self):
        from Screens.Setup import SetupSummary
        return SetupSummary
