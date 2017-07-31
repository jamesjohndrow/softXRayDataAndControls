from pylab import *
import psana

def getPeak(detectorObject,thisEvent):

	myWaveForm = -detectorObject(thisEvent)[0][0]

	myWaveForm -= mean(myWaveForm[:2500])

	myFit = polyfit(arange(len(myWaveForm))[7500:10000]-8406, myWaveForm[7500:10000],3)

	myDictionary = {}
	myDictionary['acqirisParameter1'] = myFit[-1]
	myDictionary['acqirisParameter2'] = myFit[-2]

	#return myFit[-1]
	return myDictionary

def getWaveForm(detectorObject,thisEvent):
	return detectorObject(thisEvent)[0][0]
	
def get(detectorObject,thisEvent):
	return detectorObject(thisEvent)

def getRaw(detectorObject,thisEvent):
	return detectorObject(thisEvent)

def getGMD(detectorObject,thisEvent):
	temp = detectorObject.get(thisEvent)
	return temp.milliJoulesPerPulse()

def getEBeam(detectorObject,thisEvent):
	temp = detectorObject.get(thisEvent)
	return temp.ebeamPhotonEnergy()
