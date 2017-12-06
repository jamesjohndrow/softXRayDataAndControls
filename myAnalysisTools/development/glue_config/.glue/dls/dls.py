from glue.viewers.custom.qt import CustomViewer
from glue.core.visual import VisualAttributes
from glue.core import DataCollection

from glue.core.subset import RoiSubsetState

from matplotlib.colors import LogNorm
from matplotlib.patches import Circle, Rectangle, Arc
from matplotlib.lines import Line2D
import numpy as np
from lib.analysis_library import vectorized_binned_statistic_dd
from scipy.stats import binned_statistic
import pickle
import zmq
import sys
import time
import threading
import random

"""
class YourThreadName(QThread):

    def __init__(self):
        QThread.__init__(self)

    def __del__(self):
        self.wait()

    def run(self):
        # your logic here"""

def publish_glue_object_memory(hex_id):
	port = 5556


	context = zmq.Context()
	socket = context.socket(zmq.PUB)
	socket.bind("tcp://*:%s" % port)

	while True:
		#topic = random.randrange(9999,10005)
		topic = 10001
		#messagedata = random.randrange(1,215) - 80
		messagedata=hex_id
		#print("%d %d" % (topic, messagedata))
		socket.send_string("%d %d" % (topic, messagedata))
		#socket.send(str(hex_id))
		#print("sending string")
		time.sleep(1)


def t_func(r,median_truncation):
	temp = np.array([pickle.loads(i) for i in r])
	
	x=temp[:,0]
	y=temp[:,1]


	myLength=len(y)
	threshold=median_truncation/400.0
	ySortedIndex = np.argsort(y)
	y = y[ySortedIndex][int(threshold*myLength):int(myLength*(1-1*threshold))]
	x = x[ySortedIndex][int(threshold*myLength):int(myLength*(1-1*threshold))]
	
	xSortedIndex = np.argsort(x)
	y = y[xSortedIndex][int(threshold*myLength):int(myLength*(1-1*threshold))]
	x = x[xSortedIndex][int(threshold*myLength):int(myLength*(1-1*threshold))]

	
	myCov = np.cov(x,y)
	simple_slope = myCov[0,1]/myCov[0,0]
	
	non_serialized_result = np.array([np.mean(y*1.0/x),np.mean(y)/np.mean(1.0*x),simple_slope])
	#serialized_result = pickle.dumps(non_serialized_result)
	dict_result = {'shot_by_shot_median':np.median(y*1.0/x),'shot_by_shot':np.mean(y*1.0/x),'median':np.median(y)/np.median(1.0*x),'averaged':np.mean(y)/np.mean(1.0*x),'simple_slope':simple_slope}

	return dict_result


class dls_viewer(CustomViewer):
	name = 'dls_viewer'
	x = 'att(/GMD)'	#this switch swaps the x and y axes.
	y = 'att(/acqiris2)'	#need to figure out how to make this programable.  Replaced x and y with pop and viv, then need to rename in glue.
	#x = 'att'	#using above for quicker development
	#y = 'att'	#using above for quicker development
	bins = (25,300)
	median_truncation = (1,100)
	#more_bins =(-10,10)	#this adds bins 
	z = 'att(/atm_corrected_timing)'
	ephoton = 'att(/ebeam/photon_energy)'
	shot_by_shot = False
	the_slope = False
	modulation_spectroscopy = False
	#color = ['Reds', 'Purples']
	#hit = 'att(shot_made)'
	my_offset = 5
	my_offset_index = 0
	#test = {"testing":123,"testing_testing":456}



	def __init__(self, widget_instance):
		if(3==sys.version_info[0]):
			super().__init__(widget_instance)
		else:
			CustomViewer.__init__(self,widget_instance)
		self.test = "testing"
		self.my_sub_groups = {}
	
	"""def make_selector(self, roi, x, y):

		state = RoiSubsetState()
		state.roi = roi
		state.xatt = x.id
		state.yatt = y.id
		state.x=0
		state.y=1
		state.z=2
		return state"""

	def get_offset(self):
		print(self.my_sub_groups)
		
		return

	def plot_data(self, axes, x, y,z, style,bins):

		temp = 0


	def plot_subset(self, axes, x, y,z, style,bins,shot_by_shot,the_slope,median_truncation,state,modulation_spectroscopy,my_offset,my_offset_index):		
		binSize = (347.1-326.9)/bins
		tEdges = np.arange(326.9,347.1,binSize)
		my_hex_style_id = str(hex(id(style))) 
		my_hex_x_id = str(hash(frozenset(x)))
		my_hex_y_id = str(hash(frozenset(y)))


		print(""+str(dir(self.my_sub_groups)))
		print(""+str(self))
		#print(test)
		if my_hex_style_id not in self.my_sub_groups.keys():
			print("new hex id")
			
			self.my_sub_groups[my_hex_style_id]={"offset":my_offset,"x_id":my_hex_x_id,"y_id":my_hex_y_id}
			self.my_sub_groups[my_hex_style_id]['last_x_id'] = 0
			self.my_sub_groups[my_hex_style_id]['last_y_id'] = 0
			self.my_sub_groups[my_hex_style_id]['x_data'] = tEdges
			self.my_sub_groups[my_hex_style_id]['y_data'] = {}
		
		else:
			self.my_sub_groups[my_hex_style_id]["x_id"] = my_hex_x_id
			self.my_sub_groups[my_hex_style_id]["y_id"] = my_hex_y_id

		#print(self.my_sub_groups.keys())	
		chosen_id = list(self.my_sub_groups.keys())[int(my_offset_index)]
		self.my_sub_groups[chosen_id]["offset"] = my_offset
		this_offset = self.my_sub_groups[my_hex_style_id]["offset"]
		#this_offset=0
		
		#print(self.my_sub_groups[my_hex_style_id])

		#axes.plot(myHistogram[1][:-1],the_dls[::-1],mec=style.color,mfc=style.color,marker='o',linewidth=0)
		#print(dir(state))

		myValues = np.array([x,y]).transpose()
		if(the_slope):
			myStatistic = 'simple_slope'
		elif(shot_by_shot and not the_slope):
			myStatistic = 'shot_by_shot'
		elif(not shot_by_shot and not the_slope):
			myStatistic = 'averaged'

		def t_func_wrapper(r):
			return t_func(r,median_truncation)
		
		#the calculation below needs to be checked if it's already been calculated.  if not, don't re-calculate.
		x_not_changed = (self.my_sub_groups[my_hex_style_id]['x_id']==self.my_sub_groups[my_hex_style_id]['last_x_id'])
		y_not_changed = (self.my_sub_groups[my_hex_style_id]['y_id']==self.my_sub_groups[my_hex_style_id]['last_y_id'])
		if(not (x_not_changed and y_not_changed)):
			if(len(z)!=0):
				self.my_sub_groups[my_hex_style_id]['y_data'] = vectorized_binned_statistic_dd(z,myValues,bins=[tEdges],statistic=t_func_wrapper)	#square brackets around tEdges is important
				self.my_sub_groups[my_hex_style_id]['y_data'][myStatistic]-=np.mean(self.my_sub_groups[my_hex_style_id]['y_data'][myStatistic])	#normalization for displaying
				self.my_sub_groups[my_hex_style_id]['y_data'][myStatistic]/=np.std(self.my_sub_groups[my_hex_style_id]['y_data'][myStatistic])	#normalization for displaying
				
	
				#if (not modulation_spectroscopy):
				#	axes.plot(tEdges[:-1],myStats[myStatistic][::-1]+this_offset,c=style.color,marker='.',linewidth=2)
				#else:
				#	axes.plot(tEdges[:-1],np.cumsum(myStats['simple_slope'][::-1]/myStats['averaged'][::-1]),c=style.color,marker='.',linewidth=2)
		try:	
			myStats = self.my_sub_groups[my_hex_style_id]['y_data']
			axes.plot(tEdges[:-1],myStats[myStatistic][::-1]+this_offset,c=style.color,marker='.',linewidth=2)
		except:
			pass

		self.my_sub_groups[my_hex_style_id]['last_x_id'] = self.my_sub_groups[my_hex_style_id]['x_id']
		self.my_sub_groups[my_hex_style_id]['last_y_id'] = self.my_sub_groups[my_hex_style_id]['y_id']

	def setup(self, axes):
		temp =0 
		axes.set_ylim(-1, 10)
		axes.set_xlim(326, 347)
		#axes.set_aspect('equal', adjustable='datalim'
		#publish_glue_object_memory(id(self))
		self.t = threading.Thread(target=publish_glue_object_memory,args=(id(self),))
		self.t.start()

	#def __del__(self):
	#	self.t.stop()
		

	
