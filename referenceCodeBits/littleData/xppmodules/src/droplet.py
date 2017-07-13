#
# add option to prepareImg to mask the direct neighbors of masked pixels as well
# only to be used for default threshold _not_ the lower one.
#
# with two thresholds: re-label w/ second threshold image (optionally)
#
# photonize: store differently: store pos w/ number of photons (not COM for last photon, but pixels)
#
# 'fitting': model distributions of multiple photons in 2,3,4 pixels & compare chi sq to actual data.
#
import numpy as np
import time
import scipy.ndimage.measurements as measurements
import skimage.measure as measure
import scipy.ndimage.filters as filters
from scipy import sparse

class aduHist:
        def __init__(self,aduHist=[], ROI=None, name=''):
                self.name=name+'aduHist'
                self.bins=[]
                if len(aduHist)==1:
                        self.bins=np.arange(0, aduHist[0])
                elif len(aduHist)==2:
                        self.bins=np.arange(aduHist[0], aduHist[1])
                elif len(aduHist)==3:
                        if isinstance(aduHist[2], int):
                                self.bins=np.linspace(aduHist[0], aduHist[1], aduHist[2])
                        if isinstance(aduHist[2], float):
                                self.bins=np.arange(aduHist[0], aduHist[1], aduHist[2])
                self.ROI = ROI
        def fillHist(self, dadu, pos=None):
                if pos is None:
                        return np.histogram(dadu.flatten()[dadu.flatten()>0], self.bins)[0]
                else:
                        dx = pos[:,0].flatten()
                        dy = pos[:,1].flatten()
                        Filter = [ dx > ROI[0] & dx < ROI[1] & dy > ROI[3] & dy < ROI[4] ]
                        dadu = dadu.flatten()[Filter]
                        return np.histogram(dadu[dadu>0], self.bins)[0]
                        
class dropletSave:
        def __init__(self,thresAdu=[50,np.nan],maxDroplets=1500, name='',dropPosInt=False, retPixel=False, ret2ndMom=0, boolMask=False):
                self.name=name
                self.maxDroplets = maxDroplets
                self.dropPosInt = dropPosInt
                self.retPixel = retPixel
                self.ret2ndMom = ret2ndMom
                self.thresAdu = thresAdu
                self.boolMask = boolMask

        def shapeArray(self, returnDict):
                for key in returnDict.keys():
                        if key.find(self.name)<0:
                                continue;
                        if key.find('nDroplets')>=0:
                                continue;
                        if key.find('aduHist')>=0:
                                continue;
                        try: 
                                inputSize = len(returnDict[key])
                                if key.find('Pix')<0:
                                        if inputSize>=self.maxDroplets:
                                                returnDict[key] = returnDict[key][:self.maxDroplets]
                                        else:
                                                returnDict[key] = np.append(returnDict[key], np.zeros(self.maxDroplets-len(returnDict[key])))
                                else:
                                        if inputSize>=self.maxDroplets*self.retPixel:
                                                returnDict[key] = returnDict[key][:self.retPixel*self.maxDroplets]
                                        else:
                                                returnDict[key] = np.append(returnDict[key], np.zeros(self.retPixel*self.maxDroplets-len(returnDict[key])))
                        except:
                                print 'cannot get len of: ',key
                                print '--> ',returnDict[key]
                                import sys
                                sys.exit()
        def initArray(self):
                ret_dict = {(self.name+'_npix'): np.zeros(self.maxDroplets,dtype=np.int)}
                ret_dict[self.name+'_adu'] = np.zeros(self.maxDroplets)
                if self.dropPosInt:
                        ret_dict[self.name+'X'] = np.zeros(self.maxDroplets,dtype=np.int)
                        ret_dict[self.name+'Y'] = np.zeros(self.maxDroplets,dtype=np.int)
                else:
                        ret_dict[self.name+'X'] = np.zeros(self.maxDroplets)
                        ret_dict[self.name+'Y'] = np.zeros(self.maxDroplets)
                ret_dict[self.name+'_bb00'] = np.zeros(self.maxDroplets)
                ret_dict[self.name+'_bb01'] = np.zeros(self.maxDroplets)
                ret_dict[self.name+'_bb10'] = np.zeros(self.maxDroplets)
                ret_dict[self.name+'_bb11'] = np.zeros(self.maxDroplets)
                if self.ret2ndMom!=0:
                        for i in np.arange(self.ret2ndMom):
                                for ii in np.arange(self.ret2ndMom):
                                        ret_dict['%s_mom%d%d'%(self.name,i,ii)] = np.zeros(self.maxDroplets)
                if self.retPixel!=0:
                        ret_dict[self.name+'_Pix'] = np.zeros([self.maxDroplets*self.retPixel])
                if self.boolMask:
                        ret_dict[self.name+'_masked'] = np.zeros(self.maxDroplets)
                return ret_dict
                                
class photonizeDrops:
        def __init__(self,ADU_per_photon=154, thresFrac = 0.48, maxPhotons=1500, maxMultPhotons=25, name=''):
                if name[-1]!='_' and len(name)>0:
                        self.name = name+'_'
                else:
                        self.name=name
                self.ADU_per_photon = ADU_per_photon
                self.thresFrac = thresFrac
                self.maxPhotons = maxPhotons
                self.maxMultPhotons = maxMultPhotons

class droplet:
    def __init__(self, threshold=10.0, thresholdLow=3., thresADU=71., rms=None, mask=None, name='', useRms=True, relabel=True):
        """ 
        class takes corrected image as input (pedestal, common mode & gain if present)
        threshold : # noise sigma for threshold (def: 3.0)
        img is used only for displaying corrections
        """
        self.threshold = threshold
        self.thresholdLow = thresholdLow

        self.thresADU = thresADU
        self.useRms = useRms
        self.rms = rms
        self.mask = mask
        self.grid = np.meshgrid(range(max(self.rms.shape)),range(max(self.rms.shape)))
        self.name = name
        #new way to store this info
        self.dropletSaves=[]
        self.aduHists=[]
        self.debug = False
        self.compData = self.rms
        if not self.useRms:
            self.compData = np.ones_like(self.rms)
        self.footprint=np.array([[0,1,0],[1,1,1],[0,1,0]])
        self.aduROI=False
        self.relabel = relabel
        self.photonizeDrops=None
        self.photonize=False

    def setDebug(self, debug):
        if isinstance(debug, bool):
                self.debug = debug

    def addDropletSave(self,thresAdu=[np.nan,np.nan],maxDroplets=1500, name='',dropPosInt=False, retPixel=False, ret2ndMom=0, boolMask=False):
        dropSave = dropletSave(thresAdu,maxDroplets, name,dropPosInt, retPixel, ret2ndMom, boolMask)
        self.dropletSaves.append(dropSave)

    def addAduHist(self, ADUhist=[700], ROI=None, name=''):
        name = self.name+'_'+name
        thisAduHist = aduHist(ADUhist, ROI, name)
        self.aduHists.append(thisAduHist)

    def addPhotonizeDrops(self,ADU_per_photon=154, thresFrac = 0.48, maxPhotons=1500, maxMultPhotons=25, name=''):
        self.photonizeDrops = photonizeDrops(ADU_per_photon=ADU_per_photon, thresFrac = thresFrac, maxPhotons=maxPhotons, maxMultPhotons=maxMultPhotons, name=name)
        self.photonize=True

    def checkAduHist(self):
            for adu in self.aduHists:
                    if adu.ROI is not None:
                            self.aduROI = True

    def applyThreshold(self,img, donut=False, invert=False, low=False):
        if not donut:
            if low:
                    threshold = self.thresholdLow
            else:
                    threshold = self.threshold
            if not invert:
                img[img<self.compData*threshold] = 0.0
            else:
                img[img>self.compData*threshold] = 0.0
        else:
            img[img<self.compData*self.thresholdLow] = 0.0
            img[img>self.compData*self.threshold] = 0.0

    def neighborImg(self,img):
        return filters.maximum_filter(img,footprint=self.footprint)

    def prepareImg(self,img,donut=False,invert=False, low=False):
        imgIn = img.copy()
        if self.mask is not None:
            imgIn[self.mask==0]=0
        self.applyThreshold(imgIn,donut,invert,low)
        return imgIn

    def returnEmpty(self):
        ret_dict = {'nDroplets': -1}
        for aduHist in self.aduHists:
                ret_dict[aduHist.name] = np.zeros_like(len(aduHist.bins)+1)
        for dropSave in self.dropletSaves:
                dropDict = dropSave.initArray()
                for key in dropDict.keys():
                        ret_dict[key] = dropDict[key]
        if self.photonize:
                ret_dict['nPhotons'] = -1
                ret_dict['photons'] = np.zeros([self.maxPhotons,2])     
        return ret_dict

    def procAduHist(self, dadu, pos_drop=None):
        for adu in self.aduHists: 
                if adu.ROI is None:
                        self.ret_dict[adu.name] = adu.fillHist(dadu)
                else:
                        self.ret_dict[adu.name] = adu.fillHist(dadu,pos=pos_drop)

    def dropletize(self, data):
        tstart=time.time()
        if data is None:
            print 'img is None!'
            self.ret_dict = self.returnEmpty()
            return

        img = self.prepareImg(data)
        time_start = time.time()
        #is faster than measure.label(img, connectivity=1)
        img_drop = measurements.label(img)
        time_label = time.time()
        #get all neighbors
        if (self.threshold != self.thresholdLow):
                imgDrop = self.neighborImg(img_drop[0])
                img = self.prepareImg(data, low=True)
                #
                if self.relabel:
                        imgDrop[img==0]=0
                        img_drop_relabel = measurements.label(imgDrop)
                        imgDrop = img_drop_relabel[0]
        else:
                imgDrop = img_drop[0]

        drop_ind = np.arange(1,img_drop[1]+1)
        adu_drop = measurements.sum(img,imgDrop, drop_ind)
        self.ret_dict = {'nDroplets': len(drop_ind)}
        if len(self.aduHists)>0:
                if not self.aduROI:
                        self.procAduHist(adu_drop)
                        if len(self.dropletSaves)==0:
                                return

        if self.aduROI:
                pos_drop = np.array(measurements.center_of_mass(img,img_drop[0], drop_ind))
                self.procAduHist(adu_drop, pos_drop)
        if len(self.dropletSaves)==0:
                return

        #clean list with lower threshold. Only that one!
        vThres = np.where(adu_drop<self.thresADU)[0]
        vetoed = np.in1d(imgDrop.ravel(), (vThres+1)).reshape(imgDrop.shape)
        imgDrop[vetoed]=0

        ###
        # add label_img_neighbor w/ mask as image -> sum ADU , field "masked" (binary)?
        ###
        if 'boolMask' not in self.__dict__.keys():
                boolMask=False
                for saveD in self.dropletSaves:
                        if saveD.boolMask:
                                boolMask=True
                self.__dict__['boolMask'] = boolMask
        if self.__dict__['boolMask']:
                maxImg = filters.maximum_filter(imgDrop,footprint=self.footprint)
                maskMax = measurements.sum(self.mask,maxImg, drop_ind)
                imgDropMin = imgDrop.copy()
                imgDropMin[imgDrop==0]=(imgDrop.max()+1)
                minImg = filters.minimum_filter(imgDropMin,footprint=self.footprint)
                minImg[minImg==(imgDrop.max()+1)]=0
                maskMin = measurements.sum(self.mask,maxImg, drop_ind)
                maskDrop = maskMax+maskMin

        #adu_drop = np.delete(adu_drop,vThres)
        #use region props
        self.regions = measure.regionprops(imgDrop, intensity_image=img, cache=True)
        pos_drop = []
        moments = []
        bbox = []
        adu_drop = []
        npix_drop = []
        images = []
        dropSlices = measurements.find_objects(imgDrop)
        for droplet,ds in zip(self.regions,dropSlices):
                pos_drop.append(droplet['weighted_centroid'])
                moments.append(droplet['weighted_moments_central'])
                bbox.append(droplet['bbox'])
                adu_drop.append(droplet['intensity_image'].sum())
                npix_drop.append((droplet['intensity_image']>0).sum())
                images.append(droplet['intensity_image'].flatten())

        for saveD in self.dropletSaves:
                aduArray = np.array(adu_drop).copy()
                Filter = np.ones_like(aduArray).astype(bool)
                if saveD.thresAdu[0] is not np.nan and saveD.thresAdu[1] is not np.nan:
                        Filter = ((aduArray>saveD.thresAdu[0]) & (aduArray<saveD.thresAdu[1]))
                elif saveD.thresAdu[0] is not np.nan:
                        Filter = (aduArray>saveD.thresAdu[0]) 
                elif saveD.thresAdu[1] is not np.nan:
                        Filter = (aduArray<saveD.thresAdu[1])
                dropName = self.name
                if saveD.name!='':
                        dropName = dropName+'_'+saveD.name
                self.ret_dict[dropName+'_nDroplets'] = Filter.sum()
                self.ret_dict[dropName+'_adu'] = aduArray[Filter]
                self.ret_dict[dropName+'_npix'] = np.array(npix_drop)[Filter]
                if saveD.boolMask:
                        self.ret_dict[dropName+'_masked'] = np.array(maskDrop)[Filter]
                if Filter.sum()>0:
                        self.ret_dict[dropName+'_X'] = np.array(pos_drop)[Filter][:,0]
                        self.ret_dict[dropName+'_Y'] = np.array(pos_drop)[Filter][:,1]
                else:
                        self.ret_dict[dropName+'_X'] = np.array([0.])
                        self.ret_dict[dropName+'_Y'] = np.array([0.])
                if saveD.ret2ndMom>1:
                        moments_dropLocal = np.array(moments)[Filter]
                        if len(moments_dropLocal)>0:
                                for i in (np.arange(saveD.ret2ndMom)):
                                        for ii in (np.arange(saveD.ret2ndMom)):
                                                if i==0 and ii==0:
                                                        continue
                                                self.ret_dict['%s_mom%d%d'%(dropName,i,ii)] = moments_dropLocal[:,i,ii]
                        else:
                                for i in (np.arange(saveD.ret2ndMom)):
                                        for ii in (np.arange(saveD.ret2ndMom)):
                                                if i==0 and ii==0:
                                                        continue
                                                self.ret_dict['%s_mom%d%d'%(dropName,i,ii)] = [0.]
                if (saveD.retPixel):
                        if Filter.sum()>0:
                                self.ret_dict[dropName+'_bbox_x0'] = np.array(bbox)[Filter][:,0]
                                self.ret_dict[dropName+'_bbox_y0'] = np.array(bbox)[Filter][:,1]
                                self.ret_dict[dropName+'_bbox_x1'] = np.array(bbox)[Filter][:,2]
                                self.ret_dict[dropName+'_bbox_y1'] = np.array(bbox)[Filter][:,3]
                                try:
                                        self.ret_dict[dropName+'_Pix'] = (np.concatenate(np.array(images).flatten()[Filter])).flatten()
                                except:
                                        self.ret_dict[dropName+'_Pix'] = [0.]
                        else:
                                self.ret_dict[dropName+'_bbox_x0'] =  [0.]
                                self.ret_dict[dropName+'_bbox_y0'] =  [0.]
                                self.ret_dict[dropName+'_bbox_x1'] =  [0.]
                                self.ret_dict[dropName+'_bbox_y1'] =  [0.]
                                self.ret_dict[dropName+'_Pix'] = [0.]

                saveD.shapeArray(self.ret_dict)

        self.ret_dict['evtTimeDrop']=time.time() - tstart
        #write optionally so to store pixels / nphotons rather than photons/positions
        if not self.photonize:
            return

        tstartPhot=time.time()            
        vThres = np.where(adu_drop <= (self.photonizeDrops.thresFrac*self.photonizeDrops.ADU_per_photon))[0]
        #print len(vThres)
        drop_ind = np.delete(drop_ind,vThres)
        adu_drop = np.delete(adu_drop,vThres)
        bbox = np.delete(bbox,vThres,0)
        images = np.delete(images,vThres,0)

        vSingle = np.where(adu_drop <= ((1.+self.photonizeDrops.thresFrac)*self.photonizeDrops.ADU_per_photon))[0]
        #print vSingle
        singles_ind = drop_ind[vSingle]
        singles_adu = measurements.sum(img,img_drop[0], singles_ind).tolist()
        singles_pos = measurements.center_of_mass(img,img_drop[0], singles_ind)
        self.ret_dict[self.photonizeDrops.name+'nPhotons_single'] = len(singles_pos) 
        drop_ind = np.delete(drop_ind,vSingle)
        adu_drop = np.delete(adu_drop,vSingle)
        dropSlices = measurements.find_objects(img_drop[0])
        self.ret_dict[self.photonizeDrops.name+'nPhotons_multi'] = len(adu_drop) 
        self.ret_dict[self.photonizeDrops.name+'nPhotons_multi_ADU'] = np.array(adu_drop).sum()/170.
        bbox = np.delete(bbox,vSingle,0)
        images = np.delete(images,vSingle,0)

        #imgg is correct. need to come up with x.y
        for s,bbx,imgg in zip(adu_drop,bbox,images):
            #print s
            num_phts = np.ceil(s/self.photonizeDrops.ADU_per_photon - self.photonizeDrops.thresFrac)
            lgrid = np.meshgrid(range(bbx[0],bbx[2]),range(bbx[1],bbx[3]))
            #print lgrid
            posX = lgrid[0].transpose().flatten()
            posY = lgrid[1].transpose().flatten()

            while num_phts:
                m = np.argmax(imgg)
                imgg[m] -= self.photonizeDrops.ADU_per_photon
                num_phts -=1
                #if num_phts>1:
                singles_pos.append((posX[m],posY[m]))
                singles_adu.append(self.photonizeDrops.ADU_per_photon)
                #else:
                #    singles_pos.append((np.sum(np.multiply(posX,pp))/np.sum(pp),np.sum(np.multiply(posY,pp))/np.sum(pp)))

        time_findMult = time.time()
        nPhot = len(singles_pos)
        self.ret_dict[self.photonizeDrops.name+'nPhotons'] = nPhot
        #make img to get doubles
        pdata = np.ones(len(singles_adu)).astype(int)
        try:
                px = (np.array(singles_pos)[:,0]).astype(int)
                py = (np.array(singles_pos)[:,1]).astype(int)
        except:
                px = np.ones(len(singles_adu)).astype(int)
                py = np.ones(len(singles_adu)).astype(int)
        #print 'img shape: ',data.shape, px.max(), py.max()
        sImgSparse = sparse.coo_matrix((pdata, (px, py)),shape=data.shape).todense()
        self.ret_dict[self.photonizeDrops.name+'pHist']=np.histogram(sImgSparse.flatten(), np.arange(0,self.photonizeDrops.maxMultPhotons))[0]
        self.ret_dict[self.photonizeDrops.name+'nPhot']=sImgSparse.sum()

        singles_adu = np.ceil(np.array(singles_adu)/self.photonizeDrops.ADU_per_photon - self.photonizeDrops.thresFrac)
        #shape array
        if nPhot>=self.photonizeDrops.maxPhotons:
            self.ret_dict[self.photonizeDrops.name+'photons_row'] = np.array(singles_pos[:self.photonizeDrops.maxPhotons])[:,0]
            self.ret_dict[self.photonizeDrops.name+'photons_col'] = np.array(singles_pos[:self.photonizeDrops.maxPhotons])[:,1]
            self.ret_dict[self.photonizeDrops.name+'photons_data'] = singles_adu[:self.photonizeDrops.maxPhotons]
        elif nPhot>0:
            self.ret_dict[self.photonizeDrops.name+'photons_row'] = np.append(np.array(singles_pos[:])[:,0],np.zeros(self.photonizeDrops.maxPhotons-nPhot),axis=0)
            self.ret_dict[self.photonizeDrops.name+'photons_col'] = np.append(np.array(singles_pos[:])[:,1],np.zeros(self.photonizeDrops.maxPhotons-nPhot),axis=0)
            self.ret_dict[self.photonizeDrops.name+'photons_data'] = np.append(singles_adu,np.zeros(self.photonizeDrops.maxPhotons-nPhot),axis=0)
        else:
            self.ret_dict[self.photonizeDrops.name+'photons_row'] = np.zeros(self.photonizeDrops.maxPhotons)
            self.ret_dict[self.photonizeDrops.name+'photons_col'] = np.zeros(self.photonizeDrops.maxPhotons)
            self.ret_dict[self.photonizeDrops.name+'photons_data'] = np.zeros(self.photonizeDrops.maxPhotons)
                
        self.ret_dict['evtTimePhot']=time.time() - tstartPhot
        return #ret_dict
