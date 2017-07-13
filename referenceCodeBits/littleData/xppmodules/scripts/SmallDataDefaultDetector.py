# importing generic python modules
import psana
import abc

#
# classes for default detector types
#
class defaultDetector(object):
    __metaclass__ = abc.ABCMeta
    def __init__(self, detname, name):
        self.name=name
        self.detname=detname
        self.det=psana.Detector(detname)
    def inRun(self):
        dNames=[]
        for dn in psana.DetNames():
            for dnn in dn:
                if dnn!='':
                    dNames.append(dnn)
        if self.detname in dNames:
            return True
        return False
    @abc.abstractmethod
    def data(self,evt):
        """method that should return a dict of values from event"""
        

class lightStatus(defaultDetector):
    def __init__(self, detname='evr0', codes=[[162],[]]):
        defaultDetector.__init__(self, detname, 'lightStatus')
        self.xrayCodes = codes[0]
        self.laserCodes = codes[1]

    def data(self,evt):
        xfel_status, laser_status = (1,1) # default if no EVR code matches
        dl={}
        evtCodes = self.det.eventCodes(evt)
        for xOff in self.xrayCodes:
            if xOff in evtCodes:
                xfel_status = 0
        for lOff in self.laserCodes:
            if lOff in evtCodes:
                laser_status = 0
        dl['xray']=xfel_status
        dl['laser']=laser_status
        return dl
        
class ipmDetector(defaultDetector):
    def __init__(self, detname, name=None, savePos=False):
        if name is None:
            self.name = detname
        else:
            self.name = name
        defaultDetector.__init__(self, detname, name)
        self.savePos = savePos
    def data(self, evt):
        dl={}
        dl['sum']=self.det.sum(evt)
        dl['channels']=self.det.channel(evt)
        if self.savePos:
            dl['xpos']=self.det.xpos(evt)
            dl['ypos']=self.det.ypos(evt)
        return dl

class bmmonDetector(defaultDetector):
    def __init__(self, detname, name=None, savePos=False):
        if name is None:
            self.name = detname
        else:
            self.name = name
        defaultDetector.__init__(self, detname, name)
        self.savePos = savePos
    def data(self, evt):
        dl={}
        data = self.det.get(evt)
        dl['sum']=data.TotalIntensity()
        dl['channels']=data.peakA()
        if self.savePos:
            dl['xpos']=data.X_Position()
            dl['ypos']=data.Y_Position()
        return dl

class epicsDetector(defaultDetector):
    def __init__(self, name='epics', PVlist=[]):
        self.name = name
        self.detname='epics'
        self.PVlist = PVlist
        self.pvs=[]
        for pv in PVlist:
            try:
                self.pvs.append(psana.Detector(pv))
            except:
                print 'could not find EPICS PV %s in data'%pv
    def inRun(self):
        if len(self.pvs)>0:
            return True
        return False

    def data(self,evt):
        dl={}
        for pvname,pv in zip(self.PVlist,self.pvs):
            dl[pvname]=pv()
        return dl

class encoderDetector(defaultDetector):
    def __init__(self, detname, name=None):
        if name is None:
            self.name = detname
        else:
            self.name = name
        defaultDetector.__init__(self, detname, name)
    def data(self, evt):
        dl={}
        for desc,value in zip(self.det.descriptions(), self.det.values(evt)):
            if desc!='':
                dl[desc]=value
        return dl

class controlDetector(defaultDetector):
    def __init__(self, name='scan'):
        defaultDetector.__init__(self, 'ControlData', 'scan')
        self.stepPV = psana.Detector('scan_current_step')
    def data(self, evt):
        dl={}
        for icpv,cpv in enumerate(self.det().pvControls()):
            dl['var%d'%icpv]=cpv.value()
            dl[cpv.name()]=cpv.value()
            dl['varStep']=self.stepPV()
        return dl

class aiDetector(defaultDetector):
    def __init__(self, detname, name=None):
        if name is None:
            self.name = detname
        else:
            self.name = name
        defaultDetector.__init__(self, detname, name)
        self.aioInfo = [[ i for i in range(0,16)], [ 'ch%02d'%i for i in range(0,16)], [ 1. for i in range(0,16)], [ 0. for i in range(0,16)]]

    def setPars(self, AIOPars):
        if len(AIOPars)<2:
            print 'need 2/3 lists: channel#, user-friendly names & conversion factors (optional)'
            return
        self.aioInfo[0] = AIOPars[0]
        self.aioInfo[1] = AIOPars[1]
        if len(AIOPars)==3:
            self.aioInfo[2] = AIOPars[2]
            if len(AIOPars)==4:
                self.aioInfo[3] = AIOPars[3]
            else:
                self.aioInfo[3] = [0. for entry in AIOPars[0]]
        else:
            self.aioInfo[2] = [1. for entry in AIOPars[0]]

    def data(self, evt):
        dl={}
        for ichn,chName,chnScale,chnOffset in zip(self.aioInfo[0], self.aioInfo[1], self.aioInfo[2], self.aioInfo[3]):
            dl[chName]=self.det.get(evt).channelVoltages()[ichn]*chnScale+chnOffset
        return dl

class ttDetector(defaultDetector):
    def __init__(self, name='tt', baseName='TTSPEC:'):
        self.name = name
        self.detname='epics'
        self.ttNames = ['FLTPOS','FLTPOS_PS','AMPL','FLTPOSFWHM','REFAMPL','AMPLNXT']
        self.PVlist = [ baseName+pvname for pvname in self.ttNames ]
        self.pvs=[]
        for pv in self.PVlist:
            try:
                self.pvs.append(psana.Detector(pv))
            except:
                print 'could not find timetool EPICS PV %s in data'%pv
        self.ttCalib=None
    def inRun(self):
        if len(self.pvs)>0:
            return True
        return False
    def setPars(self, calibPars):
      if calibPars != None:
        self.ttCalib = calibPars

    def data(self,evt):
        dl={}
        for ttname,pvname,pv in zip(self.ttNames,self.PVlist,self.pvs):
            dl[ttname]=pv()
        ttOrg = dl[self.ttNames[1]]
        if self.ttCalib is None:
            dl['ttCorr']=ttOrg
        else:
            dl['ttCorr']=self.ttCalib[0] + self.ttCalib[1]*ttOrg
            if len(self.ttCalib)>2:
                dl['ttCorr']+=ttOrg*ttOrg*self.ttCalib[2]
        return dl

class damageDetector(defaultDetector):
    def __init__(self, name='damage'):
        self.name = name
        self.detNames=[]
        for dn in psana.DetNames():
            if dn[1]!='':
                self.detNames.append(dn[1])
            else:
                self.detNames.append(dn[0])
    def inRun(self):
        return True
    def data(self,evt):
        #check if detectors are in event
        dl={}
        aliases = [ k.alias() for k in evt.keys() ]
        srcNames = [ k.src().__str__().replace(')','').replace('BldInfo(','').replace('DetInfo(','') for k in evt.keys() ]
        for det in self.detNames:
            if det in aliases:
                dl[det.replace('-','_')]=1
            elif det in srcNames:
                dl[det.replace('-','_')]=1
            else:
                dl[det.replace('-','_')]=0
        return dl
