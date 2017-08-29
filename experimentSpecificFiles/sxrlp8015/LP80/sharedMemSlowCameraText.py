from pylab import *
import psana
#myDataSource = psana.DataSource("shmem=psana.0:stop=no")
myDataSource = psana.DataSource("exp=sxrlp8015:run=17:smd:dir/reg/d/ffb/sxr/sxrlp8015/xtc:live")
#myDataSource = psana.DataSource("exp=sxrlp8015:run=17")

myUserAndorDetectorObject = psana.Detector('userAndor')
myAndorDetectorObject = psana.Detector('andor')


myEnumeratedEvents = enumerate(myDataSource.events())

for eventNumber,thisEvent in myEnumeratedEvents:
	
	#if(eventNumber < 101):
	#	continue

	myUserImage = myUserAndorDetectorObject.image(thisEvent)
	myImage = myAndorDetectorObject.image(thisEvent)

	if(eventNumber % 100 ==1):
		print eventNumber

	if (myImage != None):
		break
	if (myUserImage != None):
		break
