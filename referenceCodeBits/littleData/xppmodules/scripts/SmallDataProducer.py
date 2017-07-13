# importing generic python modules
import numpy as np
import h5py
import psana
import time
import argparse
import socket
import os

# importing xpp specific modules
from littleData import *
from utilities import *

from SmallDataUtils import *
########################################################## 
##
## User Input start --> 
##
########################################################## 
##########################################################
# functions for run dependant parameters
##########################################################
def getROIs(run):
    if run<=177:
	sigROI = [[1,2], [50,100], [50,100]]
        np.append(sigROI,[[0,1], [150,200], [150,200]],axis=0)
    else:
        sigROI = [[1,2], [65,115], [0,388]]
    if len(sigROI)>1:
        return sigROI, 
    else:
        return sigROI
##########################################################
# run independent parameters 
##########################################################
#event codes which signify no xray/laser
#aliases for experiment specific PVs go here
epicsPV = ['s1h_w']
########################################################## 
##
## <-- User Input end
##
########################################################## 


##########################################################
#command line input parameter: definitions & reading
##########################################################
maxNevt=1e9
chunkSize=-1
dirname = None
parser = argparse.ArgumentParser()
parser.add_argument("--run", help="run")
parser.add_argument("--exp", help="expeariment name")
parser.add_argument("--nevt", help="number of events", type=int)
parser.add_argument("--dir", help="directory for output files (def <exp>/hdf5/smalldata)")
parser.add_argument("--offline", help="run offline (def for current exp from ffb)")
parser.add_argument("--chunks", help="use Chunks of size", type=int)
args = parser.parse_args()
if not args.run:
    run=raw_input("Run Number:\n")
else:
    run=args.run
if not args.exp:
    hutches=['amo','sxr','xpp','xcs','mfx','cxi','mec']
    hostname=socket.gethostname()
    hutch=None
    for thisHutch in hutches:
        if hostname.find(thisHutch)>=0:
            hutch=thisHutch.upper()
    if hutch is None:
        #then check current path
        path=os.getcwd()
        for thisHutch in hutches:
            if path.find(thisHutch)>=0:
                hutch=thisHutch.upper()
    if hutch is None:
        print 'cannot figure out which experiment to use, please specify -e <expname> on commandline'
        sys.exit()
    expname=RegDB.experiment_info.active_experiment(hutch)[1]
    dsname='exp='+expname+':run='+run+':smd:dir=/reg/d/ffb/%s/%s/xtc:live'%(hutch.lower(),expname)
else:
    expname=args.exp
    hutch=expname[0:3]
    dsname='exp='+expname+':run='+run+':smd'
if args.offline:
    dsname='exp='+expname+':run='+run+':smd'
if args.chunks:
    chunkSize=args.chunks
if args.nevt:
    maxNevt=args.nevt
if args.dir:
    dirname=args.dir
    if dirname[-1]=='/':
        dirname=dirname[:-1]

debug = True
time_ev_sum = 0.
try:
    if rank==0:
        print 'looking at data: ',dsname
    ds = psana.MPIDataSource(dsname)
    
    if dirname is None:
        dirname = '/reg/d/psdm/%s/%s/hdf5/smalldata'%(hutch.lower(),expname)
    smldataFile = '%s/%s_Run%03d.h5'%(dirname,expname,int(run))
    if rank==0:
        print 'saving data in file: ',smldataFile
    smldata = ds.small_data(smldataFile,gather_interval=100)
except:
    print 'we seem to not have small data, you need to use the idx file based Ldat_standard code....',dsname
    import sys
    sys.exit()

########################################################## 
##
## User Input start --> 
##
########################################################## 
#define detectors.
ROIs = getROIs(int(run))
cs140_rob = DetObject('cs140_rob' ,ds.env(), int(run), name='cs140_rob', common_mode=1)
dets=[]
if len(ROIs)>0:
    cs140_rob.addROI('ROI',ROIs[0],writeArea=True)
    for i in range(len(ROIs)-1):
        cs140_rob.addROI('ROI_%d'%(i+1),ROIs[i+1],writeArea=True)
dets.append(cs140_rob)   

########################################################## 
##
## <-- User Input end
##
########################################################## 
dets = [ det for det in dets if checkDet(ds.env(), det._srcName)]
#for now require all area detectors in run to also be present in event.

defaultDets = defaultDetectors(hutch)
#ttCalib=[0.,2.,0.]
#setParameter(defaultDets, ttCalib)
#aioParams=[[1],['laser']]
#setParameter(defaultDets, aioParams, 'ai')
if len(epicsPV)>0:
    defaultDets.append(epicsDetector(PVlist=epicsPV, name='epicsUser'))


d={}
for eventNr,evt in enumerate(ds.events()):
    printMsg(eventNr, evt.run())
    time_ev_start = MPI.Wtime()

    if eventNr >= maxNevt:
        break

    #add default data
    defData = detData(defaultDets, evt)
    smldata.event(defData)

    #detector data using DetObject 
    userDict = {}
    for det in dets:
        det.evt = dropObject()
        try:
            det.getData(evt)
        except:
            det.evt.dat = None
        det.processDetector()
        userDict[det._name]=getUserData(det)
    smldata.event(userDict)

    #special stuff (XTCav, tt raw/reprocessed data) -- to be done --

#add config data here
userDataCfg={}
for det in dets:
    userDataCfg[det._name]=getCfgOutput(det)
Config={'UserDataCfg':userDataCfg}
smldata.save(Config)
