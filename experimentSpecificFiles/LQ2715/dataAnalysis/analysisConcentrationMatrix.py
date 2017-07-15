from pylab import *

myData = loadtxt("intZall.dat")[:,8:]

y = arange(myData.shape[0])
x = array([ones(myData.shape[0])[11:],(y-mean(y))[11:],(exp(-y)-mean(exp(-y)))[11:]])
mySpectra = dot(inv(dot(x,x.transpose())),dot(x,myData[11:]))

subplot(311)
plot(mySpectra[0]/min(mySpectra[0]))
subplot(312)
plot(mySpectra[1]/max(mySpectra[1]))
subplot(313)
plot(mySpectra[2]/min(mySpectra[2]) - mySpectra[0]/min(mySpectra[0]))

show()