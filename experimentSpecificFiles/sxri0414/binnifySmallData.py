#!/reg/g/psdm/sw/conda/inst/miniconda2-prod-rhel7/envs/ana-1.3.9/bin/python -i
from pylab import *
from scipy.interpolate import interp1d
import h5py
import argparse
from scipy.optimize import curve_fit
import pickle
import os
import math
from filterMasks import filterMasks

#--------------------------------------------------------------------------
# File and Version Information:
#  $Id: README 2017-08-06 18:54:12Z sioan@SLAC.STANFORD.EDU $
#
# Description:
#  README file for data analysis
#------------------------------------------------------------------------

#Package author: Sioan Zohar

#Brief description:
#==================
#takes an hdf5 files turns it into applies a mask, turns it into dictionary, and bins it according to a config file or parameters
#the idea is to iterate this same code on different data sets using one config file or to test out analysis approaches by evaluating one data set and
#many config files iterating over different config files.  Testing different analysis techniques (that are abstracted into different configurations of identical code)
#is important for understanding why somes analysis techniques gives the expected result and some give unexpceted results.

#In depth description
#====================



def hdf5_to_dict(myhdf5Object):
	replacementDictionary = {}
	for i in myhdf5Object:
		#print(str(myhdf5Object[i]))
		if ('dataset' in str(myhdf5Object[i])):
			#print("dataset is in"+str(myhdf5Object[i]))
			if ('Summarized' not in str(myhdf5Object[i])):
				replacementDictionary[i] = nan_to_num(myhdf5Object[i])
			else:
				x=1	
		else:
			replacementDictionary[i] = {}
			#print("dataset is not in"+str(myhdf5Object[i]))
			#print(i)
			replacementDictionary[i] = hdf5_to_dict(myhdf5Object[i])

	return replacementDictionary


#to do list
#1) separate out mask section into directory and files. 
#2) add arg parser to go over battery of analysis and specified files. need to use the @ trick to get the interactive to work
#3) rolling statistics takes too long. how to speed up?

def removeNans(myDict):
	notNanMask = True
	for i in myDict:		
		notNanMask *= array([not math.isnan(j) for j in myDict[i]])
	
	for i in myDict:		
		myDict[i] = myDict[i][notNanMask]

	return myDict

def basicHistogram(myDict,keyToAverage,keyToBin,bins,isLog):#fast for debugging

	myDataDictionary = {}

	if(isLog):
		myDataDictionary['x'] = bins[:-1]
		myDataDictionary['counts'] = histogram(myDict[keyToBin],bins)[0]

		myDataDictionary['yMean'] = histogram(myDict[keyToBin],bins,weights = log(myDict[keyToAverage]))[0]
		myDataDictionary['yMean']/= myDataDictionary['counts']
		
		myDataDictionary['y2ndMoment'] = histogram(myDict[keyToBin],bins,weights = log(myDict[keyToAverage])**2)[0]
		myDataDictionary['y2ndMoment']/= myDataDictionary['counts']

		myDataDictionary['standardDeviation'] = (myDataDictionary['y2ndMoment']-myDataDictionary['yMean'])**0.5
		myDataDictionary['standardDeviation'] = exp(myDataDictionary['standardDeviation'])

		myDataDictionary['yMean'] = exp(myDataDictionary['yMean'])

		#myDataDictionary['yMean'] = exp(myDataDictionary['yMean'])
		#myDataDictionary['standardDeviation'] = exp(myDataDictionary['standardDeviation'])
	
	else:
		myDataDictionary['x'] = bins[:-1]
		myDataDictionary['counts'] = histogram(myDict[keyToBin],bins)[0]

		myDataDictionary['yMean'] = histogram(myDict[keyToBin],bins,weights = myDict[keyToAverage])[0]
		myDataDictionary['yMean']/= myDataDictionary['counts']
	
		myDataDictionary['y2ndMoment'] = histogram(myDict[keyToBin],bins,weights = myDict[keyToAverage]**2)[0]
		myDataDictionary['y2ndMoment']/= myDataDictionary['counts']

		myDataDictionary['standardDeviation'] = (myDataDictionary['y2ndMoment']-myDataDictionary['yMean'])**0.5

	del myDataDictionary['y2ndMoment']

	myDataDictionary = removeNans(myDataDictionary)

	return myDataDictionary

if __name__ == '__main__':
	


	currentWorkingDirectory = os.getcwd()

	h5FileName = sys.argv[1]
	experimentRunName = h5FileName.split("/")[1][:-3]

	f = h5py.File(currentWorkingDirectory+"/"+h5FileName,'r')
	myDict= hdf5_to_dict(f)
	f.close()

	myMask =  filterMasks.__dict__[experimentRunName](myDict)

	myDict['normalizedAcqiris'] = myDict['acqiris2']/(1e-11+myDict['GMD'])

	#time tool direction. need to abstract into config file. also, milimeter to picosecond correction
	myDict['estimatedTime'] = 2/.3*(myDict['delayStage']-49)+1*myDict['TSS_OPAL']['pixelTime']/1000.0	

	myDict['normalizedAcqiris'] = myDict['normalizedAcqiris'][myMask]
	myDict['estimatedTime'] = myDict['estimatedTime'][myMask]

	
	#def rollingStatistics(scatterData,axisToAverage,axisToBin,bins,m,isLog=False): #reference for how to use
	#need to change arguments to binKey, averageKey. averageKey is really the y value and the binKey is the x
	#myDataDictionary = rollingStatistics(toBeBinned,0,1,arange(0.5,21,.1),2,isLog=True)#very long wait time. not very efficient
	keyToAverage = 'normalizedAcqiris'
	keyToBin = 'estimatedTime'
	myDataDictionary = basicHistogram(myDict,keyToAverage,keyToBin,bins=arange(0.5,21,.1),isLog=True)#fast for debugging

	pickle.dump(myDataDictionary, open(currentWorkingDirectory+"/binnedData/"+experimentRunName+".pkl", "wb"))
	#temp = pickle.load(open(experimentRunName+".pkl","rb"))




