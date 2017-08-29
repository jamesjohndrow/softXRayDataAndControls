from pylab import *


myData = loadtxt("imageForSVD.txt")
u,s,v = svd(myData[50:120])  
figure(0)
imshow(myData)

figure(1)
subplot(421)
plot(-v[0],'b-')
subplot(423)
plot(-3*v[0],'r-')
plot(-v[1],'b-')
subplot(425)
plot(-v[2],'b-')
subplot(427)
plot(-v[3],'b-')


subplot(422)
plot(u[:,0],'bo')
subplot(424)
plot(u[:,1],'bo')
subplot(426)
plot(u[:,2],'bo')
subplot(428)
plot(u[:,2],'bo')

show()