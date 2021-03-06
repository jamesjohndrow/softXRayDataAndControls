from pylab import *
import psana

def genericReturn(detectorObject,thisEvent):
	return detectorObject(thisEvent)

def genericSummaryZero(detectorObject,thisEvent,previousProcessing):
	return 0

def myZeroReturn(detectorObject,thisEvent,previousProcessing):
	return 0

def processMCP(detectorObject,thisEvent):
	myDict = {}

	myDict['MCP'] = -99999
	if (None not in [detectorObject(thisEvent)]):
		tempWaveform = detectorObject(thisEvent)[0][0]
		myDict['MCP'] = -(sum(tempWaveform[1190:1220] - mean(tempWaveform[0:1190])))

	return myDict

def dropletAnalysis(detectorObject,thisEvent):
	
	myImage = detectorObject.image(thisEvent)

	myDict = {}

	if myImage is None:
		myDict['ROI1'] = -9999999
		myDict['ROI2'] = -9999999
	
	else:
		myDict['ROI1'] = sum(myImage[420:560,80:220])
		myDict['ROI2'] = sum(myImage[420:560,1040:1100])


	return myDict

def accumulatorROIImage(detectorObject,thisEvent,previousProcessing):


	myImage = detectorObject.image(thisEvent)
	
	if ('acummulatedHistogram' not in previousProcessing.keys()):
		y,x = histogram(myImage.flatten(),bins=arange(-200,4000,10))
		previousProcessing['acummulatedHistogramCounts'] = y
		previousProcessing['acummulatedHistogramBins'] = x 

	else:
		previousProcessing['acummulatedHistogramCounts']+=histogram(myImage.flatten(),bins=arange(-200,4000,10))[0]

	return previousProcessing

def getTimeToolData(detectorObject,thisEvent):
	ttData = detectorObject.process(thisEvent)
	myDict = {}	
	if(ttData is None):
		
		myDict['amplitude'] = -99999
		myDict['pixelTime'] = -99999
		myDict['positionFWHM'] = -99999


	else:

		myDict['amplitude'] = ttData.amplitude()
		myDict['pixelTime'] = ttData.position_time()
		myDict['positionFWHM'] = ttData.position_fwhm()

	return myDict

def getPeak(detectorObject,thisEvent):

	myWaveForm = -detectorObject(thisEvent)[0][0]

	myWaveForm -= mean(myWaveForm[:2500])

	x = arange(len(myWaveForm))[7500:10000]-8406
	myFit = polyfit(x, myWaveForm[7500:10000],3)

	p = poly1d(myFit)
	myMax = max(p(x))

	#return myFit[-1]	#placing a dictionary here also works
	return myMax	

def accumulateAverageWave(detectorObject,thisEvent,previousProcessing):

	myWaveForm = -detectorObject(thisEvent)[0][0]
	myWaveForm -= mean(myWaveForm[:2500])

	return (previousProcessing+myWaveForm)

def getWaveForm(detectorObject,thisEvent):
	if (None not in [detectorObject(thisEvent)[0][0]]):
		return detectorObject(thisEvent)[0][0]
	else:	
		return 0
	
def get(detectorObject,thisEvent):
	if (None not in [detectorObject(thisEvent)]):
		return detectorObject(thisEvent)
	else:
		return 0

def getRaw(detectorObject,thisEvent):
	if (None not in [detectorObject(thisEvent)]):
		return detectorObject(thisEvent)
	else:
		return 0

def getGMD(detectorObject,thisEvent):
	temp = detectorObject.get(thisEvent)
	if (None not in [temp]):
		return temp.milliJoulesPerPulse()
	else: 	
		return 0

def getEBeam(detectorObject,thisEvent):
	temp = detectorObject.get(thisEvent)
	if(None not in [temp]):
		return temp.ebeamPhotonEnergy()
	else:
		return 0



