from psana import *
import numpy as np
import sys
runnum = int(sys.argv[1])

dsource = MPIDataSource('exp=xpp10916:run=%d:smd:dir=/reg/d/ffb/xpp/xpp10916/xtc:live'%runnum)
gd_det = Detector('FEEGasDetEnergy')
gon_ipm = Detector('XCS-IPM-gon')
ipm1_wv = DetInfo('Wave8WF')
#ipm1 = Detector('BldInfo(-Invalid-)')

smldata = dsource.small_data('/reg/d/psdm/xpp/xpp10916/results/run%d.h5'%runnum,gather_interval=100)

#summary: get waveformdata for each trace.

for nevt,evt in enumerate(dsource.events()):
   gd = gd_det.get(evt)

   gmd = gmd_det.get(evt)
   mono = mono_det.get(evt)
   dls = dls_det.get(evt)
   #dls_calib=dls_det.values(evt)
   ebeam = ebeam_det.get(evt)
   eventCodes = evr_det.eventCodes(evt)
   ttool_fltpos = ttool_fltpos_det()
   ttool_ampl = ttool_ampl_det()
   ttool_fwhm = ttool_fwhm_det()
   andor = andor_det.calib(evt)
   opal=opal_det.calib(evt)

   #if wf is None or gd is None or gmd is None or mono is None or eventCodes is None or ebeam is None:
   #   #print 'none',wf,gd,gmd,mono,eventCodes
   #   print 'none',eventCodes
   #   continue


   d = {}
   if (wf is not None):#&(runnum<=32): 
	d['wf_Fe']=wf[0][88000:90000] 	#Acq01 ch 1
	d['wf_tfy']=wf[1][88000:90000]	#Acq01 ch 2
        d['wf_i0']=wf[2][88000:90000]	#Acq01 ch 3
	d['wf_laser_diode']=wf[3][88000:90400]	#Acq01 ch 4, needs longer window
#   elif (wf is not None)&(runnum>32): 
#	d['wf_Fe']=wf[0][88000:90000] 	#Acq01 ch 1
#	d['wf_tfy']=wf[2][88000:90000]	#Acq01 ch 3
#        d['wf_i0']=wf[1][88000:90000]	#Acq01 ch 2
   if andor is not None: d['andor']= np.transpose(andor).squeeze()
   if gd is not None:
      gd_vals = np.array((gd.f_11_ENRC(),gd.f_12_ENRC(),
                          gd.f_21_ENRC(),gd.f_22_ENRC()))
      d['gd']=gd_vals
   if gmd is not None: d['gmd']=gmd.relativeEnergyPerPulse()
   if mono is not None: d['mono']=mono.encoder_count()
   if dls is not None: 
      d['dls']=dls.encoder_count()
      d['dls_calib']=calibrate_dls(d['dls'][0])
   if eventCodes is not None:
      d['xray_drop'] = int(162 in eventCodes)
      d['laser_a'] = int(76 in eventCodes)#maybe 77
      d['laser_b']=int(77 in eventCodes)

   if ttool_fltpos is not None:
      d['ttool_fltpos'] = ttool_fltpos
      d['ttool_ampl'] = ttool_ampl
      d['ttool_fwhm'] = ttool_fwhm
   if ebeam is not None: d['photonEnergy'] = ebeam.ebeamPhotonEnergy()
   if opal is not None: 
      opal_trace=np.sum(opal[0:290,:],0)
      d['TSS_OPAL']=opal_trace
   smldata.event(d)
   #if evt>3: break

smldata.save()
