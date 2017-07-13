from os import path
import numpy as np
from pylab import ginput
from matplotlib import pyplot as plt
from matplotlib import gridspec
from matplotlib import path
import os
import psana
import LittleDataAna as lda
from utilities import fitCircle
from littleData import DetObject
from littleData import dropObject
import azimuthalBinning as ab
import RegDB.experiment_info
plt.ion()

class LittleDataAna_psana(object):
    def __init__(self, expname='', run=-1,dirname='', filename=''):
        self.run=run
        self.expname=expname
        self.hutch=expname[0:3]
        currExpname = RegDB.experiment_info.active_experiment(self.hutch.upper())[1]
        if expname==currExpname:
            lastRun = RegDB.experiment_info.experiment_runs(self.hutch.upper())[-1]['num']
            if self.run > lastRun:
                print 'experiment %s does only have %d runs, requested %d'%(expname, lastRun, run)
                return None
        self.dsnameIdx='exp=%s:run=%i:idx'%(expname,run)
        self.dsname='exp=%s:run=%i:smd'%(expname,run)
        print 'make LittleDataAna_psana from dsname: ',self.dsname
        try:
            self.ds = psana.DataSource(self.dsname)
        except:
            print 'Failed to set up small data psana dataset!'
            self.ds = None
        try:
            self.dsIdx = psana.DataSource(self.dsnameIdx)
            self.dsIdxRun = self.dsIdx.runs().next()
        except:
            print 'Failed to set up index based psana dataset'
            self.dsIdx = None
        print 'try to make littleDataAna using dirname ',dirname,' for exp: ',expname,' and run ',run
        try:
            print 'setting up littleData ana from anaps '
            self.lda = lda.LittleDataAna(expname,run,dirname=dirname, filename=filename)
        except:
            print 'failed, set anaps.lda to None'
            self.lda = None
        self.jobsIds = []

    def commonModeStr(self, common_mode=0):
        if common_mode<0:
            return 'raw_'
        elif common_mode==5:
            return 'unb_'
        elif common_mode==45:
            return 'median_'
        elif common_mode==46:
            return 'cm46_'
        elif common_mode==47:
            return 'cm47_'
        elif common_mode==10:
            return 'cm47_'
        elif common_mode==0:
            return 'pedSub_'
        else:
            return ''

    def resetDs(self, idx=True):
        if idx:
            del self.dsIdx
            self.dsIdx = psana.DataSource(self.lda.dsnameIdx)
            self.dsIdxRun = self.dsIdx.runs().next()
        else:
            del self.ds
            self.ds = psana.DataSource(self.lda.dsname)

    def Keys(self,printthis=False):
        try:
            keys=self.ds.events().next().keys()
            if printthis: 
                print keys
            else:
                return keys
        except:
            print 'could not use the smd dataset'
            times = self.dsIdxRun.times()            
            evt=self.dsIdxRun.event(times[0])
            keys=evt.keys()
            if printthis: 
                print keys
            else:
                return keys

    def CfgKeys(self,idx=True,printthis=False):
        if idx:
            keys=self.dsIdx.env().configStore().keys()
        else:
            keys=self.ds.env().configStore().keys()
        if printthis: 
            print keys
        else:
            return keys

    def EpicsAliases(self,idx=True,printthis=False):
        if idx:
            keys=self.dsIdx.env().epicsStore().aliases()
        else:
            keys=self.ds.env().epicsStore().aliases()
        if printthis: 
            print keys
        else:
            return keys
        
    def plotVar(self, plotvar, numBins=[100],setCuts=False, applyCuts=False, limits=[1,99],fig=None,asHist=False):
        self.lda.plotVar(plotvar=plotvar, numBins=numBins,setCuts=setCuts, applyCuts=applyCuts, limits=limits,fig=fig,asHist=asHist)

    def plotScan(self, ttCorr=False, sig='diodeU/channels', sigROI=[], i0='ipm3/sum', numBins=100):
        self.lda.plotScan(ttCorr=ttCorr, sig=sig, sigROI=sigROI, i0=i0, numBins=numBins)

#
# these functions need psana as well, make separate class that imports LittleDataAna?
#
    def addDetInfo(self, detname='None', common_mode=0):
        if detname=='None':
            aliases = self._getDetName()
            if len(aliases)==1:
                detname = aliases[0]
            else:
                print 'detectors in event: \n',
                for alias in aliases:
                    print alias
                detname = raw_input("Select detector to get detector info for?:\n")
        print 'try to make psana Detector with: ',detname

        #only do this if information is not in object yet
        if detname in self.__dict__.keys() and self.__dict__[detname].common_mode==common_mode:
            return detname

        if detname in self.__dict__.keys():
            print 'redefine detector object with different common mode: ',common_mode,' instead of ', self.__dict__[detname].common_mode
        det = DetObject(detname , self.dsIdx.env(), self.run, name=detname,common_mode=common_mode)
        self.__dict__[detname]=det
        if (detname+'_pedestals') in self.__dict__.keys():
            return detname
        self.__dict__[detname+'_pedestals'] = det.ped
        self.__dict__[detname+'_rms'] = det.rms
        self.__dict__[detname+'_x']=det.x
        self.__dict__[detname+'_y']=det.y
        self.__dict__[detname+'_iX']=det.iX
        self.__dict__[detname+'_iY']=det.iY
        return detname

    def _getDetName(self, detname='None'):
        if not isinstance(detname, basestring):
            print 'please give parameter name unless specifying arguments in right order. detname is first'
            return
        #look for detector
        if detname=='None':
            aliases=[]
            for key in self.Keys():
                if key.alias().find('cs')>=0 or key.alias().find('epix')>=0 or key.alias().find('opal')>=0 or key.alias().find('Epix')>=0:
                    aliases.append(key.alias())
            if len(aliases)<1:
                print 'no cs, epix or opal in aliases, look at source'
                for key in self.Keys():
                    if key.src().__repr__().find('cs')>=0 or key.src().__repr__().find('Cs')>=0 or key.src().__repr__().find('Ep')>=0 or key.src().__repr__().find('Opal')>=0:
                        aliases.append(key.src().__repr__())
            if len(aliases)==1:
                detname = aliases[0]
            else:
                return aliases

    def AvImage(self, detname='None', numEvts=100, thresADU=0., thresRms=0., useLdat=False, nSkip=0,minIpm=-1., common_mode=0, std=False, printFid=False):
        if not isinstance(detname, basestring):
            print 'please give parameter name unless specifying arguments in right order. detname is first'
            return
        #look for detector
        if detname=='None':
            detname = self._getDetName()
            if isinstance(detname, list):
                print 'detectors in event: \n',
                for alias in detname:
                    print alias
                detname = raw_input("Select detector to get detector info for?:\n")

        if not detname in self.__dict__.keys() or self.__dict__[detname].common_mode!=common_mode:
            self.addDetInfo(detname=detname, common_mode=common_mode)
        det=self.__dict__[detname]
        rms = self.__dict__[detname+'_rms']
        pedestals = self.__dict__[detname+'_pedestals']
        iX = self.__dict__[detname+'_iX']
        iY = self.__dict__[detname+'_iY']

        if detname.find('opal')>=0:
            common_mode = -1
            if pedestals[0,0]==-1:
                print 'time tool opal, image was not saved. Should ideally exclude from detector list'
                return
        else:
            print 'done setting up the geometry'

        #now get the non-image data
        imgAr = []
        run = self.dsIdxRun
        times=[]
        if self.lda is None or 'fh5' not in self.lda.__dict__.keys():
        #if 'fh5' not in self.lda.__dict__.keys():
            useLdat=False
        if useLdat:
            evttsSel = self.lda.getSelIdx()
            for evtts in evttsSel[nSkip:min(nSkip+numEvts, len(evttsSel))]:
                times.append(psana.EventTime(int(evtts[1][0]<<32|evtts[1][1]),int(evtts[0])))
        else:
            times = run.times()[nSkip:]
        print 'requested ',numEvts,' used ',min(len(times),numEvts), ' now actually get events'
        if (min(len(times),numEvts) < numEvts*0.5):
            print 'to few events'
            return

        for tm in times:
            #print 'numEvts ',numEvts
            if numEvts<=0:
                break
            evt=run.event(tm)
            if minIpm!=-1 and ( (self.hutch=='xpp' and evt.get(psana.Lusi.IpmFexV1, psana.Source('BldInfo(XppSb2_Ipm)')).sum() < minIpm) or (self.hutch=='xcs' and evt.get(psana.Lusi.IpmFexV1, psana.Source('BldInfo(XCS-IPM-05)')).sum() < minIpm)):
                continue
            if printFid:
                print (evt.get(psana.EventId)).fiducials()
            aliases = [ k.alias() for k in evt.keys() ]
            if not detname in aliases:
                continue

            det.evt = dropObject()
            det.getData(evt)
            data = det.evt.dat.copy()
            if det.mask is not None:
                data[det.mask==0]=0
            if thresADU != 0:
                data[data<abs(thresADU)]=0
                if thresADU < 0:
                    data[data>=abs(thresADU)]=1
            if thresRms != 0:
                data[data<abs(thresRms)*rms]=0
                if thresRms < 0:
                    data[data>=abs(thresRms)*rms]=1
            imgAr.append(data)                      
            numEvts-=1

        #make array
        data='AvImg_'
        img = np.array(imgAr)
        if std:
            img = img.std(axis=0)
        elif thresADU >= 0 and thresRms >=0:
            img = img.mean(axis=0)
        else:
            img = img.sum(axis=0)

        if thresADU!=0:
            data+='thresADU%d_'%int(thresADU)
        if thresRms!=0:
            data+='thresRms%d_'%int(thresRms*10.)
        if std:
            data+='std_'

        print 'use common mode: ',common_mode
        data+=self.commonModeStr(common_mode)

        data+=detname
        self.__dict__[data]=img

    def getAvImage(self,detname=None, imgName=None):
        avImages=[]
        for key in self.__dict__.keys():
            if key.find('_mask_')>=0:
                continue
            if key.find('_azint_')>=0:
                continue
            if imgName is not None and key.find(imgName)<0:
                continue
            if key.find('AvImg')>=0:
                if detname is not None and key.find(detname)>=0:
                    avImages.append(key)
                elif detname is None:
                    avImages.append(key)
        if len(avImages)==0:
            print 'please create the AvImage first!'
            return
        elif len(avImages)>1:
            print 'we have the following options: ',avImages
            avImage=raw_input('type the name of the AvImage to use:')
        else:
            avImage=avImages[0]
        detname = self._getDetname_from_AvImage(avImage)
        img = self.__dict__[avImage]
        return detname, img, avImage

    def getAzInt(self,detname=None):
        azInts=[]
        for key in self.__dict__.keys():
            if key.find('_mask_')>=0:
                continue
            print 'key ',key
            if key.find('azint')>=0:
                if detname is not None and key.find(detname)>=0:
                    azInts.append(key)
                elif detname is None:
                    azInts.append(key)
        if len(azInts)==0:
            print 'please create an azimuthal integral first!'
            return
        elif len(azInts)>1:
            print 'we have the following options: ',azInts
            avInt=raw_input('type the name of the AvImage to use:')
        else:
            avInt=azInts[0]
        detname = self._getDetname_from_AvImage(avInt.replace('_azint_',''))
        values = self.__dict__[avInt]
        #azavName = 'azav'
        #bins = self.__dict__[detname].__dict__[azavName+'_q']
        return detname, values, avInt

    def _getDetname_from_AvImage(self,avimage):
        detname=''
        dns = avimage.replace('AvImg_','').replace('std_','').replace('median_','').replace('pedSub_','').replace('cm46_','').replace('raw_','').replace('unb_','').split('_')
        for ddns in dns:
            if ddns.find('thres')<0:
                detname+=ddns;detname+='_'
        if detname[-1]=='_':
            detname = detname[:-1]
        return detname

    def plotAvImage(self,detname=None, use_mask=False, ROI=[], limits=[5,99.5], returnIt=False):
        detname, img, avImage = self.getAvImage(detname=None)

        if use_mask:
            mask = self.__dict__[detname].det.mask_calib(self.run)
            img = (img*mask)

        plotMax = np.percentile(img, limits[1])
        plotMin = np.percentile(img, limits[0])
        print 'plot %s using the %g/%g percentiles as plot min/max: (%g, %g)'%(avImage,limits[0],limits[1],plotMin,plotMax)

        if len(img.shape)>2:
            image = self.__dict__[detname].det.image(self.run, img)
        else:
            image = img

        fig=plt.figure(figsize=(10,6))
        if ROI!=[]:
            gs=gridspec.GridSpec(1,2,width_ratios=[2,1])        
            plt.subplot(gs[1]).imshow(img[ROI[0][0],ROI[1][0]:ROI[1][1],ROI[2][0]:ROI[2][1]],clim=[plotMin,plotMax],interpolation='None')
        else:
            gs=gridspec.GridSpec(1,2,width_ratios=[99,1])        
        plt.subplot(gs[0]).imshow(image,clim=[plotMin,plotMax],interpolation='None')
        plt.title(avImage)
        plt.show()
        if returnIt:
            return image
                     
    def SelectRegion(self,detname=None, limits=[5,99.5]):
        avImages=[]
        for key in self.__dict__.keys():
            if key.find('AvImg')>=0:
                if detname is not None and key.find(detname)>=0:
                    avImages.append(key)
                elif detname is None:
                    avImages.append(key)
        if len(avImages)==0:
            print 'please create the AvImage first!'
            return
        elif len(avImages)>1:
            print 'we have the following options: ',avImages
            avImage=raw_input('type the name of the AvImage to use:')
        else:
            avImage=avImages[0]
        detname = self._getDetname_from_AvImage(avImage)
        img = self.__dict__[avImage]
        #print img.shape

        plotMax = np.percentile(img, limits[1])
        plotMin = np.percentile(img, limits[0])
        print 'plot %s using the %g/%g percentiles as plot min/max: (%g, %g)'%(avImage,limits[0],limits[1],plotMin,plotMax)

        fig=plt.figure(figsize=(10,6))
        gs=gridspec.GridSpec(1,2,width_ratios=[2,1])

        needsGeo=False
        if self.__dict__[detname].ped.shape != self.__dict__[detname].imgShape:
            needsGeo=True

        if needsGeo:
            image = self.__dict__[detname].det.image(self.run, img)
        else:
            image = img

        plt.subplot(gs[0]).imshow(image,clim=[plotMin,plotMax],interpolation='None')

        iX = self.__dict__[detname+'_iX']
        iY = self.__dict__[detname+'_iY']

        happy = False
        while not happy:
            p =np.array(ginput(2))
            plt.subplot(gs[1]).imshow(image[p[:,1].min():p[:,1].max(),p[:,0].min():p[:,0].max()],clim=[plotMin,plotMax],interpolation='None')
            if needsGeo:
                mask_roi=np.zeros_like(image)
                mask_roi[p[:,1].min():p[:,1].max(),p[:,0].min():p[:,0].max()]=1
                mask_nda = np.array( [mask_roi[ix, iy] for ix, iy in zip(iX,iY)] )
            if raw_input("Happy with this selection:\n") in ["y","Y"]:
                happy = True
                    
        if not needsGeo:
            print 'ROI: [[%i,%i], [%i,%i]]'%(p[:,1].min(),p[:,1].max(),p[:,0].min(),p[:,0].max())
            return

        if len(mask_nda.shape)>2:
            for itile,tile in enumerate(mask_nda):
                if tile.sum()>0:
                    ax0 = np.arange(0,tile.sum(axis=0).shape[0])[tile.sum(axis=0)>0]
                    ax1 = np.arange(0,tile.sum(axis=1).shape[0])[tile.sum(axis=1)>0]
                    print 'ROI: [[%i,%i], [%i,%i], [%i,%i]]'%(itile,itile+1,ax1.min(),ax1.max(),ax0.min(),ax0.max())
                    fig=plt.figure(figsize=(6,6))
                    plt.imshow(img[itile,ax1.min():ax1.max(),ax0.min():ax0.max()],interpolation='none')
                    plt.show()
        else:
            tile=mask_nda
            if tile.sum()>0:
                ax0 = np.arange(0,tile.sum(axis=0).shape[0])[tile.sum(axis=0)>0]
                ax1 = np.arange(0,tile.sum(axis=1).shape[0])[tile.sum(axis=1)>0]
                print 'ROI: [[%i,%i], [%i,%i]]'%(ax1.min(),ax1.max(),ax0.min(),ax0.max())
            

    def FitCircle(self, detname=None, use_mask=False, use_mask_local=True, limits=[5,99.5]):
        detname, img, avImage = self.getAvImage(detname=None)

        if use_mask:
            mask = self.__dict__[detname].det.mask_calib(self.run)
            img = (img*mask)

        if use_mask_local:
            if self.__dict__.has_key('_mask_'+avImage):
                mask = self.__dict__['_mask_'+avImage]
                img = (img*mask)
            else:
                maskName = raw_input('no local mask defined for %s, please enter file name '%avImage)
                
                if os.path.isfile(maskName):
                    locmask=np.loadtxt(maskName)
                    if self.__dict__[detname].x is not None and locmask.shape != self.__dict__[detname].x.shape:
                        if locmask.shape[1] == 2:
                            locmask = locmask.transpose(1,0)
                        locmask = locmask.reshape(self.__dict__[detname].x.shape)
                    self.__dict__['_mask_'+avImage] = locmask
                img = (img*locmask)

        plotMax = np.percentile(img[img!=0], 99.5)
        plotMin = np.percentile(img[img!=0], 5)
        print 'plot %s using the %g/%g percentiles as plot min/max: (%g, %g)'%(avImage,limits[0],limits[1],plotMin,plotMax)


        needsGeo=False
        if self.__dict__[detname].ped is not None and self.__dict__[detname].ped.shape != self.__dict__[detname].imgShape:
            needsGeo=True

        if needsGeo:
            image = self.__dict__[detname].det.image(self.run, img)
        else:
            image = img

        x = self.__dict__[detname+'_x']
        y = self.__dict__[detname+'_y']
        if x is None:
            x = np.arange(0, image.shape[1])
            y = np.arange(0, image.shape[0])
            x,y = np.meshgrid(x,y)
        extent=[x.min(), x.max(), y.min(), y.max()]

        if raw_input("Select Circle Points by Mouse?:\n") in ["y","Y"]:
            fig=plt.figure(figsize=(10,10))
            if needsGeo:
                plt.imshow(np.rot90(image),extent=extent,clim=[plotMin,plotMax],interpolation='None')
            else:
                plt.imshow(image,extent=extent,clim=[plotMin,plotMax],interpolation='None')
            happy = False
            while not happy:
                points=ginput(n=0)
                parr=np.array(points)
                #res: xc, yc, R, residu
                res = fitCircle(parr[:,0],parr[:,1])
                #draw the circle.
                circle = plt.Circle((res[0],res[1]),res[2],color='b',fill=False)
                plt.gca().add_artist(circle)
                plt.plot([res[0],res[0]],[y.min(),y.max()],'r')
                plt.plot([x.min(),x.max()],[res[1],res[1]],'r')

                if raw_input("Happy with this selection:\n") in ["y","Y"]:
                    happy = True
                print 'x,y: ',res[0],res[1],' R ',res[2]

        elif raw_input("Select Circle Points with threshold (y/n):\n") in ["y","Y"]:
            fig=plt.figure(figsize=(10,10))
            plt.imshow(image,extent=extent,clim=[plotMin,plotMax],interpolation='None')
            happy = False
            while not happy:
                thres = float(raw_input("min percentile % of selected points:\n"))
                thresP = np.percentile(img[img!=0], thres)
                print 'thresP',thresP
                imageThres=image.copy()
                imageThres[image>thresP]=1
                imageThres[image<thresP]=0
                fig=plt.figure(figsize=(5,5))
                plt.imshow(imageThres,clim=[-0.1,1.1])
                if raw_input("Happy with this threshold (y/n):\n") in ["y","Y"]:
                    happy=True

            #print 'DEBUG: ',x.shape,y.shape,img.shape
            res = fitCircle(x.flatten()[img.flatten()>thresP],y.flatten()[img.flatten()>thresP])
            circleM = plt.Circle((res[0],res[1]),res[2],color='b',fill=False)
            fig=plt.figure(figsize=(10,10))
            if needsGeo:
                plt.imshow(np.rot90(image),extent=extent,clim=[plotMin,plotMax],interpolation='None')
            else:
                plt.imshow(image,extent=extent,clim=[plotMin,plotMax],interpolation='None')
            plt.gca().add_artist(circleM)
            plt.plot([res[0],res[0]],[y.min(),y.max()],'r')
            plt.plot([x.min(),x.max()],[res[1],res[1]],'r')
            print 'x,y: ',res[0],res[1],' R ',res[2]
    
            plt.show()

    def FitCircleThreshold(self, thresHold=None, detname=None, use_mask=False, use_mask_local=True, limits=[5,99.5], plotIt=False):
        detname, img, avImage = self.getAvImage(detname=None)

        plotMax = np.percentile(img, 99.5)
        plotMin = np.percentile(img, 5)
        print 'plot %s using the %g/%g percentiles as plot min/max: (%g, %g)'%(avImage,limits[0],limits[1],plotMin,plotMax)

        if use_mask:
            mask = self.__dict__[detname].det.mask_calib(self.run)
            img = (img*mask)

        if use_mask_local:
            if self.__dict__.has_key('_mask_'+avImage):
                mask = self.__dict__['_mask_'+avImage]
                img = (img*mask)
            else:
                print 'no local mask defined for ',avImage

        needsGeo=False
        if self.__dict__[detname].ped is not None and self.__dict__[detname].ped.shape != self.__dict__[detname].imgShape:
            needsGeo=True

        if needsGeo:
            image = self.__dict__[detname].det.image(self.run, img)
        else:
            image = img

        x = self.__dict__[detname+'_x']
        y = self.__dict__[detname+'_y']
        if x is None:
            x = np.arange(0, image.shape[1])
            y = np.arange(0, image.shape[0])
            x,y = np.meshgrid(x,y)
        extent=[x.min(), x.max(), y.min(), y.max()]

        if plotIt:
            fig=plt.figure(figsize=(10,10))
            plt.imshow(image,extent=extent,clim=[plotMin,plotMax],interpolation='None')
        happy = False
        while not happy:
            if thresHold is None:
                thresHold = float(raw_input("min percentile % of selected points:\n"))
            thresP = np.percentile(img, thresHold)
            print 'thresP',thresP
            imageThres=image.copy()
            imageThres[image>thresP]=1
            imageThres[image<thresP]=0
            if plotIt:
                fig=plt.figure(figsize=(5,5))
                plt.imshow(imageThres,clim=[-0.1,1.1])
                if raw_input("Happy with this threshold (y/n):\n") in ["y","Y"]:
                    happy=True
            else:
                happy=True

        #print 'DEBUG: ',x.shape,y.shape,img.shape
        res = fitCircle(x.flatten()[img.flatten()>thresP],y.flatten()[img.flatten()>thresP])
        circleM = plt.Circle((res[0],res[1]),res[2],color='b',fill=False)
        if plotIt:
            fig=plt.figure(figsize=(10,10))
            if needsGeo:
                plt.imshow(np.rot90(image),extent=extent,clim=[plotMin,plotMax],interpolation='None')
            else:
                plt.imshow(image,extent=extent,clim=[plotMin,plotMax],interpolation='None')
            plt.gca().add_artist(circleM)
            plt.plot([res[0],res[0]],[y.min(),y.max()],'r')
            plt.plot([x.min(),x.max()],[res[1],res[1]],'r')
        print 'x,y: ',res[0],res[1],' R ',res[2]
    
        if plotIt:
            plt.show()

        return res[0], res[1], res[2]

    def MakeMask(self, detname=None, limits=[5,99.5]):
        detname, img, avImage = self.getAvImage(detname=None)

        plotMax = np.percentile(img, limits[1])
        plotMin = np.percentile(img, limits[0])
        print 'plot %s using the %g/%g percentiles as plot min/max: (%g, %g)'%(avImage,limits[0],limits[1],plotMin,plotMax)

        needsGeo=False
        if self.__dict__[detname].ped.shape != self.__dict__[detname].imgShape:
            needsGeo=True

        if needsGeo:
            image = self.__dict__[detname].det.image(self.run, img)
        else:
            image = img

        det = self.__dict__[detname].det
        x = self.__dict__[detname+'_x']
        y = self.__dict__[detname+'_y']
        if x is None:
            xVec = np.arange(0, image.shape[1])
            yVec = np.arange(0, image.shape[0])
            x, y = np.meshgrid(xVec, yVec)
        iX = self.__dict__[detname+'_iX']
        iY = self.__dict__[detname+'_iY']
        extent=[x.min(), x.max(), y.min(), y.max()]

        fig=plt.figure(figsize=(10,6))
        from matplotlib import gridspec
        gs=gridspec.GridSpec(1,2,width_ratios=[2,1])
        
        mask=[]
        mask_r_nda=None
        select=True
        while select:
            plt.subplot(gs[0]).imshow(image,clim=[plotMin,plotMax],interpolation='None')

            shape = raw_input("rectangle(r), circle(c), polygon(p), dark(d) or noise(n)?:\n")
            #this definitely works for the rayonix...
            if shape=='r':
                print 'select two corners: '
                p =np.array(ginput(2))
                mask_roi=np.zeros_like(image)
                mask_roi[p[:,1].min():p[:,1].max(),p[:,0].min():p[:,0].max()]=1
                if needsGeo:
                    mask_r_nda = np.array( [mask_roi[ix, iy] for ix, iy in zip(iX,iY)] )
                    plt.subplot(gs[1]).imshow(det.image(self.run,mask_r_nda))
                else:
                    mask_r_nda = mask_roi
                    plt.subplot(gs[1]).imshow(mask_r_nda)
                print 'mask from rectangle (shape):',mask_r_nda.shape
            elif shape=='c':
                plt.subplot(gs[0]).imshow(np.rot90(image),clim=[plotMin,plotMax],interpolation='None',extent=(x.min(),x.max(),y.min(),y.max()))
                if raw_input("Select center by mouse?\n") in ["y","Y"]:
                    c=ginput(1)
                    cx=c[0][0];cy=c[0][1]
                    print 'center: ',cx,' ',cy
                else:
                    ctot = raw_input("center (x y)?\n")
                    c = ctot.split(' ');cx=float(c[0]);cy=float(c[1]);
                if raw_input("Select outer radius by mouse?\n") in ["y","Y"]: 
                    r=ginput(1)
                    rox=r[0][0];roy=r[0][1]
                    ro=np.sqrt((rox-cx)**2+(roy-cy)**2)
                    if raw_input("Select inner radius by mouse (for donut-shaped mask)?\n") in ["y","Y"]:
                        r=ginput(1)
                        rix=r[0][0];riy=r[0][1]
                        ri=np.sqrt((rix-cx)**2+(riy-cy)**2)
                    else:
                        ri=0
                    print 'radii: ',ro,' ',ri
                else:
                    rtot = raw_input("radii (r_outer r_inner)?\n")
                    r = rtot.split(' ');ro=float(r[0]);ri=max(0.,float(r[1]));        
                mask_router_nda = np.array( [(ix-cx)**2+(iy-cy)**2<ro**2 for ix, iy in zip(x,y)] )
                mask_rinner_nda = np.array( [(ix-cx)**2+(iy-cy)**2<ri**2 for ix, iy in zip(x,y)] )
                mask_r_nda = mask_router_nda&~mask_rinner_nda
                print 'mask from circle (shape):',mask_r_nda.shape
                if needsGeo:
                    plt.subplot(gs[1]).imshow(det.image(self.run,mask_r_nda))
                else:
                    plt.subplot(gs[1]).imshow(mask_r_nda)
            elif shape=='p':
                if needsGeo:
                    plt.subplot(gs[0]).imshow(np.rot90(image),clim=[plotMin,plotMax],interpolation='None',extent=(x.min(),x.max(),y.min(),y.max()))
                elif det.dettype==13:
                    plt.subplot(gs[0]).imshow(np.rot90(image),clim=[plotMin,plotMax],interpolation='None',extent=(x.min(),x.max(),y.min(),y.max()))
                elif det.dettype==19:
                    #plt.subplot(gs[0]).imshow(np.rot90(image),clim=[plotMin,plotMax],interpolation='None',extent=(x.min(),x.max(),y.min(),y.max()))
                    plt.subplot(gs[0]).imshow(image,clim=[plotMin,plotMax],interpolation='None',extent=(x.min(),x.max(),y.min(),y.max()))
                else:
                    plt.subplot(gs[0]).imshow(image,clim=[plotMin,plotMax],interpolation='None',extent=(x.min(),x.max(),y.min(),y.max()))
                nPoints = int(raw_input("Number of Points (-1 until middle mouse click)?\n"))
                p=np.array(ginput(nPoints))
                print p
                mpath=path.Path(p)
                all_p = np.array([ (ix,iy) for ix,iy in zip(x.flatten(),y.flatten()) ] )
                mask_r_nda = np.array([mpath.contains_points(all_p)]).reshape(x.shape)
                if needsGeo:
                    plt.subplot(gs[1]).imshow(det.image(self.run,mask_r_nda))
                else:
                    plt.subplot(gs[1]).imshow(mask_r_nda)
                print 'mask from polygon (shape):',mask_r_nda.shape
                print 'not implemented yet....'
            elif shape=='d' or shape=='n':
                figDark=plt.figure(figsize=(11,6))
                gsPed=gridspec.GridSpec(1,2,width_ratios=[1,1])
                if shape=='d':
                    pedResult = det.pedestals(self.run)
                    hstPed = np.histogram(pedResult.flatten(), np.arange(0, pedResult.max()*1.05))
                else:
                    pedResult = det.rms(self.run)
                    hstPed = np.histogram(pedResult.flatten(), np.arange(0, pedResult.max()*1.05,0.05))
                if needsGeo:
                    pedResultImg = det.image(self.run,pedResult)
                else:
                    pedResultImg = pedResult.copy()
                plt.subplot(gsPed[0]).imshow(pedResultImg,clim=[np.percentile(pedResult,1),np.percentile(pedResult,99)])
                plt.subplot(gsPed[1]).plot(hstPed[1][:-1],np.log(hstPed[0]),'o')
                if raw_input("Select range by mouse?\n") in ["y","Y"]: 
                    c=ginput(2)
                    pedMin=c[0][0];pedMax=c[1][0]
                else:
                    ctot=raw_input("Enter allowed pedestal range (min max)")
                    c = ctot.split(' ');pedMin=float(c[0]);pedMax=float(c[1]);
                mask_r_nda=np.zeros_like(pedResult)
                print mask_r_nda.sum()
                mask_r_nda[pedResult<pedMin]=1
                mask_r_nda[pedResult>pedMax]=1
                print mask_r_nda.sum()
                mask_r_nda = (mask_r_nda.astype(bool)).astype(int)
                print mask_r_nda.sum()
                if needsGeo:
                    plt.subplot(gs[1]).imshow(det.image(self.run,mask_r_nda.astype(bool)))
                else:
                    plt.subplot(gs[1]).imshow(mask_r_nda.astype(bool))

            if mask_r_nda is not None:
                print 'created a mask....',len(mask)
                mask.append(mask_r_nda.astype(bool).copy())
                countMask=1
                totmask_nm1 = mask[0]
                for thismask in mask[1:-1]:
                    totmask_nm1 = np.logical_or(totmask_nm1,thismask)
                    countMask+=1
                if len(mask)>1:
                    totmask = np.logical_or(totmask_nm1,mask[-1])
                    countMask+=1
                else:
                    totmask = totmask_nm1
            print 'masked in this step: ',np.ones_like(x)[mask_r_nda.astype(bool)].sum()
            print 'masked up to this step: ',np.ones_like(x)[totmask_nm1].sum()
            print 'masked tot: ',np.ones_like(x)[totmask].sum()

            if len(mask)>1:
                fig=plt.figure(figsize=(13,6))
                gs2=gridspec.GridSpec(1,2,width_ratios=[1,1])
                plt.show()
                image_mask = img.copy(); image_mask[totmask]=0;
                #image_mask_nm1 = img.copy(); image_mask_nm1[totmask_nm1]=0;
                #print 'DEBUG: ',(img-image_mask_nm1).sum(), (img-image_mask).sum()
                plt.subplot(gs2[0]).imshow(image,clim=[plotMin,plotMax])
                if needsGeo:
                    plt.subplot(gs2[1]).imshow(det.image(self.run,image_mask),clim=[plotMin,plotMax])
                else:
                    plt.subplot(gs2[1]).imshow(image_mask,clim=[plotMin,plotMax])
            else:
                fig=plt.figure(figsize=(10,6))
                plt.show()
                image_mask = img.copy(); image_mask[totmask]=0;
                if needsGeo:
                    plt.imshow(det.image(self.run,image_mask),clim=[plotMin,plotMax])
                else:
                    plt.imshow(image_mask,clim=[plotMin,plotMax])
                

            if raw_input("Add this mask?\n") in ["n","N"]:
                mask = mask[:-1]

            if len(mask)>0:
                #remake the image with mask up to here.
                totmask = mask[0]
                for thismask in mask[1:]:
                    totmask = np.logical_or(totmask,thismask)
                image_mask = img.copy(); image_mask[totmask]=0;
                if needsGeo:
                    image = self.__dict__[detname].det.image(self.run, image_mask)
                else:
                    image = image_mask

            if raw_input("Done?\n") in ["y","Y"]:
                select = False

        #end of mask creating loop
        if len(mask)==0:
            return
        totmask = mask[0]
        for thismask in mask[1:]:
            totmask = np.logical_or(totmask,thismask)

        if raw_input("Invert [y/n]? (n/no inversion: masked pixels will get rejected)?\n") in ["y","Y"]:
            totmask = (totmask.astype(bool)).astype(int)
        else:
            totmask = (~(totmask.astype(bool))).astype(int)
        print 'edited code....'
        self.__dict__['_mask_'+avImage]=totmask

        if  det.dettype == 2:
            mask=totmask.reshape(2,185*388).transpose(1,0)
        elif det.dettype == 1:
            mask=totmask.reshape(32*185,388)
        elif det.dettype == 13:
            mask=totmask.reshape(704,768)
        else:
            mask=totmask
        #2x2 save as 71780 lines, 2 entries
        #cspad save as 5920 lines, 388 entries
        if raw_input("Save to calibdir?\n") in ["y","Y"]:
            srcStr=det.source.__str__().replace('Source("DetInfo(','').replace(')")','')
            if det.dettype==2:
                dirname='/reg/d/psdm/%s/%s/calib/CsPad2x2::CalibV1/%s/pixel_mask/'%(self.lda.expname[:3],self.lda.expname,srcStr)
            elif det.dettype==1:
                dirname='/reg/d/psdm/%s/%s/calib/CsPad::CalibV1/%s/pixel_mask/'%(self.lda.expname[:3],self.lda.expname,srcStr)        
            elif det.dettype==13:
                dirname='/reg/d/psdm/%s/%s/calib/Epix100a::CalibV1/%s/pixel_mask/'%(self.lda.expname[:3],self.lda.expname,srcStr)
            elif det.dettype==19:
                dirname='/reg/d/psdm/%s/%s/calib/Camera::CalibV1/%s/pixel_mask/'%(self.lda.expname[:3],self.lda.expname,srcStr)        
            if not os.path.exists(dirname):
                os.makedirs(dirname)
            fname='%s-end.data'%self.run
            np.savetxt(dirname+fname,mask)
        elif raw_input("Save to local?\n") in ["y","Y"]:
            np.savetxt('Mask_%s_%s_Run%03d.data'%(avImage,self.lda.expname,int(self.run)),mask)
        return mask
         
    def addAzInt(self, detname=None, phiBins=1, qBin=0.01, eBeam=9.5, center=None, dis_to_sam=None, name='azav'):
        detname, img, avImage = self.getAvImage(detname=None)
        if dis_to_sam==None:
            dis_to_sam=float(raw_input('please enter the detector distance'))
        if center==None or len(center)!=2:
            centerString=raw_input('please enter the coordinates of the beam center as c1,c2 or [c1,c2]:')
            center=[int(centerString.replace('[','').replace(']','').split(',')[0]),
                    int(centerString.replace('[','').replace(']','').split(',')[1])]
        self.__dict__[detname].addAzAv(phiBins=phiBins, qBin=qBin, center=center, dis_to_sam=dis_to_sam, eBeam=eBeam, azavName=name)

    def getAzAvs(self,detname=None):
      if detname is None:
        detname, img, avImage = self.getAvImage(detname=None)   
        if detname is None:
          return
      azintArray = [ self.__dict__[detname][key] for key in self.__dict__[detname].__dict__.keys() if isinstance(self.__dict__[detname][key], ab.azimuthalBinning) ]
      azintNames = [ key for key in self.__dict__[detname].__dict__.keys() if isinstance(self.__dict__[detname][key], ab.azimuthalBinning) ]
      return azintNames, azintArray

    def AzInt(self, detname=None, use_mask=False, use_mask_local=False, plotIt=False, azintName=None, data=None, imgName=None):
        avImage=None
        if data is not None:
            if detname is None:
                detname=raw_input('type the name detector alias')
            img=data
        else:
            detname, img, avImage = self.getAvImage(detname=detname, imgName=None)
        if use_mask:
            mask = self.__dict__[detname].det.mask_calib(self.run)
            img = (img*mask)
        if use_mask_local:
            if avImage is None:
                detname_dump, img_dump, avImage = self.getAvImage(detname=detname)
            if self.__dict__.has_key('_mask_'+avImage):
                mask = self.__dict__['_mask_'+avImage]
                img = (img*mask)
            else:
                print 'no local mask defined for ',avImage

        azIntNames,azIntegrations = self.getAzAvs(detname)
        if len(azIntegrations)>1:
            if azintName is None:
                print 'we have the following options: ',azIntNames
                azintName=raw_input('type the name of the Azimuthal integral to use:')
            azIntegs = [ iiaz for iName, iiaz in zip(azIntNames,azIntegrations) if iName==azintName]
            azInteg = azIntegs[0]
        else:
            azInteg = azIntegrations[0]
            azintName = azIntNames[0]
        azintValues = azInteg.doCake(img).squeeze()
        self.__dict__['_azint_'+azintName] = azintValues
        if plotIt:
            fig=plt.figure(figsize=(8,5))
            if len(azintValues.shape)==1:
                plt.plot(self.__dict__[detname].__dict__[azintName+'_q'],azintValues,'o')
            elif len(azintValues.shape)==2:
                plt.imshow(azintValues,aspect='auto',interpolation='none')
                plt.colorbar()
        else:
            return azintValues

    def plotAzInt(self, detname=None, azintName=None):
        detname, img, avImage = self.getAvImage(detname=detname)
        azIntNames,azIntegrations = self.getAzAvs(detname)
        azint=''
        if len(azIntegrations)>1:
            if azintName is None:
                print 'we have the following options: ',azIntNames
                azintName=raw_input('type the name of the Azimuthal integral to use:')
            azIntegs = [ iiaz for iName, iiaz in zip(azIntNames,azIntegrations) if iName==azintName]
            azInteg = azIntegs[0]
            azint = azintName
        else:
            azInteg = azIntegrations[0]
            azint = azIntNames[0]
        if azint=='':
            print 'did not find azimuthal integral asked for'
            return
        else:
            if ('_azint_'+azint) not in self.__dict__.keys():
                print 'did not find azint ',azint,', all keys are: ',self.__dict__.keys()
        try:
            azintValues = self.__dict__['_azint_'+azint]
            fig=plt.figure(figsize=(8,5))
            if len(azintValues.shape)==1:
                print azintValues.shape, self.__dict__[detname].__dict__[azint+'_q'].shape
                plt.plot(self.__dict__[detname].__dict__[azint+'_q'],azintValues,'o')
            elif len(azintValues.shape)==2:
                plt.imshow(azintValues,aspect='auto',interpolation='none')
                plt.colorbar()
        except:
            pass

    def AzInt_centerVar(self, detname=None, use_mask=False, center=None, data=None, varCenter=110., zoom=[-1,-1]):
        if data is not None:
            if detname is None:
                detname=raw_input('type the name detector alias')
            img=data
        else:
            detname, img, avImage = self.getAvImage(detname=detname)
        if use_mask:
            mask = self.__dict__[detname].det.mask_calib(self.run)
            img = (img*mask)

        if center==None or len(center)!=2:
            centerString=raw_input('please enter the coordinates of the beam center as c1,c2 or [c1,c2]:')
            center=[int(centerString.replace('[','').replace(']','').split(',')[0]),
                    int(centerString.replace('[','').replace(']','').split(',')[1])]
        self.addAzInt(detname=detname, phiBins=13, qBin=0.001, eBeam=9.5, center=[center[0],center[1]], dis_to_sam=1000., name='c00')
        self.addAzInt(detname=detname, phiBins=13, qBin=0.001, eBeam=9.5, center=[center[0]-varCenter,center[1]], dis_to_sam=1000., name='cm10')
        self.addAzInt(detname=detname, phiBins=13, qBin=0.001, eBeam=9.5, center=[center[0]+varCenter,center[1]], dis_to_sam=1000., name='cp10')
        self.addAzInt(detname=detname, phiBins=13, qBin=0.001, eBeam=9.5, center=[center[0],center[1]-varCenter], dis_to_sam=1000., name='c0m1')
        self.addAzInt(detname=detname, phiBins=13, qBin=0.001, eBeam=9.5, center=[center[0],center[1]+varCenter], dis_to_sam=1000., name='c0p1')
        self.AzInt(detname=detname, use_mask=use_mask, data=data, azintName='c00')
        self.AzInt(detname=detname, use_mask=use_mask, data=data, azintName='cm10')
        self.AzInt(detname=detname, use_mask=use_mask, data=data, azintName='cp10')
        self.AzInt(detname=detname, use_mask=use_mask, data=data, azintName='c0m1')
        self.AzInt(detname=detname, use_mask=use_mask, data=data, azintName='c0p1')

        try:
            azintValues_c00 = self.__dict__['_azint_c00']
            azintValues_cm10 = self.__dict__['_azint_cm10']
            azintValues_cp10 = self.__dict__['_azint_cp10']
            azintValues_c0m1 = self.__dict__['_azint_c0m1']
            azintValues_c0p1 = self.__dict__['_azint_c0p1']

            fig=plt.figure(figsize=(10,6))
            from matplotlib import gridspec
            ymin=0;ymax=azintValues_c00.shape[1]-1
            #plt.subplot2grid((3,3),(1,1)).set_title('center= %9.2f, %9.2f'%(center[0],center[1]))
            #plt.subplot2grid((3,3),(1,0)).set_title('center= %9.2f, %9.2f'%(center[0]-varCenter,center[1]))
            #plt.subplot2grid((3,3),(1,2)).set_title('center= %9.2f, %9.2f'%(center[0]+varCenter,center[1]))
            #plt.subplot2grid((3,3),(0,1)).set_title('center= %9.2f, %9.2f'%(center[0],center[1]-varCenter))
            #plt.subplot2grid((3,3),(2,1)).set_title('center= %9.2f, %9.2f'%(center[0],center[1]+varCenter))
            plt.subplot2grid((3,3),(1,1)).imshow(azintValues_c00[:,ymin:ymax],aspect='auto',interpolation='none')
            plt.subplot2grid((3,3),(1,0)).imshow(azintValues_cm10[:,ymin:ymax],aspect='auto',interpolation='none')
            plt.subplot2grid((3,3),(1,2)).imshow(azintValues_cp10[:,ymin:ymax],aspect='auto',interpolation='none')
            plt.subplot2grid((3,3),(0,1)).imshow(azintValues_c0m1[:,ymin:ymax],aspect='auto',interpolation='none')
            plt.subplot2grid((3,3),(2,1)).imshow(azintValues_c0p1[:,ymin:ymax],aspect='auto',interpolation='none')

            print zoom, (zoom[0]!=zoom[1])
            while zoom[0]!=zoom[1]:
                if zoom[1]<zoom[0] or zoom[0]<0 or zoom[1]<0:
                    yString=raw_input('please enter x-boundaries of the zoomed figure as c1,c2 or [c1,c2]:')
                    ymin=int(yString.replace('[','').replace(']','').split(',')[0])
                    ymax=int(yString.replace('[','').replace(']','').split(',')[1])
                else:
                    ymin=zoom[0]
                    ymax=zoom[1]
                #plt.subplot2grid((3,3),(1,1)).set_title('center= %9.2f, %9.2f'%(center[0],center[1]))
                #plt.subplot2grid((3,3),(1,0)).set_title('center= %9.2f, %9.2f'%(center[0]-varCenter,center[1]))
                #plt.subplot2grid((3,3),(1,2)).set_title('center= %9.2f, %9.2f'%(center[0]+varCenter,center[1]))
                #plt.subplot2grid((3,3),(0,1)).set_title('center= %9.2f, %9.2f'%(center[0],center[1]-varCenter))
                #plt.subplot2grid((3,3),(2,1)).set_title('center= %9.2f, %9.2f'%(center[0],center[1]+varCenter))
                plt.subplot2grid((3,3),(1,1)).imshow(azintValues_c00[:,ymin:ymax],aspect='auto',interpolation='none')
                plt.subplot2grid((3,3),(1,0)).imshow(azintValues_cm10[:,ymin:ymax],aspect='auto',interpolation='none')
                plt.subplot2grid((3,3),(1,2)).imshow(azintValues_cp10[:,ymin:ymax],aspect='auto',interpolation='none')
                plt.subplot2grid((3,3),(0,1)).imshow(azintValues_c0m1[:,ymin:ymax],aspect='auto',interpolation='none')
                plt.subplot2grid((3,3),(2,1)).imshow(azintValues_c0p1[:,ymin:ymax],aspect='auto',interpolation='none')
                if raw_input("done? (y/n):\n") in ["y","Y"]:
                    zoom=[-1,-1]
                else:
                    yString=raw_input('please enter x-boundaries of the zoomed figure as c1,c2 or [c1,c2] - was: ',zoom)
                    ymin=int(yString.replace('[','').replace(']','').split(',')[0])
                    ymax=int(yString.replace('[','').replace(']','').split(',')[1])
        except:
            pass

    def SelectRegionDroplet(self, detname=None, limits=[5,99.5]):
        avImages=[]
        for key in self.__dict__.keys():
            if key.find('AvImg')>=0:
                if detname is not None and key.find(detname)>=0:
                    avImages.append(key)
                elif detname is None:
                    avImages.append(key)
        if len(avImages)==0:
            print 'please create the AvImage first!'
            return
        elif len(avImages)>1:
            print 'we have the following options: ',avImages
            avImage=raw_input('type the name of the AvImage to use:')
        else:
            avImage=avImages[0]
        detname = self._getDetname_from_AvImage(avImage)
        img = self.__dict__[avImage]
        print img.shape

        plotMax = np.percentile(img, limits[1])
        plotMin = np.percentile(img, limits[0])
        print 'plot %s using the %g/%g percentiles as plot min/max: (%g, %g)'%(avImage,limits[0],limits[1],plotMin,plotMax)

        needsGeo=False
        if self.__dict__[detname].ped.shape != self.__dict__[detname].imgShape:
            needsGeo=True

        if needsGeo:
            image = self.__dict__[detname].det.image(self.run, img)
        else:
            image = img

        det = self.__dict__[detname].det
        x = self.__dict__[detname+'_x']
        y = self.__dict__[detname+'_y']
        iX = self.__dict__[detname+'_iX']
        iY = self.__dict__[detname+'_iY']
        extent=[x.min(), x.max(), y.min(), y.max()]

        fig=plt.figure(figsize=(10,6))
        from matplotlib import gridspec
        gs=gridspec.GridSpec(1,2,width_ratios=[1,1])
        
        mask=None
        mask_r_nda=None

        plt.subplot(gs[0]).imshow(image,clim=[plotMin,plotMax],interpolation='None')

        print 'select two corners: '
        p =np.array(ginput(2))
        mask_roi=np.zeros_like(image)
        mask_roi[p[:,1].min():p[:,1].max(),p[:,0].min():p[:,0].max()]=1
        if needsGeo:
            mask_r_nda = np.array( [mask_roi[ix, iy] for ix, iy in zip(iX,iY)] )
        else:
            mask_r_nda = mask_roi

        if mask_r_nda is not None:
            #print 'created a mask....'
            if mask is None:
                mask = mask_r_nda.astype(bool).copy()
            else:
                mask = np.logical_or(mask,mask_r_nda)
        print 'masked: ',np.ones_like(x)[mask.astype(bool)].sum()

        image_mask = img.copy(); image_mask[~mask]=0;
        if needsGeo:
            plt.subplot(gs[1]).imshow(det.image(self.run,image_mask),clim=[plotMin,plotMax])
        else:
            plt.subplot(gs[1]).imshow(image_mask,clim=[plotMin,plotMax])

        if  det.dettype == 2:
            mask=mask.reshape(2,185*388).transpose(1,0)
        elif det.dettype == 1:
            mask=mask.reshape(32*185,388)
        elif det.dettype == 13:
            mask=mask.reshape(704,768)

        #2x2 save as 71780 lines, 2 entries
        #cspad save as 5920 lines, 388 entries
        if raw_input("Save to calibdir?\n") in ["y","Y"]:
            mask = (~(mask.astype(bool))).astype(int)
            srcStr=det.source.__str__().replace('Source("DetInfo(','').replace(')")','')
            if det.dettype==2:
                dirname='/reg/d/psdm/%s/%s/calib/CsPad2x2::CalibV1/%s/pixel_mask/'%(self.lda.expname[:3],self.lda.expname,srcStr)
            elif det.dettype==2:
                dirname='/reg/d/psdm/%s/%s/calib/CsPad::CalibV1/%s/pixel_mask/'%(self.lda.expname[:3],self.lda.expname,srcStr)        
            elif det.dettype==13:
                dirname='/reg/d/psdm/%s/%s/calib/Epix100a::CalibV1/%s/pixel_mask/'%(self.lda.expname[:3],self.lda.expname,srcStr)        
            if not os.path.exists(dirname):
                os.makedirs(dirname)
            fname='%s-end.data'%self.run
            np.savetxt(dirname+fname,mask)
        elif raw_input("Save to local?\n") in ["y","Y"]:
            mask = (~(mask.astype(bool))).astype(int)
            np.savetxt('%s_mask_run%s.data'%(self.lda.expname,self.run),mask)
        return mask
         
    def plotCalib(self, detname='None',common_mode=0):
        if not detname in self.__dict__.keys() or self.__dict__[detname].common_mode!=common_mode:
            detname = self.addDetInfo(detname=detname, common_mode=common_mode)
            if detname == 'None':
                print 'need detector name as input! '
                return
        det=self.__dict__[detname].det
        rms = self.__dict__[detname+'_rms']
        pedestals = self.__dict__[detname+'_pedestals']
        needsGeo=False
        if self.__dict__[detname].ped.shape != self.__dict__[detname].imgShape:
            needsGeo=True

        hstPed = np.histogram(pedestals.flatten(), np.arange(0, pedestals.max()*1.05))
        hstRms = np.histogram(rms.flatten(), np.arange(0, rms.max()*1.05,0.05))
        if needsGeo:
            pedImg = det.image(self.run,pedestals)
            rmsImg = det.image(self.run,rms)
        else:
            pedImg = pedestals
            rmsImg = rms

        figDark=plt.figure(figsize=(11,6))
        gsPed=gridspec.GridSpec(2,2,width_ratios=[1,1])
        plt.subplot(gsPed[1]).plot(hstPed[1][:-1],np.log(hstPed[0]),'o')
        plt.subplot(gsPed[3]).plot(hstRms[1][:-1],np.log(hstRms[0]),'o')

        im0 = plt.subplot(gsPed[0]).imshow(pedImg,clim=[np.percentile(pedestals,1),np.percentile(pedestals,99)])
        cbar0 = plt.colorbar(im0)

        im2 = plt.subplot(gsPed[2]).imshow(rmsImg,clim=[np.percentile(rms,1),np.percentile(rms,99)])
        cbar2 = plt.colorbar(im2)

    def calibHisto(self, detname='None', common_mode=0, printVal=[-1]):
        if not detname in self.__dict__.keys() or self.__dict__[detname].common_mode!=common_mode:
            detname = self.addDetInfo(detname=detname, common_mode=common_mode)
            if detname == 'None':
                print 'need detector name as input! '
                return
        det=self.__dict__[detname].det
        rms = self.__dict__[detname+'_rms']
        pedestals = self.__dict__[detname+'_pedestals']
        needsGeo=False
        if self.__dict__[detname].ped.shape != self.__dict__[detname].imgShape:
            needsGeo=True
        #now look at directory and get filenames of darks. Hmm. extra function?
        detNameStr = det.name.__str__()
        if detNameStr.find('Epix')>=0:
            detTypeStr='Epix100a::CalibV1'
        elif  detNameStr.find('2x2')>=0:
            detTypeStr='CsPad2x2::CalibV1'
        else:
            detTypeStr='CsPad::CalibV1'
        fnames = os.listdir('/reg/d/psdm/%s/%s/calib/%s/%s/pedestals/'%(self.hutch, self.expname, detTypeStr, detNameStr))
        pedNames=[]
        pedRuns=[]
        for fname in fnames:
            if fname[-5:]=='.data':
                pedNames.append(fname)
                pedRuns.append(int(fname.split('-')[0]))

        currRun=0
        icurrRun=0
        allPeds=[]
        allRms=[]
        allPedsImg=[]
        allRmsImg=[]
        pedRuns.sort()
        for ipedRun,pedRun in enumerate(pedRuns):
            if pedRun <= self.run and self.run-pedRun < self.run-currRun:
                currRun = pedRun
                icurrRun = ipedRun
            allPeds.append(det.pedestals(pedRun))
            allRms.append(det.rms(pedRun))
            if needsGeo:
                allPedsImg.append(allPeds[-1])
                allRmsImg.append(allRms[-1])
            else:
                allPedsImg.append(allPeds[-1])
                allRmsImg.append(allRms[-1])
            if len(printVal)<2:
                print 'getting pedestal from run ',pedRun
            elif len(printVal)>=4:
                print 'run %d, pixel cold/hot, low noise, high noise: %d / %d / %d / %d pixels'%(pedRun,(allPeds[-1]<printVal[0]).sum(), (allPeds[-1]>printVal[1]).sum(),(allRms[-1]<printVal[2]).sum(), (allRms[-1]>printVal[3]).sum())
            elif len(printVal)>=2:
                print 'run %d, pixel cold/hot: %d / %d pixels'%(pedRun,(allPeds[-1]<printVal[0]).sum(), (allPeds[-1]>printVal[1]).sum())

        ped2d=[] 
        rms2d=[] 
        print 'maxmin peds ',allPeds[icurrRun].shape, allPeds[icurrRun].max()  , allPeds[icurrRun].min() ,np.percentile(allPeds[icurrRun],0.5), np.percentile(allPeds[icurrRun],99.5)
        for thisPed,thisRms in zip(allPeds,allRms):
            #ped2d.append(np.histogram(thisPed.flatten(), np.arange(np.percentile(allPeds[icurrRun],0.5), np.percentile(allPeds[icurrRun],99.5)))[0],10)
            ped2d.append(np.histogram(thisPed.flatten(), np.arange(0, np.percentile(allPeds[icurrRun],99.5),10))[0])
            rms2d.append(np.histogram(thisRms.flatten(), np.arange(0, allRms[icurrRun].max()*1.05,0.1))[0])
        ped2dNorm=[] 
        rms2dNorm=[] 
        for thisPed,thisRms in zip(ped2d,rms2d):
            ped2dNorm.append(np.array(thisPed).astype(float)/np.array(ped2d[icurrRun]).astype(float))
            rms2dNorm.append(np.array(thisRms).astype(float)/np.array(rms2d[icurrRun]).astype(float))
        
        ped2dNorm = np.array(ped2dNorm)
        rms2dNorm = np.array(rms2dNorm)
        print 'shapes:',rms2dNorm.shape, ped2dNorm.shape

        figDark=plt.figure(figsize=(11,10))
        gsPed=gridspec.GridSpec(2,2)
        im0 = plt.subplot(gsPed[0]).imshow(ped2d,clim=[np.percentile(ped2d,1),np.percentile(ped2d,99)],interpolation='none',aspect='auto')
        cbar0 = plt.colorbar(im0)

        im01 = plt.subplot(gsPed[1]).imshow(ped2dNorm,clim=[np.percentile(ped2dNorm,1),np.percentile(ped2dNorm,99)],interpolation='none',aspect='auto')
        cbar01 = plt.colorbar(im01)

        im2 = plt.subplot(gsPed[2]).imshow(rms2d,clim=[np.percentile(rms2d,1),np.percentile(rms2d,99)],interpolation='none',aspect='auto')
        cbar2 = plt.colorbar(im2)

        im21 = plt.subplot(gsPed[3]).imshow(rms2dNorm,clim=[np.percentile(rms2dNorm,1),np.percentile(rms2dNorm,99)],interpolation='none',aspect='auto')
        cbar21 = plt.colorbar(im21)


    def compareCommonMode(self, detname='None',common_modes=[], numEvts=100, thresADU=0., thresRms=0.):
        if detname is 'None':
            detname = self.addDetInfo(detname=detname)
            if detname == 'None':
                print 'need detector name as input! '
                return

        if len(common_modes)==0:
            if detname.find('cs')>=0:
                common_modes=[1,5,0]
            elif detname.find('epix')>=0:
                common_modes=[46,45,4,0]
            else:
                common_modes=[0,-1]

        baseName='AvImg_'
        if thresADU!=0:
            baseName+='thresADU%d_'%int(thresADU)
        if thresRms!=0:
            baseName+='thresRms%d_'%int(thresRms*10.)
        imgNames=[]
        imgs=[]

        for cm in common_modes:
            self.AvImage(detname, numEvts=numEvts, thresADU=thresADU, thresRms=thresRms, common_mode=cm)
            imgNames.append('%s%s%s'%(baseName,self.commonModeStr(cm),detname))
            #add needsGeo clause here.
            if self.__dict__[detname].ped.shape != self.__dict__[detname].imgShape:
                imgs.append(self.__dict__[detname].det.image(self.run, self.__dict__[imgNames[-1]]))
            else:
                imgs.append(self.__dict__[imgNames[-1]])
            self.AvImage(detname, numEvts=numEvts, thresADU=thresADU, thresRms=thresRms, common_mode=cm, std=True)
            imgNames.append('%sstd_%s%s'%(baseName,self.commonModeStr(cm),detname))
            if self.__dict__[detname].ped.shape != self.__dict__[detname].imgShape:
                imgs.append(self.__dict__[detname].det.image(self.run, self.__dict__[imgNames[-1]]))
            else:
                imgs.append(self.__dict__[imgNames[-1]])

        #print imgNames
        #for img in imgs:
        #    print img.shape

        fig=plt.figure(figsize=(15,10))
        gsCM=gridspec.GridSpec(len(common_modes),2)
        for icm,cm in enumerate(common_modes):
            if cm==0:
                lims=[np.percentile(imgs[icm*2],1),np.percentile(imgs[icm*2],99)]
            else:
                lims=[np.percentile(imgs[0],1),np.percentile(imgs[0],99)]
            limsStd=[np.percentile(imgs[1],1),np.percentile(imgs[1],99)]
            imC = plt.subplot(gsCM[icm*2]).imshow(imgs[icm*2],clim=lims,interpolation='none',aspect='auto')
            plt.colorbar(imC)
            imCS = plt.subplot(gsCM[icm*2+1]).imshow(imgs[icm*2+1],clim=limsStd,interpolation='none',aspect='auto')
            plt.colorbar(imCS)
