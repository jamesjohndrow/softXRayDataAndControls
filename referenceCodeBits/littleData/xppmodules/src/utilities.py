import os
import copy
import cPickle
import json
import copy
import numpy as np
import h5py
from scipy import optimize
from scipy import ndimage
from os import walk
from os import path

from matplotlib import pyplot as plt

from mpi4py import MPI
comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

import time
import psana
import RegDB.experiment_info

import resource

def MAD(a, c=0.6745, axis=None):
  """
  Median Absolute Deviation along given axis of an array:
  
  median(abs(a - median(a))) / c
  
  c = 0.6745 is the constant to convert from MAD to std; it is used by
  default  
  """
  
  a = np.ma.masked_where(a!=a, a)
  if a.ndim == 1:
    d = np.ma.median(a)
    m = np.ma.median(ma.fabs(a - d) / c)
  else:
    d = np.ma.median(a, axis=axis)
    # I don't want the array to change so I have to copy it?
    if axis > 0:
      aswp = np.ma.swapaxes(a,0,axis)
    else:
      aswp = a
      m = np.ma.median(ma.fabs(aswp - d) / c, axis=0)
      
  return m
    
def nanmedian(arr, **kwargs):
      """
      Returns median ignoring NAN
      """
      return np.ma.median( np.ma.masked_where(arr!=arr, arr), **kwargs )
    
def rebinFactor(a, shape):
    sh = shape[0],a.shape[0]//shape[0],shape[1],a.shape[1]//shape[1]
    return a.reshape(sh).mean(-1).mean(1)

def rebin(a, shape):
    if isinstance(shape, float) or isinstance(shape, int):
      shape = [shape, shape]
    if (a.shape[0]%shape[0]) == 0 and (a.shape[1]%shape[1]) == 0:
      rebinFactor(a, shape)
    else:
      factor = [ float(int(a.shape[0]/shape[0])+1), float(int(a.shape[1]/shape[1])+1)]
      bigImg = ndimage.zoom(a, [shape[0]*factor[0]/a.shape[0],shape[1]*factor[1]/a.shape[1]])
      img = rebinFactor(bigImg, shape)
    return img

def reduceVar(vals, sigROI,threshold=-1e25):
    if threshold!=-1e25:
      vals = vals[vals<threshold]=0
    print 'array shape: ',len(vals.shape)
    if len(vals.shape)>1 and sigROI!=[]:
      if len(vals.shape)==2:
        if not isinstance(sigROI, list):
          return vals[:,sigROI]
        elif len(sigROI)>1:
          return vals[:,sigROI[0]:sigROI[1]]
        else:
          return vals[:,sigROI[0]]
      elif len(vals.shape)==3:
        if not isinstance(sigROI, list):
          return vals[:,sigROI,:]
        elif len(sigROI)==1:
          return vals[:,sigROI[0],:]
        elif len(sigROI)==2:
          return vals[:,sigROI[0]:sigROI[1],:]
        else:
          return vals[:,sigROI[0]:sigROI[1],sigROI[2]:sigROI[3]]
      elif len(vals.shape)==4:
        if not isinstance(sigROI, list):
          return vals[:,sigROI,:,:]
        elif len(sigROI)==1:
          return vals[:,sigROI[0],:,:]
        elif len(sigROI)==2:
          return vals[:,sigROI[0]:sigROI[1],:,:]
        elif len(sigROI)==4:
          return vals[:,sigROI[0]:sigROI[1],sigROI[2]:sigROI[3],:]
        else:
          return vals[:,sigROI[0]:sigROI[1],sigROI[2]:sigROI[3],sigROI[4]:sigROI[5]]

    print 'this dimension is not yet implemented:',vals.shape,' ROI: ',sigROI
    return vals
                                                                                            
#from ixppy
def E2lam(E,o=0):
    """ Computes photon wavelength in m
        E is photon energy in eV or keV
        set o to 0 if working at sub-100 eV energies
    """
    if o:
      E=E
    else:
      E=eV(E)
    lam=(12398.4/E)*1e-10
    return lam
  #lam = 12.39842 /E
  #return lam

def eV(E):
  if E < 100:
    E=E*1000.0;
    return E*1.0

def msg(s,newline=True):
  sys.stdout.write(s)
  if (newline):
    sys.stdout.write("\n")
  sys.stdout.flush()


def now():
  """ returns string with current date and time (with millisecond resolution)"""
  import datetime
  now = datetime.datetime.now()
  return "%04d-%02d-%02d %02d:%02d:%02d.%03d" % ( now.year, now.month,now.day,
                     now.hour,now.minute,now.second,int(now.microsecond/1e3))


def update_average(n, A, B):
    '''
    updates a numpy matrix A that represents an average over the previous n-1 shots
    by including B into the average, B being the nth shot
    '''
    if type(A).__name__ != type(B).__name__:
        print 'NOT SAME TYPE',type(A).__name__ ,' ',type(B).__name__
        return A
        
    #not actually taking an average
    if n == 0:
        A += B
        return A
    elif n == 1:
        A = B
        return A
    elif np.sum(A) == 0 or np.sum(A) == 1:
        A = B
        return A
    else:
        A *= float(n-1)/float(n)
        A += (1.0/float(n))*B
        return A

def checkDet(env, detname):
  for key in env.configStore().keys():
    if key.alias()==detname:
      return True
  for key in env.configStore().keys():
    #print key.src().__repr__(),detname,key.src().__repr__()==detname
    if key.src().__repr__()==detname:
      return True
  return False

def pumpprobe_status(evt, xrayoff=[162], laseroff=[91]):
    xfel_status, laser_status = (1,1) # default if no EVR code matches
    evr = evt.get(psana.EvrData.DataV4, psana.Source('DetInfo(NoDetector.0:Evr.0)'))
    if evr is None:
      evr = evt.get(psana.EvrData.DataV3, psana.Source('DetInfo(NoDetector.0:Evr.0)'))
      if evr is None:
        return np.nan, np.nan
      fifoEvts = [ pcode.eventCode() for pcode in evr.fifoEvents() ]
      for offcode in xrayoff:
        if offcode in fifoEvts: xfel_status = 0
      for offcode in laseroff:
        if offcode in fifoEvts: laser_status = 0
    else:
      for offcode in xrayoff:
        if evr.present(offcode): xfel_status = 0
      for offcode in laseroff:
        if evr.present(offcode): laser_status = 0

    return xfel_status, laser_status
        
def printMsg(eventNr, run):
  printFreq = 10
  #if eventNr > 10000:
  #  printFreq = 10000
  if eventNr > 1000:
    printFreq = 1000
  elif eventNr > 120:
    printFreq = 100
    
  if eventNr%printFreq == 0:
    if rank == 0:
      usage = resource.getrusage(resource.RUSAGE_SELF)
      print "*** In Event: run", run, ",event# =", eventNr,' memory used: ',usage[2]*resource.getpagesize()/1000000.,' at ',time.strftime('%X')

def getExpName(env):  
  if (env.jobName()).find('shmem')>=0:
    return RegDB.experiment_info.active_experiment('XPP')[1]
  else:
    return env.experiment()

def addPsanaCnfInfoToHdf5(fh5, cfgName, h5DsetName='cnf/'):
  fcnf = open(cfgName)
  cnftext = ''
  cnflines = []
  module='None'
  for line in fcnf.readlines():
    if (line[0:5]).find('#')<0:
      if (line.find('['))>=0:
        module=line.strip().strip('[').strip(']')
      splits = line.split("=")
      if len(splits)>1:
        name = splits[0].strip()
        value = splits[1].strip()
        cnflines.append([module ,name, value])
  for cnfpars in cnflines:
    dsetcfg = fh5.create_dataset((h5DsetName+cnfpars[0]+'/'+cnfpars[1]), (100,), dtype='S10')
    dsetcfg[...] = cnfpars[2] 
  
def getXtcavShape(dataSource, XTCAVRetrieval):
  XTCAVRetrieval.SetEnv(dataSource.env())
  nXtcav=0
  nEvt=0
  for evt in dataSource.events():
    nEvt+=1
    if not XTCAVRetrieval.SetCurrentEvent(evt):
      continue
    try:
      time,power,ok=XTCAVRetrieval.XRayPower()  
      try:
        agreement,ok=XTCAVRetrieval.ReconstructionAgreement()
        return time.shape
        break
      except:
        print 'agreement failed'
    except:
      print 'could not call xraypower'

    if nEvt > 200:
      break

  return (-1, -1)



##########################################################################################
###  helper classes & functions
##########################################################################################

def maskThres(array, cut_ADU=None, cut_rms=None):
    mask_thres=np.zeros_like(array).astype(bool)
    if cut_ADU:
        mask_thres = array>cut_ADU
    if cut_rms is not None:
        mask_thres = np.logical_and(mask_thres, array>cut_rms)
    return mask_thres

#create a mask given a list or array of ROI coordinates as input. array serves for size
def maskROI(array, ROI):
    if isinstance(ROI, list):
        ROI = np.array(ROI).reshape(ROI.shape[0]/2,2)        
    mask_ROI=np.ones_like(array).astype(bool)
    for ib, b in enumerate(ROI):
        np.rollaxis(mask_ROI, axis=ib)[:b[0],...]=False
        np.rollaxis(mask_ROI, axis=ib)[b[1]:,...]=False
    res_shape =  [r[1]-r[0] for r in ROI]
    return mask_ROI, res_shape

#this function applies the ROI mask. This assumes a rectangular mask.
def ROIarea(array, mask, shape):
    return array[mask].reshape(shape).copy()

#project data in x/y axis with mask, possibly ROI. Calculates either mean of sum, latter can be in single photon counting mode
def projection(array, mask, axis=0, maskThres=None, singlePhoton=False, mean=False):  
    if maskThres is not None:
        array[~maskThres]=0
        if singlePhoton:
            array[maskThres]=1
    if mean:
        return np.ma.masked_array(array,~mask).mean(axis=axis)
    return np.ma.masked_array(array,~mask).sum(axis=axis)        

#calculates center of mass of first 2 dim of array within ROI using the mask
def centerOfMass(array, mask):    
    array=array.squeeze()
    mask=mask.squeeze()
    if array.ndim<2:
        return np.nan, np.nan
    #why do I need to invert this?
    X, Y = np.meshgrid(np.arange(array.shape[0]), np.arange(array.shape[1]))    
    imagesums = np.sum(np.sum(np.ma.masked_array(array,   ~mask),axis=0),axis=0)
    centroidx = np.sum(np.sum(np.ma.masked_array(array*X.T, ~mask),axis=0),axis=0)
    centroidy = np.sum(np.sum(np.ma.masked_array(array*Y.T, ~mask),axis=0),axis=0)
    return centroidx/imagesums,centroidy/imagesums 
    
########################################################################################

def getLittleDataFromRunPkl(expname, run, online=False, inDir=None, outDir=None):
    #get all files ending in pkl w/ run number in ftc dir
    tmpName = '/reg/d/psdm/xpp/%s/scratch/tmp_littleDat/'%(expname)
    tmpShmemName = '/reg/neh/operator/xppopr/experiments/%s/littleData/'%(expname)
    dirName = '/reg/d/psdm/xpp/%s/hdf5/smalldata/'%(expname)
    if not os.path.isdir(dirName):
      dirName = '/reg/d/psdm/xpp/%s/ftc/'%(expname)

    fSname = 'ldat_%s_Run%i.pkl'%(expname,run)
    fnameBase = 'ldat_%s_Run%i_'%(expname,run)
    fnameBaseShmem = 'ldat__Run%i_'%(run)

    singleFileExists = False
    lds = None
    if (path.isfile(dirName + fSname)):
      print 'single file'
      singleFileExists = True
      if not online and inDir is None:
          f = open(dirName+fSname)
          return cPickle.load(f)

    filelist=[]

    if inDir is not None:
        for (dirpath, dirnames, filenames) in walk(inDir):
          for fname in filenames:
                if fname.find(fnameBase) >=0 and fname.find('.pkl')>=0:
                    filelist.append(inDir+'/'+fname)
    
    if len(filelist)<1 and not online:
        print 'no single file, look for many offline fiels'
        for (dirpath, dirnames, filenames) in walk(tmpName):
            for fname in filenames:
                if fname.find(fnameBase) >=0:
                    filelist.append(tmpName+fname)

    if len(filelist)<1:
        print 'no files in offline system or request for online files: look for many online files'
        for (dirpath, dirnames, filenames) in walk(tmpShmemName):
            for fname in filenames:
                if fname.find(fnameBaseShmem) >=0:
                    filelist.append(tmpShmemName+fname)
    filelist.sort()

    if len(filelist)<1:
      print 'we have not found any pickle files!'
      return None
        
    for filename in filelist:
        f = open(filename)
        if lds is None:                
            lds = cPickle.load(f)
        else:
            lds.add(cPickle.load(f))

    if outDir is not None:
      cPickle.dump(lds, open(outDir+fSname,"wb"))
      return lds

    if not singleFileExists and len(filelist)>0:
        cPickle.dump(lds, open(dirName+fSname,"wb"))

    return lds

def getLittleDataFromFilePkl(expname, runs):

  if not isinstance(runs, list):
    return getLittleDataFromRunPkl(expname, runs)

  lds = None
  for thisrun in runs:
    if lds is None:
      lds = getLittleDataFromRunPkl(expname, thisrun)
    else:
      lds.add(getLittleDataFromRunPkl(expname, thisrun))

    return lds

def getLittleDataFromRunHd5(expname, run):
  tmpName = '/reg/d/psdm/xpp/%s/scratch/tmp_littleDat/'%(expname)
  tmpShmemName = '/reg/neh/operator/xppopr/experiments/%s/littleData/'%(expname)
  dirName = '/reg/d/psdm/xpp/%s/hdf5/smalldata/'%(expname)
  if os.path.isdir(dirName):
    dirName = '/reg/d/psdm/xpp/%s/ftc/'%(expname)

  fSname = 'ldat_%s_Run%i.h5'%(expname,run)
  fnameBase = 'ldat_%s_Run%i_'%(expname,run)
  fnameBaseShmem = 'ldat__Run%i_'%(run)
  
  singleFileExists = False
  lds = None
  if (path.isfile(dirName + fSname)):
    print 'single file'
    singleFileExists = True
    if not online:
      f = h5py.File(dirName+fSname)
      return f

  filelist=[]
  if not online:
    print 'no single file, look for many offline fiels'
    for (dirpath, dirnames, filenames) in walk(tmpName):
      for fname in filenames:
        if fname.find(fnameBase) >=0:
          filelist.append(tmpName+fname)

  if len(filelist)<1:
    print 'no files in offline system or request for online files: look for many online files'
    for (dirpath, dirnames, filenames) in walk(tmpShmemName):
      for fname in filenames:
        if fname.find(fnameBaseShmem) >=0:
          filelist.append(tmpShmemName+fname)
  filelist.sort()

  files = []
  for fname in filelist:
    files.append(h5py.File(fname,"r"))
    
    fullkeys = []
    for key in (files[0]).keys():
      try:
        for skey in (files[0])[key].keys():
          print'%s/%s'%(key,skey)
          fullkeys.append('%s/%s'%(key,skey))
      except:
        fullkeys.append('%s'%(key))
        pass
    
  fMerged = h5py.File(filelist[0][:-11]+"_merge.h5", "w")
  for key in fullkeys:
    if key == 'cnf':
      dsetcnf = fMerged.create_dataset('cnf', [1.], dtype='f')
      dsetcnf.attrs['cnf'] = (files[0])['cnf'].attrs.values()[0]
    else:
      #get data.
      Ar = ((files[0])[key].value).tolist()
      npAr = (files[0])[key].value
      for i in range(1, len(flist)):
        arTemp = ((files[i])[key].value).tolist()
        Ar.extend(arTemp)
      arShape=()
      for i in range(0,len(npAr.shape)):
        if i == 0:
          arShape+=(len(Ar),)
        else:
          arShape+=(npAr.shape[i],)
      dset = fMerged.create_dataset(key, arShape, dtype='f')
      dset[...] = np.array(Ar)
  fMerged.close()

  return h5py.File(filelist[0][:-11]+"_merged.h5", "w")

def getLittleDataFromFileHd5(expname, runs):
  return None


def getLittleDataFromFile(expname, runs):
  data = getLittleDataFromFileHd5(expname, runs)
  if data == None:
      data = getLittleDataFromFilePkl(expname, runs)
  return data

def getLittleDataFromRun(expname, runs):
  data =  getLittleDataFromRunHd5(expname, runs)
  if data is None:
    data = getLittleDataFromRunPkl(expname, runs)
  return data

#implement cspad also for use in cspadMovie....
def getImg(evt, comSrc, comROI=None):
  thisImg = None
  #opal camera - alias
  if comSrc[0].find('opal')>=0:
    if evt.get(psana.Camera.FrameV1, psana.Source(comSrc[0])) is not None:
      thisImg = evt.get(psana.Camera.FrameV1, psana.Source(comSrc[0])).data16()
    else:
      return None
  #opal camera
  elif comSrc[0].find('Opal1000')>=0:
    if evt.get(psana.Camera.FrameV1, psana.Source('DetInfo(%s)'%comSrc[0])) is not None:
      thisImg = evt.get(psana.Camera.FrameV1, psana.Source('DetInfo(%s)'%comSrc[0])).data16()
    else:
      return None
  elif comSrc[0].find('cs140')>=0 or comSrc[0].find('Cspad2x2')>=0:
    if comSrc[0].find('cs140')>=0:
      try:
        evt.get(psana.CsPad2x2.ElementV1, psana.Source(comSrc[0]))
      except Exception, e:
        #print 'have exception: ',Exception, ' --- ',e
        return None
        
      if len(comSrc)==1:
        if evt.get(psana.CsPad2x2.ElementV1, psana.Source(comSrc[0])) is not None:
          thisImg = evt.get(psana.CsPad2x2.ElementV1, psana.Source(comSrc[0])).data()
      else:
        if evt.get(psana.CsPad2x2.ElementV1, psana.Source(comSrc[0]), comSrc[1]) is not None:
          thisImg = evt.get(psana.CsPad2x2.ElementV1, psana.Source(comSrc[0]), comSrc[1]).data()
    else:
      if len(comSrc)==1:
        if evt.get(psana.CsPad2x2.ElementV1, psana.Source('DetInfo(%s)'%comSrc[0])) is not None:
          thisImg = evt.get(psana.CsPad2x2.ElementV1, psana.Source('DetInfo(%s)'%comSrc[0])).data()
      else:
        if evt.get(psana.CsPad2x2.ElementV1, psana.Source('DetInfo(%s)'%comSrc[0]), comSrc[1]) is not None:
          thisImg = evt.get(psana.CsPad2x2.ElementV1, psana.Source('DetInfo(%s)'%comSrc[0]), comSrc[1]).data()
    
  elif comSrc[0].find('cspad')>=0 or comSrc[0].find('Cspad')>=0:
    if comSrc[0].find('cspad')>=0:
      if len(comSrc)==1:
        cspad_data = evt.get(psana.CsPad.DataV2, psana.Source(comSrc[0]))
      else:
        cspad_data = evt.get(psana.CsPad.DataV2, psana.Source(comSrc[0]), comSrc[1])
    else:
      if len(comSrc)==1:
        cspad_data = evt.get(psana.CsPad.DataV2, psana.Source('DetInfo(%s)'%comSrc[0]))
      else:
        cspad_data = evt.get(psana.CsPad.DataV2, psana.Source('DetInfo(%s)'%comSrc[0]), comSrc[1])
    if cspad_data is not None:
      q0=cspad_data.quads(0).data()
      q1=cspad_data.quads(1).data()
      q2=cspad_data.quads(2).data()
      q3=cspad_data.quads(3).data()
      thisImg = np.concatenate((q0,q1,q2,q3))
 
  else:
    print 'not an OPAL or cspad, please check or implement this detector'
    return None

  if thisImg is not None and comROI is not None:
    if len(comROI)==2:
      com_crop = thisImg[comROI[0]:comROI[1]]
    elif len(comROI)==4:
      com_crop = thisImg[comROI[0]:comROI[1],comROI[2]:comROI[3]]
    elif len(comROI)==6:
      com_crop = thisImg[comROI[0]:comROI[1],comROI[2]:comROI[3],comROI[4]:comROI[5]]
    thisImg = np.squeeze(com_crop)
    
  return thisImg

# --------------------------------------------------------------
class mergeLittleHdf5(object):
  def __init__(self,expname, inDir='./',outDir='./'):
    self.inDir = inDir
    self.outDir = outDir
    self.expname = expname
#  def merge(files, expname, run, inDir, outDir):
#    self.rmin=None
#    self.rmax=None
    
  def getFilelist(self, run, dirname):
    filelist=[]
    fnameBase = 'ldat_%s_Run%i_'%(self.expname,run)
    #if dirname.find('xppopr/experiments/')<0:
    #else:
    #  fnameBase = 'ldat__Run%i_'%(run)
    print 'dirname: ',dirname, ' BASE ',fnameBase
    for (dirpath, dirnames, filenames) in walk(dirname):
        for fname in filenames:
            if fname.find(fnameBase) >=0:
                filelist.append(dirname+fname)
    filelist.sort()
    return filelist

  def getKeys(self,h5file):
    fullkeys = []
    for key in (h5file).keys():
      try:
        for skey in (h5file)[key].keys():
          print'%s/%s'%(key,skey)
          fullkeys.append('%s/%s'%(key,skey))
      except:
        fullkeys.append('%s'%(key))
        pass
    return fullkeys    
    
  def mergeh5(self, files, run, outDir):
    print 'temporary debuggin!'
    fnameBase = 'ldat_%s_Run%i'%(self.expname,run)
    fMerged = h5py.File(outDir+fnameBase+".h5", "w")
    fullkeys = self.getKeys(files[0])
    for key in fullkeys:
      if key == 'cnf':
        dsetcnf = fMerged.create_dataset('cnf', [1.], dtype='f')
        dsetcnf.attrs['cnf'] = (files[0])['cnf'].attrs.values()[0]
      else:
            #get data.
        Ar = ((files[0])[key].value).tolist()
        npAr = (files[0])[key].value
        for i in range(1, len(files)):
          arTemp = ((files[i])[key].value).tolist()
          Ar.extend(arTemp)
        arShape=()
        for i in range(0,len(npAr.shape)):
          if i == 0:
            arShape+=(len(Ar),)
          else:
            arShape+=(npAr.shape[i],)
        if key.find('EvtID')>=0:
          print 'create dset of int32: ',key
          dset = fMerged.create_dataset(key, arShape, dtype='int32')
        else:
          print 'create dset of float: ',key
          dset = fMerged.create_dataset(key, arShape, dtype='f')
        dset[...] = np.array(Ar)
    fMerged.close()
    print 'temporary debugging - before sleep!'
    time.sleep(10)
    print 'temporary debugging - after sleep!'

  def merge(self,run):
    flist = self.getFilelist(run, self.inDir)
    print 'for expname ',self.expname,' and run ',run,' we will merge these files: ',flist
    files = []
    for fname in flist:
      files.append(h5py.File(fname,"r"))
    self.mergeh5(files, run, self.outDir)

# --------------------------------------------------------------
def Mergeh5(infiles, outfile):
  fullkeys = []
  for key in (infiles[0]).keys():
    try:
      for skey in (infiles[0])[key].keys():
        print'%s/%s'%(key,skey)
        fullkeys.append('%s/%s'%(key,skey))
    except:
      fullkeys.append('%s'%(key))
      pass

  for key in fullkeys:
    print 'key: ',key
    Ar = ((infiles[0])[key].value).tolist()
    npAr = (infiles[0])[key].value
    for i in range(1, len(infiles)):
      arTemp = ((infiles[i])[key].value).tolist()
      Ar.extend(arTemp)
    arShape=()
    for i in range(0,len(npAr.shape)):
      if i == 0:
        arShape+=(len(Ar),)
      else:
        arShape+=(npAr.shape[i],)
    if key.find('EvtID')>=0:
      print 'create dset of int32: ',key
      dset = outfile.create_dataset(key, arShape, dtype='int32')
    else:
      print 'create dset of float: ',key
      dset = outfile.create_dataset(key, arShape, dtype='f')
    dset[...] = np.array(Ar)

# --------------------------------------------------------------
def ipm_norm(do_norm, filter_ipm, filter_limit):
    """ get the diode normalisation.
    """
    ipm2 = evt.get(Lusi.IpmFexV1, Source('BldInfo(XppSb2_Ipm)'))
    ipm3 = evt.get(Lusi.IpmFexV1, Source('BldInfo(XppSb3_Ipm)'))
    ipmU0 = evt.get(Lusi.IpmFexV1, Source('BldInfo(XppEnds_Ipm0)'))
    if ipm2 is None or ipm3 is None or ipmU0 is None:
        print '*** Missing ipm data',ipm2,ipm3,ipmU0
        return 99

    NormDiode = 0

    if do_norm == 1:
        if ipmU0 != 0 and ipmU0.channel()[NormDiode] !=0:
            norm = 1./ipmU0.channel()[NormDiode]
        else:
            return 99
        
    if self.do_norm == 2 and ipm2.sum() != 0:
        norm = 1./ipm2.sum()

    if do_norm == 3 and ipm3.sum() != 0:
        norm = 1./ipm3.sum()
               
    if filter_ipm == 1 and ipmU0.channel()[NormDiode] < filter_limit:
        return 99

    if filter_ipm == 2 and ipm2.sum() < filter_limit:
        return 99

    if filter_ipm == 3 and ipm3.sum() < filter_limit:
        return 99

    return norm


class ROI_rectangle(object):
  def __init__(self,rmin=None,rmax=None,cmin=None,cmax=None):
    self.rmin=None
    self.rmax=None
    self.cmin=None
    self.cmax=None
    self.isempty = False
    self.set(rmin,rmax,cmin,cmax)
  def set(self,rmin=None,rmax=None,cmin=None,cmax=None):
    if (rmin is not None): self.rmin = rmin
    if (rmax is not None): self.rmax = rmax
    if (cmin is not None): self.cmin = cmin
    if (cmax is not None): self.cmax = cmax
    if (self.rmin == self.rmax or self.cmin==self.cmax): self.isempty = True
  def mean(self,img):
    i = img[self.rmin:self.rmax,self.cmin:self.cmax]
    return i.mean()
  def sum(self,img):
    i = img[self.rmin:self.rmax,self.cmin:self.cmax]
    return i.sum()
  def sumThres(self,img,threshold):
    i = img[self.rmin:self.rmax,self.cmin:self.cmax]
    return ((i>threshold)*i).sum()
  def max(self,img):
    i = img[self.rmin:self.rmax,self.cmin:self.cmax]
    return i.max()
  def select(self,img):
    return img[self.rmin:self.rmax,self.cmin:self.cmax]
  def projx(self,img):
    img=img[self.rmin:self.rmax,self.cmin:self.cmax]
    return img.mean(axis=0)
  def projy(self,img):
    img=img[self.rmin:self.rmax,self.cmin:self.cmax]
    return img.mean(axis=1)

#one more cut_off then nbins -> #nbins == #bincenters; bincenters[0] = hmin. 
class OnOffHisto(object):
  def __init__(self, hmin=0, hmax=1, nbins=50):
    self.hmin = hmin
    self.hmax = hmax
    self.nbins = nbins
    self.yval = np.zeros(nbins)
    self.yval_sq = np.zeros(nbins)
    self.nent = np.zeros(nbins)
    self.bin_width = np.abs(hmax-hmin/nbins)
    self._bin_cutoffs = np.linspace(self.hmin-self.bin_width/2., self.hmax-self.bin_width/2., self.nbins+1)


  @property
  def bin_cutoffs(self):
    return self._bin_cutoffs

  @property
  def bin_centers(self):
    return self.bin_cutoffs[1:] - self.bin_width/2.0

  def mpisum(self):
    self.yval_mpi = np.empty_like(self.yval)
    self.yval_sq_mpi = np.empty_like(self.yval_sq)
    self.nent_mpi = np.empty_like(self.nent)
    comm.Reduce(self.nent,self.nent_mpi)
    comm.Reduce(self.yval,self.yval_mpi)
    comm.Reduce(self.yval_sq,self.yval_sq_mpi)

  def setN(self, min, max, nbin):
    self.hmin = min
    self.hmax = max
    self.nbins = nbin
    if (max != min):
       self._bin_cutoffs = np.linspace(self.hmin-self.bin_width/2., self.hmax-self.bin_width/2., self.nbins+1)
    self.yval = np.resize(self.yval,nbin)
    self.yval_sq = np.resize(self.yval,nbin)
    self.nent = np.resize(self.nent,nbin)
    #print 'min, max, nbin: ',min,' ',max,' ',nbin,' width ',self._bin_width
    #print 'cutoffs: ',self._bin_cutoffs
    
  #think about this a little more: bins: calc from min/max or add 0.5*bin-width to that
  def setW(self, min, max, bin_width):
    self.hmin = min
    self.hmax = max
    if bin_width != 0:
      self.nbins = np.int((np.float(max+bin_width/2.) - np.float(min-bin_width/2.)) / np.float(bin_width))
      if (self.nbins < 0):
        self.nbins = -1 * self.nbins
    self.yval = np.resize(self.yval,self.nbins)
    self.yval_sq = np.resize(self.yval,self.nbins)
    self.nent = np.resize(self.nent,self.nbins)
    #self._bin_cutoffs = np.arange(min-bin_width/2., (max+bin_width/2.), bin_width)
    #the above gave an extra _bin_cutoff for -1001.2,-998.8,0.2
    self._bin_cutoffs = np.array([(min-bin_width/2.+i*bin_width) for i in range(self.nbins+1)])
    #print self._bin_cutoffs

  def setNW(self, min, nbin, bin_width):
    self.hmin = min
    self.hmax = self.hmin + nbin * bin_width
    self.yval = np.resize(self.yval,nbin)
    self.yval_sq = np.resize(self.yval,nbin)
    self.nent = np.resize(self.nent,nbin)
    self._bin_cutoffs = np.arange(min-bin_width/2., (max+bin_width/2.), bin_width)

  def getbin(self, xval):
    #normalizeValueBetweenZeroOne = (max(self.hmin,min(self.hmax,xval))-self.hmin)/float(self.hmax-self.hmin)
    #return int(min(self.nbins-1,self.nbins * normalizeValueBetweenZeroOne))
    if xval > self.hmax or xval < self.hmin:
      #print 'out of bounds'
      return -1
    else:
      #print 'XVAL: ',xval, ' --- ',self.hmin,'  -- ', self.hmax
      #print ' xval: ',xval, '  ', (xval - (self.hmin - self._bin_width/2.))/self._bin_width
      #print 'int ',np.int ((xval - (self.hmin - self._bin_width/2.))/self._bin_width)
      return np.int ((xval - (self.hmin - self.bin_width/2.))/self.bin_width)

  def mpisum(self):
    self.yval_mpi = np.empty_like(self.yval)
    self.yval_sq_mpi = np.empty_like(self.yval_sq)
    self.nent_mpi = np.empty_like(self.nent)
    comm.Reduce(self.nent,self.nent_mpi)
    comm.Reduce(self.yval,self.yval_mpi)
    comm.Reduce(self.yval_sq,self.yval_sq_mpi)

  def add(self, xval, value):
    thisbin = self.getbin(xval)
    if thisbin >=0 and thisbin < self.nbins:
    #if thisbin >=0:
      self.nent[thisbin] += 1
      self.yval[thisbin] += value
      self.yval_sq[thisbin] += value*value

  def means(self):
    non_zero_ents = copy.deepcopy(self.nent)
    non_zero_ents[non_zero_ents == 0] = 1e12
    return np.divide(self.yval, non_zero_ents)

  def mpimeans(self):
    non_zero_ents = copy.deepcopy(self.nent_mpi)
    non_zero_ents[non_zero_ents == 0] = 1e12
    return np.divide(self.yval_mpi, non_zero_ents)

  def errSq(self):
    non_zero_ents = copy.deepcopy(self.nent-1)
    non_zero_ents[non_zero_ents == 0] = 1e12
    return np.fabs(np.divide(self.yval_sq, non_zero_ents)-(self.means()*self.means()))

  def histo2json(self, fname):
    file=open(fname, 'w')
    file.write(json.dumps([self.nent.tolist(), self.yval.tolist(), self.yval_sq.tolist()]))
    file.close()
                
  def json2histo(self, fname):
    file=open(fname, 'r')
    saved_data = eval(file.read())
    self.nent = np.fromiter(saved_data[0], float)
    self.yval = np.fromiter(saved_data[1], float)
    self.yval_sq = np.fromiter(saved_data[2], float)
    file.close()
    
  def addHisto(self, histo):
    if self.nbins != histo.nbins or self.hmin != histo.hmin or self.hmax != histo.hmax:  
      print 'cannot add these histos: (',self.nbins,':',self.hmin,':',self.hmax,') -- (',histo.nbins,':',histo.hmin,':',histo.hmax,')'
    else:
      self.nent += histo.nent
      self.yval += histo.yval
      self.yval_sq += histo.yval_sq

# --------------------------------------------------------------

def fitCircle(x,y):
  def calc_R(x,y, xc, yc):
    return np.sqrt((x-xc)**2 + (y-yc)**2)

  def f(c,x,y):
    Ri = calc_R(x,y,*c)
    return Ri - Ri.mean()

  x_m = np.mean(x)
  y_m = np.mean(y)
  center_estimate = x_m, y_m
  center, ier = optimize.leastsq(f, center_estimate, args=(x,y))
  xc, yx = center
  Ri     = calc_R(x, y, *center)
  R      = Ri.mean()
  residu = np.sum((Ri - R)**2)
  return xc, yx, R, residu

# --------------------------------------------------------------
      
def normalize(q_values, intensities, q_min=0.5, q_max=3.5):
    assert q_values.shape == intensities.shape
    inds = (q_values > q_min) * (q_values < q_max)
    factor = float(np.sum(intensities[inds])) / float(np.sum(inds))
    return intensities / factor

def differential_integral(laser_on, laser_off, q_values, q_min=1.0, q_max=2.5):
    percent_diff = (laser_on - laser_off) / laser_on
    inds = (q_values > q_min) * (q_values < q_max)
    di = np.abs(np.sum( precent_diff[inds] ))
    return di

# --------------------------------------------------------------
#hit finder in a single cspad tile (for von Hamos analysis)
def hit_finder(cspad_tile, gas_detector, att, norm_cspad):
    """ Find the hits.
    """
    value = 7
    criterium = 0  # 0 - difference, 1 - ratio

    #rh = [105, 115, 132, 152]  # run 102
    #rh = [87, 97, 150, 170]    # run 3
    #rh = [109, 119, 120, 135]  # run 80
    rh = [105, 115, 130, 150]    # run 97

    rb1 = [rh[1]+10, rh[1]+10+(rh[1]-rh[0]),rh[2], rh[3]]
    rb2 = [rh[0]-10-(rh[1]-rh[0]), rh[1]-10,rh[2], rh[3]]
    hit_area = cspad_tile[rh[0]:rh[1],rh[2]:rh[3]]
    bkg1_area = cspad_tile[rb1[0]:rb1[1],rb1[2]:rb1[3]]
    bkg2_area = cspad_tile[rb2[0]:rb2[1],rb2[2]:rb2[3]]

    # sum all pixels:
    sig = float(np.sum(hit_area))
    bkg = 0.5*(np.sum(bkg1_area)+np.sum(bkg1_area))

    #print "*** ", sig, bkg, (gas_detector * att), norm_cspad

    # normalise by gas detector and att
    if (gas_detector * att) > 0:
        sig_norm_gas = sig / (gas_detector * att)
        bkg_norm_gas = bkg / (gas_detector * att)
    else:
        sig_norm_gas = 0
        bkg_norm_gas = 0
    # normmalise by cspad stripe:
    if norm_cspad > 0:
        sig_norm_cspad = sig / norm_cspad
        bkg_norm_cspad = bkg / norm_cspad
    else:
        sig_norm_cspad = 0
        bkg_norm_cspad = 0


    return sig_norm_gas, bkg_norm_gas, sig_norm_cspad, bkg_norm_cspad

    
# --------------------------------------------------------------    

class binEvents(object):
	'to bin events based on scalar values'
	def __init__(self, lb, ub, num_bins=10):
		self._min = lb
		self._max = ub
		self._img = None
		self._bin_count = np.zeros(num_bins)
		self._num_bins = num_bins

	def find_bin(self, x):
		"finds corresponding bin for scalar value x"
		idx = np.floor( self._num_bins*(x-self._min)/(self._max - self._min) )
		if idx < 0 or idx >= self._num_bins: 
			return -1
		return idx
		
	def update_bins(self, x, arr, debug = False):
		bin_idx = self.find_bin(x)
		if debug:
			print 'update_bin: ',bin_idx
		if bin_idx < 0:
			# print "*** bin index out of range!"
			return
		if arr is None:
			return
		else:
			if self._img is None:
				self._img = np.zeros((self._num_bins, np.size(arr) ), (np.array(arr)).dtype)
				if debug:
					print "from None: img is ", self._img.shape
					if not isinstance(arr, float):
                                          print "from None: arr is ", arr.shape
				print self._img.dtype
			else:
				if debug:
					print "img is ", self._img.shape
					if not isinstance(arr, float):
                                          print "arr is ", arr.shape
				self._img[bin_idx,:]+=arr
			self._bin_count[bin_idx]+=1

# --------------------------------------------------------------    

def hasKey(inkey, inh5=None, printThis=False):
    hasKey = False
    if inh5:
        for key in inh5.keys():
            for skey in inh5[key].keys():
                if inkey.find('%s/%s'%(key,skey))>=0:
                    if printThis:
                        print 'found: %s/%s in %s'%(key,skey,inkey)
                    hasKey=True
    return hasKey

def getTTstr(fh5):
  ttCorr = None
  ttBaseStr = 'tt/'
  if hasKey('tt/ttCorr',fh5):
    ttCorr = 'tt/ttCorr'
  elif hasKey('ttCorr/tt',fh5):
    ttCorr = 'ttCorr/tt'
  if not hasKey(ttBaseStr+'AMPL',fh5):
    if hasKey('tt/XPP_TIMETOOL_AMPL',fh5):
      ttBaseStr = 'tt/XPP_TIMETOOL_'
    elif hasKey('tt/TIMETOOL_AMPL',fh5):
      ttBaseStr = 'tt/TIMETOOL_'
    elif hasKey('tt/TTSPEC_AMPL',fh5):
      ttBaseStr = 'tt/TTSPEC_'
  return ttCorr, ttBaseStr

def getDelay(fh5, use_ttCorr=True, addEnc=False):
    ttCorrStr, ttBaseStr = getTTstr(fh5)
    if ttCorrStr is not None and (np.nanstd(fh5[ttCorrStr].value)>0):
        ttCorr=fh5[ttCorrStr].value
    else:
      ttCorr=fh5[ttBaseStr+'FLTPOS_PS'].value
    nomDelay=np.zeros_like(ttCorr)

    isDaqDelayScan=False
    for scanVar in fh5['scan'].keys():
        if scanVar.find('lxt')>=0 or scanVar.find('txt')>=0:
            nomDelay=fh5['scan/'+scanVar].value*1e12
            isDaqDelayScan=True
    if not isDaqDelayScan:
        if hasKey('enc/lasDelay',fh5):
          if fh5['enc/lasDelay'].value.std()>1e-3:
            nomDelay=fh5['enc/lasDelay'].value
            addEnc=False
          elif fh5['enc/lasDelay'].value.std()>1e-15:
            nomDelay=fh5['enc/lasDelay'].value*1e12
            addEnc=False
        elif hasKey('enc/ch0',fh5):
          if fh5['enc/ch0'].value.std()>1e-15 and fh5['enc/ch0'].value.std()<1e-9:
            nomDelay=fh5['enc/ch0'].value*1e12
            #now look at the EPICS PV if everything else has failed.
        else:
            epics_delay = fh5['epics/lxt_ttc'].value
            if epics_delay.std()!=0:
                nomDelay = epics_delay

    if addEnc and not hasKey('enc/lasDelay',fh5):
      print 'required to add encoder value, did not find encoder!'
    if addEnc and hasKey('enc/lasDelay',fh5):            
      if fh5['enc/lasDelay'].value.std()>1e-6:
        nomDelay+=fh5['enc/lasDelay'].value

    if use_ttCorr:
        return ttCorr+nomDelay
    else:
        return nomDelay

def addToHdf5(fh5, key, npAr):
    arShape=()
    for i in range(0,len(npAr.shape)):
        arShape+=(npAr.shape[i],)
    dset = fh5.create_dataset(key, arShape)
    dset[...] = npAr.astype(float)


def getBins(bindef=[], fh5=None, debug=False):
  #have full list of bin boundaries, just return it
  if len(bindef)>3:
    return bindef
  
  if len(bindef)==2:
    if debug:
      print 'only two bin boundaries, so this is effectively a cut...cube will have a single image'
    Bins = np.array([min(bindef[0],bindef[1]),max(bindef[0],bindef[1])])
    return Bins

  if len(bindef)==3:
    if type(bindef[2]) is int:
        Bins=np.linspace(min(bindef[0],bindef[1]),max(bindef[0],bindef[1]),bindef[2]+1,endpoint=True)
    else:
        Bins=np.arange(min(bindef[0],bindef[1]),max(bindef[0],bindef[1]),bindef[2])
    if Bins[-1]<bindef[1]:
      Bins = np.append(Bins,max(bindef[0],bindef[1]))
    return Bins

  #have no input at all, assume we have unique values in scan. If not, return empty list 
  scanVarName = ''
  if len(bindef)<=1:
    for key in fh5['scan'].keys():
      if key.find('var')<0 and key.find('none')<0:
        scanVarName = key

  if len(bindef)==0:
    if scanVarName=='':
      print 'this run is no scan, will need bins as input, quit now'
      return []
    print 'no bins as input, we will use the scan variable %s '%scanVarName

    Bins = np.unique(fh5['scan/var0'])
    if scanVarName.find('lxt')>=0:
      Bins*=1e12
    if debug:
      print 'Bins: ',Bins
    return Bins

  #give a single number (binwidth or numBin)
  if len(bindef)==1:
    #this is a "normal" scan, use scanVar
    if scanVarName!='':
      Bins = np.unique(fh5['scan/var0'])
      if scanVarName.find('lxt')>=0:
        Bins*=1e12
      valBound = [ min(Bins), max(Bins)]
      if type(bindef[0]) is int:
        Bins=np.linspace(valBound[0],valBound[1],bindef[0],endpoint=True)
      else:
        Bins=np.arange(valBound[0],valBound[1],bindef[0])
        Bins=np.append(Bins,valBound[1])
      return Bins
      
    else:
      if hasKey('enc/ch0', fh5) or hasKey('enc/lasDelay',fh5):
        if hasKey('enc/ch0', fh5):
          vals = fh5['enc/ch0'].value.squeeze()*1e12
        else:
          vals = fh5['enc/lasDelay'].value.squeeze()
        minEnc = (int(min(vals)*10.))
        if minEnc<0:
            minEnc+=-1
        minEnc /= 10.
        maxEnc = (int(max(vals)*10.)+1)/10.
        print minEnc,maxEnc,bindef[0]
        if minEnc!=maxEnc and abs(minEnc)<101 and abs(maxEnc<1001):
          if type(bindef[0]) is int:
            Bins=np.linspace(minEnc, maxEnc, bindef[0],endpoint=True)
          else:
            Bins=np.arange(minEnc, maxEnc, bindef[0])
            if Bins[-1]< maxEnc:
              Bins=np.append(Bins,maxEnc)
          if debug:
            print 'Bins....',Bins
          return Bins
        else:
          print 'you passed only one number and the this does not look like a new delay scan or a normal scan'
          return []

    print 'why am I here? I should have hit one of the if/else staments....'
    print 'you passed: ',bindef
###
# utility functions for droplet stuff
###
def gaussian(x, amp, cen, wid):
                return amp * exp(-(x-cen)**2 /(2*wid**2))
def lorentzian(x,p0,p1):
		return (p0**2)/(p0**2 + (x-p1)**2)

def neighborImg(img):
    img_up = np.roll(img,1,axis=0); img_up[0,:]=0
    img_down = np.roll(img,-1,axis=0); img_down[-1,:]=0
    img_left = np.roll(img,1,axis=1); img_left[:,0]=0
    img_right = np.roll(img,-1,axis=1); img_right[:,-1]=0
    return np.amax(np.array([img_up, img_down, img_left, img_right]),axis=0)

def cm_epix(img,rms,maxCorr=30, histoRange=30, colrow=3, minFrac=0.25, normAll=False):
    #make a mask: all pixels > 10 rms & neighbors & pixels out of historange
    imgThres = img.copy()
    imgThres[img>=rms*10]=1
    imgThres[img<rms*10]=0
    imgThres+=neighborImg(imgThres)
    imgThres+=imgThres+(abs(img)>histoRange)

    maskedImg = np.ma.masked_array(img, imgThres)
    if normAll:
      #this should be done in the 16 blocks.
      maskedImg -= maskedImg.mean()
    if colrow%2==1:
        rs = maskedImg.reshape(704/2,768*2,order='F')
        rscount = np.ma.count_masked(rs,axis=0)
        rsmed = np.ma.median(rs,axis=0)
        rsmed[abs(rsmed)>maxCorr]=0
        rsmed[rscount>((1.-minFrac)*352)]=0
        imgCorr = np.ma.masked_array((rs.data-rsmed[None,:]).data.reshape(704,768,order='F'),imgThres)
    else:
        imgCorr = maskedImg.copy()

    if colrow>=2:
        rs = imgCorr.reshape(704*8,96)
        rscount = np.ma.count_masked(rs,axis=1)
        rsmed = np.ma.median(rs,axis=1)
        rsmed[abs(rsmed)>maxCorr]=0
        rsmed[rscount>((1.-minFrac)*96)]=0
        imgCorr = (np.ma.masked_array(rs.data-rsmed[:,None], imgThres)).reshape(704,768)
                                                
    return imgCorr.data  

###
# utility functions for plotting data as 2-d histogram
###
def hist2d(ar1, ar2,limits=[1,99.5],numBins=[100,100],histLims=[np.nan,np.nan, np.nan, np.nan],weights=None, doPlot=True):
        pmin0 = np.nanmin(ar1); pmin1 = np.nanmin(ar2)
        pmax0 = np.nanmax(ar1); pmax1 = np.nanmax(ar2)
        if not np.isnan(np.percentile(ar1,limits[0])):
            pmin0 = np.percentile(ar1,limits[0])
        if not np.isnan(np.percentile(ar2,limits[0])):
            pmin1 = np.percentile(ar2,limits[0])
        if limits[1]<100:
            if not np.isnan(np.percentile(ar1,limits[1])):
                pmax0 = np.percentile(ar1,limits[1])
            if not np.isnan(np.percentile(ar2,limits[1])):
                pmax1 = np.percentile(ar2,limits[1])
        if histLims[0] is not np.nan:
            pmin0 = histLims[0]
            pmax0 = histLims[1]
            pmin1 = histLims[2]
            pmax1 = histLims[3]
        v0 = ar1
        v1 = ar2
        binEdges0 = np.linspace(pmin0, pmax0, numBins[0])
        binEdges1 = np.linspace(pmin1, pmax1, numBins[1])
        ind0 = np.digitize(v0, binEdges0)
        ind1 = np.digitize(v1, binEdges1)
        ind2d = np.ravel_multi_index((ind0, ind1),(binEdges0.shape[0]+1, binEdges1.shape[0]+1)) 
        if weights is None:
                iSig = np.bincount(ind2d, minlength=(binEdges0.shape[0]+1)*(binEdges1.shape[0]+1)).reshape(binEdges0.shape[0]+1, binEdges1.shape[0]+1) 
        else:
                iSig = np.bincount(ind2d, weights=weights, minlength=(binEdges0.shape[0]+1)*(binEdges1.shape[0]+1)).reshape(binEdges0.shape[0]+1, binEdges1.shape[0]+1)    
        if doPlot:
          plt.imshow(iSig,aspect='auto', interpolation='none',origin='lower',extent=[binEdges1[1],binEdges1[-1],binEdges0[1],binEdges0[-1]],clim=[np.percentile(iSig,limits[0]),np.percentile(iSig,limits[1])])
          plt.colorbar()
        return iSig

###
def dictToHdf5(filename, indict):
  f = h5py.File(filename,'w')
  for key in indict.keys():
    npAr = np.array(indict[key])
    dset = f.create_dataset(key, npAr.shape, dtype='f')
    dset[...] = npAr
  f.close()

