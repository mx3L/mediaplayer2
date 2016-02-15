'''
Created on Jun 19, 2015

@author: marko
'''
from bisect import insort
import traceback

from Components.ActionMap import HelpableActionMap
from Components.Label import Label
from Components.Renderer.PositionGauge import PositionGauge
from Components.ServiceEventTracker import ServiceEventTracker
from Components.config import config
from Screens.AudioSelection import AudioSelection
from Screens.InfoBarGenerics import InfoBarShowHide, InfoBarAudioSelection
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Tools import Notifications
from Tools.Directories import resolveFilename, SCOPE_CONFIG

from enigma import iPlayableService, eTimer, getDesktop
from skin import parseColor

from compat import eConnectCallback


# InfoBarCueSheetSupport from OpenPli with removed getLastPosition and
# with delayed __serviceStarted, in case serviceReference is not yet set (BH image)
# changed on_movie_start config
 
class InfoBarCueSheetSupport:
    CUT_TYPE_IN = 0
    CUT_TYPE_OUT = 1
    CUT_TYPE_MARK = 2
    CUT_TYPE_LAST = 3

    ENABLE_RESUME_SUPPORT = False

    def __init__(self, actionmap="InfobarCueSheetActions"):
        self["CueSheetActions"] = HelpableActionMap(self, actionmap,
            {
                "jumpPreviousMark": (self.jumpPreviousMark, _("Jump to previous marked position")),
                "jumpNextMark": (self.jumpNextMark, _("Jump to next marked position")),
                "toggleMark": (self.toggleMark, _("Toggle a cut mark at the current position"))
            }, prio=1)

        self.cut_list = [ ]
        self.is_closing = False
        self.timer = eTimer()
        self.timer_conn = eConnectCallback(self.timer.timeout, self.__isServiceStarted)
        self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
            {
                iPlayableService.evStart: self.__serviceStarted,
                iPlayableService.evCuesheetChanged: self.downloadCuesheet,
            })
        self.onClose.append(self.__onClose)

    def __serviceStarted(self):
        if self.is_closing:
            return
        self.timer.start(100)

    def __isServiceStarted(self):
        if self.session.nav.getCurrentlyPlayingServiceReference() is not None:
            self.timer.stop()
            self.__servicePlaying()
        else:
            print 'service not yet started...'
        
    def __servicePlaying(self):
        print "new service started! trying to download cuts!"
        self.downloadCuesheet()

        if self.ENABLE_RESUME_SUPPORT:
            last = None
            for (pts, what) in self.cut_list:
                if what == self.CUT_TYPE_LAST:
                    last = pts
                    break
            if last is None:
                return
            # only resume if at least 10 seconds ahead, or <10 seconds before the end.
            seekable = self.__getSeekable()
            if seekable is None:
                return  # Should not happen?
            length = seekable.getLength() or (None, 0)
            print "seekable.getLength() returns:", length
            # Hmm, this implies we don't resume if the length is unknown...
            if (last > 900000) and (not length[1]  or (last < length[1] - 900000)):
                self.resume_point = last
                l = last / 90000
                on_movie_start = config.plugins.mediaplayer2.onMovieStart.value
                if "ask" in on_movie_start or not length[1]:
                    Notifications.AddNotificationWithCallback(self.playLastCB, MessageBox, _("Do you want to resume this playback?") + "\n" + (_("Resume position at %s") % ("%d:%02d:%02d" % (l / 3600, l % 3600 / 60, l % 60))), timeout=10, default="yes" in on_movie_start)
                elif on_movie_start == "resume":
# TRANSLATORS: The string "Resuming playback" flashes for a moment
# TRANSLATORS: at the start of a movie, when the user has selected
# TRANSLATORS: "Resume from last position" as start behavior.
# TRANSLATORS: The purpose is to notify the user that the movie starts
# TRANSLATORS: in the middle somewhere and not from the beginning.
# TRANSLATORS: (Some translators seem to have interpreted it as a
# TRANSLATORS: question or a choice, but it is a statement.)
                    Notifications.AddNotificationWithCallback(self.playLastCB, MessageBox, _("Resuming playback"), timeout=2, type=MessageBox.TYPE_INFO)

    def playLastCB(self, answer):
        if answer == True:
            self.doSeek(self.resume_point)
        self.hideAfterResume()

    def hideAfterResume(self):
        if isinstance(self, InfoBarShowHide):
            self.hide()

    def __getSeekable(self):
        service = self.session.nav.getCurrentService()
        if service is None:
            return None
        return service.seek()

    def cueGetCurrentPosition(self):
        seek = self.__getSeekable()
        if seek is None:
            return None
        r = seek.getPlayPosition()
        if r[0]:
            return None
        return long(r[1])

    def cueGetEndCutPosition(self):
        ret = False
        isin = True
        for cp in self.cut_list:
            if cp[1] == self.CUT_TYPE_OUT:
                if isin:
                    isin = False
                    ret = cp[0]
            elif cp[1] == self.CUT_TYPE_IN:
                isin = True
        return ret

    def jumpPreviousNextMark(self, cmp, start=False):
        current_pos = self.cueGetCurrentPosition()
        if current_pos is None:
            return False
        mark = self.getNearestCutPoint(current_pos, cmp=cmp, start=start)
        if mark is not None:
            pts = mark[0]
        else:
            return False

        self.doSeek(pts)
        return True

    def jumpPreviousMark(self):
        # we add 5 seconds, so if the play position is <5s after
        # the mark, the mark before will be used
        self.jumpPreviousNextMark(lambda x:-x - 5 * 90000, start=True)

    def jumpNextMark(self):
        if not self.jumpPreviousNextMark(lambda x: x - 90000):
            self.doSeek(-1)

    def getNearestCutPoint(self, pts, cmp=abs, start=False):
        # can be optimized
        beforecut = True
        nearest = None
        bestdiff = -1
        instate = True
        if start:
            bestdiff = cmp(0 - pts)
            if bestdiff >= 0:
                nearest = [0, False]
        for cp in self.cut_list:
            if beforecut and cp[1] in (self.CUT_TYPE_IN, self.CUT_TYPE_OUT):
                beforecut = False
                if cp[1] == self.CUT_TYPE_IN:  # Start is here, disregard previous marks
                    diff = cmp(cp[0] - pts)
                    if start and diff >= 0:
                        nearest = cp
                        bestdiff = diff
                    else:
                        nearest = None
                        bestdiff = -1
            if cp[1] == self.CUT_TYPE_IN:
                instate = True
            elif cp[1] == self.CUT_TYPE_OUT:
                instate = False
            elif cp[1] in (self.CUT_TYPE_MARK, self.CUT_TYPE_LAST):
                diff = cmp(cp[0] - pts)
                if instate and diff >= 0 and (nearest is None or bestdiff > diff):
                    nearest = cp
                    bestdiff = diff
        return nearest

    def toggleMark(self, onlyremove=False, onlyadd=False, tolerance=5 * 90000, onlyreturn=False):
        current_pos = self.cueGetCurrentPosition()
        if current_pos is None:
            print "not seekable"
            return

        nearest_cutpoint = self.getNearestCutPoint(current_pos)

        if nearest_cutpoint is not None and abs(nearest_cutpoint[0] - current_pos) < tolerance:
            if onlyreturn:
                return nearest_cutpoint
            if not onlyadd:
                self.removeMark(nearest_cutpoint)
        elif not onlyremove and not onlyreturn:
            self.addMark((current_pos, self.CUT_TYPE_MARK))

        if onlyreturn:
            return None

    def addMark(self, point):
        insort(self.cut_list, point)
        self.uploadCuesheet()
        self.showAfterCuesheetOperation()

    def removeMark(self, point):
        self.cut_list.remove(point)
        self.uploadCuesheet()
        self.showAfterCuesheetOperation()

    def showAfterCuesheetOperation(self):
        if isinstance(self, InfoBarShowHide):
            self.doShow()

    def __getCuesheet(self):
        service = self.session.nav.getCurrentService()
        if service is None:
            return None
        return service.cueSheet()

    def uploadCuesheet(self):
        cue = self.__getCuesheet()

        if cue is None:
            print "upload failed, no cuesheet interface"
            return
        cue.setCutList(self.cut_list)

    def downloadCuesheet(self):
        cue = self.__getCuesheet()

        if cue is None:
            print "download failed, no cuesheet interface"
            self.cut_list = [ ]
        else:
            self.cut_list = cue.getCutList()
            
    def __onClose(self):
        self.timer.stop()
        del self.timer_conn
        del self.timer


class MyInfoBarCueSheetSupport(InfoBarCueSheetSupport):
    def __init__(self, actionmap='InfobarCueSheetActions', dbfilename='cuesheet.db', gaugeRenderers=None, cueSheetForServicemp3=True):
        InfoBarCueSheetSupport.__init__(self, actionmap)
        self.cueSheetForServicemp3 = cueSheetForServicemp3
        gaugeRenderers = gaugeRenderers or []
        gaugeRenderer = self.getGaugeRenderer(self.renderer)
        gaugeRenderers = gaugeRenderers or gaugeRenderer and [gaugeRenderer] or []
        self.__gaugeRenderers = gaugeRenderers
        self.__cutList = CutList(dbfilename)

    def __defaultGaugeRenderers(self):
        for r in self.__gaugeRenderers:
            r.cutlist_changed = PositionGauge.__dict__['cutlist_changed'].__get__(r, PositionGauge)

    def __customGuageRenderers(self):
        for r in self.__gaugeRenderers:
            r.cutlist_changed = lambda: self.cut_list

    def saveLastPosition(self):
        service = self.session.nav.getCurrentService()
        if service is None:
            print '[InfoBarCueSheet] saveLastPosition - cannot save service is None!'
            return
        seekable = service and service.seek()
        length = seekable and seekable.getLength()
        length = length[0] and None or long(length[1])
        if length is None:
            print '[InfoBarCueSheet] saveLastPosition - cannot save length is None!'
            return
        position = self.cueGetCurrentPosition()
        if position is None:
            print '[InfoBarCueSheet] saveLastPosition - cannot save position is None!'
            return
        if not (length - position > 60 * 90 * 1000):
            print "[InfoBarCueSheet] saveLastPosition - not saving position, its within end limit"
            self.removeLastPosition()
            return
        # cleanup LAST marks
        for mark in self.cut_list[:]:
            if mark[1] == InfoBarCueSheetSupport.CUT_TYPE_LAST:
                self.cut_list.remove(mark)
        l = position / 90000
        print "[InfoBarCueSheet] saveLastPosition - saving position %d:%02d:%02d" % ((l / 3600, l % 3600 / 60, l % 60))
        self.addMark((position, InfoBarCueSheetSupport.CUT_TYPE_LAST))

    def removeLastPosition(self):
        last_mark = None
        for mark in self.cut_list:
            if mark[1] == InfoBarCueSheetSupport.CUT_TYPE_LAST:
                last_mark = mark

        for mark in self.cut_list[:]:
            if mark[1] == InfoBarCueSheetSupport.CUT_TYPE_LAST:
                if last_mark is not None and mark != last_mark:
                    self.cut_list.remove(mark)

        if last_mark is None:
            print "[InfoBarCueSheet] removeLastPosition - nothing to remove"
            return
        l = last_mark[0] / 90000
        print "[InfoBarCueSheet] removeLastPosition - %d:%02d:%02d" % ((l / 3600, l % 3600 / 60, l % 60))
        self.removeMark(last_mark)

    def getGaugeRenderer(self, rendererList):
        i = 0
        positionGauge = None
        for r in rendererList:
            if isinstance(r, PositionGauge):
                i += 1
                positionGauge = r
        if i == 0:
            print "[InfoBarCueSheetSupport] no PositionGuage render found"
        elif i > 2:
            print "[InfoBarCueSheetSupport] more PositionGuage renderers found"
            return None
        elif i == 1:
            print "[InfoBarCueSheetSupport] found PositionGuage renderer"
        return positionGauge

    def updateGaugeRenderers(self):
        for r in self.__gaugeRenderers:
            r.setCutlist(map(lambda x:(long(x[0]), int(x[1])), (cut for cut in self.cut_list)))

    def downloadCuesheet(self):
        if self.cueSheetForServicemp3:
            sref = self.session.nav.getCurrentlyPlayingServiceReference()
            if sref is None:
                print '[InfobarCueSheetSupport] downloadCuesheet - serviceReference is None!'
                return
            print '[InfobarCueSheetSupport] downloadCuesheet - serviceReference type : %d' % sref.type
            if sref.type == 4097:
                try:
                    self.cut_list = self.__cutList.getCutList(sref.getPath())
                except Exception:
                    traceback.print_exc()
                else:
                    self.__customGuageRenderers()
                    self.updateGaugeRenderers()
            else:
                self.__defaultGaugeRenderers()
                InfoBarCueSheetSupport.downloadCuesheet(self)
        else:
            InfoBarCueSheetSupport.downloadCuesheet(self)

    def uploadCuesheet(self):
        if self.cueSheetForServicemp3:
            sref = self.session.nav.getCurrentlyPlayingServiceReference()
            sref_type = sref and sref.type
            if sref_type and sref_type == 4097:
                try:
                    self.__cutList.setCutList(sref.getPath(), self.cut_list)
                except Exception:
                    traceback.print_exc()
                else:
                    self.__customGuageRenderers()
                    self.updateGaugeRenderers()
            else:
                self.__defaultGaugeRenderers()
                InfoBarCueSheetSupport.uploadCuesheet(self)
        else:
            InfoBarCueSheetSupport.uploadCuesheet(self)
        
        
class StatusScreen(Screen):

    def __init__(self, session):
        desktop = getDesktop(0)
        size = desktop.size()
        self.sc_width = size.width()
        self.sc_height = size.height()

        statusPositionX = 50
        statusPositionY = 100
        self.delayTimer = eTimer()
        self.delayTimer_conn = eConnectCallback(self.delayTimer.timeout, self.hideStatus)
        self.delayTimerDelay = 1500

        self.skin = """
            <screen name="StatusScreen" position="%s,%s" size="%s,90" zPosition="0" backgroundColor="transparent" flags="wfNoBorder">
                    <widget name="status" position="0,0" size="%s,70" valign="center" halign="left" font="Regular;22" transparent="1" foregroundColor="yellow" shadowColor="#40101010" shadowOffset="3,3" />
            </screen>""" % (str(statusPositionX), str(statusPositionY), str(self.sc_width), str(self.sc_width))

        Screen.__init__(self, session)
        self.stand_alone = True
        print 'initializing status display'
        self["status"] = Label("")
        self.onClose.append(self.__onClose)

    def setStatus(self, text, color="yellow"):
        self['status'].setText(text)
        self['status'].instance.setForegroundColor(parseColor(color))
        self.show()
        self.delayTimer.start(self.delayTimerDelay, True)

    def hideStatus(self):
        self.hide()
        self['status'].setText("")

    def __onClose(self):
        self.delayTimer.stop()
        del self.delayTimer_conn
        del self.delayTimer

class CutList(object):
    def __init__(self, filename):
        try:
            from util import CueSheetDAO
        except ImportError as e:
            self.sqlite3 = False
        else:
            self.sqlite3 = True
            self.cueSheetDAO = CueSheetDAO(resolveFilename(SCOPE_CONFIG, filename))

    def getCutList(self, path):
        if not self.sqlite3:
            print '[CutList] python-sqlite3 not installed'
            return []
        cutList = self.cueSheetDAO.get_cut_list(unicode(path, 'utf-8'))
        if cutList is not None:
            return map(lambda x:(long(x[0] * 90000), int(x[1])), (x for x in cutList))

    def setCutList(self, path, cutList):
        if not self.sqlite3:
            print '[CutList] python-sqlite3 not installed'
            return
        self.cueSheetDAO.set_cut_list(unicode(path, 'utf-8'), map(lambda x:(int(x[0] / 90000), int(x[1])), (x for x in cutList)))




# audioSelection with removed subtitles support
class MyAudioSelection(AudioSelection):

    def __init__(self, session, infobar=None, page='audio'):
        try:
            AudioSelection.__init__(self, session, infobar, page)
        except Exception:
            # really old AudioSelection
            AudioSelection.__init__(self, session)
        self.skinName = 'AudioSelection'

    def getSubtitleList(self):
        return []

class MyInfoBarAudioSelection(InfoBarAudioSelection):

    def audioSelection(self):
        self.session.openWithCallback(self.audioSelected, MyAudioSelection, infobar=self)


class InfoBarAspectChange:
    """
    Simple aspect ratio changer
    """

    V_DICT = {'16_9_letterbox':{'aspect':'16:9', 'policy2':'letterbox', 'title':'16:9 ' + _("Letterbox")},
                         '16_9_panscan':{'aspect':'16:9', 'policy2':'panscan', 'title':'16:9 ' + _("Pan&scan")},
                         '16_9_nonlinear':{'aspect':'16:9', 'policy2':'panscan', 'title':'16:9 ' + _("Nonlinear")},
                         '16_9_bestfit':{'aspect':'16:9', 'policy2':'bestfit', 'title':'16:9 ' + _("Just scale")},
                         '16_9_4_3_pillarbox':{'aspect':'16:9', 'policy':'pillarbox', 'title':'4:3 ' + _("PillarBox")},
                         '16_9_4_3_panscan':{'aspect':'16:9', 'policy':'panscan', 'title':'4:3 ' + _("Pan&scan")},
                         '16_9_4_3_nonlinear':{'aspect':'16:9', 'policy':'nonlinear', 'title':'4:3 ' + _("Nonlinear")},
                         '16_9_4_3_bestfit':{'aspect':'16:9', 'policy':'bestfit', 'title':_("Just scale")},
                         '4_3_letterbox':{'aspect':'4:3', 'policy':'letterbox', 'policy2':'policy', 'title':_("Letterbox")},
                         '4_3_panscan':{'aspect':'4:3', 'policy':'panscan', 'policy2':'policy', 'title':_("Pan&scan")},
                         '4_3_bestfit':{'aspect':'4:3', 'policy':'bestfit', 'policy2':'policy', 'title':_("Just scale")}}

    V_MODES = ['16_9_letterbox', '16_9_panscan', '16_9_nonlinear', '16_9_bestfit',
                                '16_9_4_3_pillarbox', '16_9_4_3_panscan', '16_9_4_3_nonlinear', '16_9_4_3_bestfit',
                                '4_3_letterbox', '4_3_panscan', '4_3_bestfit']


    def __init__(self):
        self.aspectChanged = False
        try:
            self.defaultAspect = open("/proc/stb/video/aspect", "r").read().strip()
        except IOError:
            self.defaultAspect = None
        try:
            self.defaultPolicy = open("/proc/stb/video/policy", "r").read().strip()
        except IOError:
            self.defaultPolicy = None
        try:
            self.defaultPolicy2 = open("/proc/stb/video/policy2", "r").read().strip()
        except IOError:
            self.defaultPolicy2 = None
        self.currentAVMode = self.V_MODES[0]

        self["aspectChangeActions"] = HelpableActionMap(self, "InfobarAspectChangeActions",
            {
             "aspectChange":(self.aspectChange, _("change aspect ratio"))
              }, -3)

        self.onClose.append(self.__onClose)


    def getAspectStr(self):
        mode = self.V_DICT[self.currentAVMode]
        aspectStr = mode['aspect']
        policyStr = mode['title']
        return "%s: %s\n%s: %s" % (_("Aspect"), aspectStr, _("Policy"), policyStr)


    def setAspect(self, aspect, policy, policy2):
        print 'aspect: %s policy: %s policy2: %s' % (str(aspect), str(policy), str(policy2))
        if aspect:
            try:
                open("/proc/stb/video/aspect", "w").write(aspect)
            except IOError as e:
                print e
        if policy:
            try:
                open("/proc/stb/video/policy", "w").write(policy)
            except IOError as e:
                print e
        if policy2:
            try:
                open("/proc/stb/video/policy2", "w").write(policy2)
            except IOError as e:
                print e


    def toggleAVMode(self):
        self.aspectChanged = True
        modeIdx = self.V_MODES.index(self.currentAVMode)
        if modeIdx + 1 == len(self.V_MODES):
            modeIdx = 0
        else:
            modeIdx += 1
        self.currentAVMode = self.V_MODES[modeIdx]
        mode = self.V_DICT[self.currentAVMode]
        aspect = mode['aspect']
        policy = 'policy' in mode and mode['policy'] or None
        policy2 = 'policy2' in mode and mode['policy2'] or None
        self.setAspect(aspect, policy, policy2)

    def __onClose(self):
        if self.aspectChanged:
            self.setAspect(self.defaultAspect, self.defaultPolicy, self.defaultPolicy2)
