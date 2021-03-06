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
import sys
import time
import ctypes
import random
import threading



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
	dict_result = {'shot_by_shot_median':np.median(y*1.0/x),'shot_by_shot_average':np.mean(y*1.0/x),'median':np.median(y)/np.median(1.0*x),'average':np.mean(y)/np.mean(1.0*x),'slope':simple_slope}

	return dict_result

def normalize_statistic(y):

	x = y - np.mean(y)
	x/=np.std(x)

	return x
	


class dls_viewer(CustomViewer):

	name = 'dls_viewer'
	#importing data
	x = 'att(/GMD)'	#this switch swaps the x and y axes.
	y = 'att(/acqiris2)'	#need to figure out how to make this programable.  Replaced x and y with pop and viv, then need to rename in glue.
	z = 'att(/atm_corrected_timing)'
	#x = 'att'	#using above for quicker development
	#y = 'att'	#using above for quicker development
	#z = 'att'
	
	#selection settings
	Subset_Number = 1
	#stored_value = 0	#each subset can have multiple stored values in self.my_subsets. how to make it so they don't get deleted when changing?
	
	#calculation settings
	bin_start = 326.9
	bin_end = 347.1
	n_bins = 150
	median_truncation = 1
	statistic_type =["average","median","shot_by_shot_average","shot_by_shot_median", "slope"]
	toggler = True
	#display settings
	offset = 0
	normalized = True

	#apply settings. plot_subset only does this when true.  Should normally be false to prevent frivolous recalculation. would ideally be button
	apply_settings = True

	def __init__(self, widget_instance):
		if(3==sys.version_info[0]):
			super().__init__(widget_instance)
		else:
			CustomViewer.__init__(self,widget_instance)
		
		self.my_subsets = {}
		self.to_display = {}
		self.my_self = ctypes.cast(id(self),ctypes.py_object)	#this allows for saved values to be written to the "option widget"'s fields'.
		self.last_chosen_id = '0'
		self.last_selected_layer = 'None'

		self.t = threading.Thread(target=self.check_layer_select)
		self.t.start()

	def make_selector(self, roi, x, y):

		state = RoiSubsetState()
		state.roi = roi
		state.xatt = x.id
		state.yatt = y.id
		print("selector roi =" +str(roi))
		return state


	def check_layer_select(self):
		while(True):
			if(str(self.my_self.value.widget.selected_layer)!=self.last_selected_layer):
				print("switched layer "+str(self.my_self.value.widget.selected_layer))
				self.my_self.value.widget.toggler = not self.my_self.value.widget.toggler
				self.last_selected_layer=str(self.my_self.value.widget.selected_layer)
			time.sleep(.3)
			

	def plot_data(self, axes, x, y,z, style,n_bins):

		temp = 0

	#plots all subsets unless I put in the conditional
	def plot_subset(self, axes, x, y,z, style,Subset_Number, bin_start, bin_end,n_bins,median_truncation, statistic_type,offset,normalized,apply_settings,toggler):		

		#identify the subset coming in
		my_hex_style_id = str(hex(id(style)))

		#hash the values to prevent frivolous recalculation 
		my_hex_x_id = str(hash(frozenset(x)))
		my_hex_y_id = str(hash(frozenset(y)))


		#calculation setup

		#make new subset state if one doesn't already exist	
		if my_hex_style_id not in self.my_subsets.keys():
			self.my_subsets[my_hex_style_id]={"offset":0,"x_id":my_hex_x_id,"y_id":my_hex_y_id,"Subset_Number":len(self.my_subsets)+1}
			self.my_subsets[my_hex_style_id]['last_x_id'] = 0
			self.my_subsets[my_hex_style_id]['last_y_id'] = 0
			self.my_subsets[my_hex_style_id]['x_data'] = np.arange(bin_start,bin_end,(bin_end-bin_start)/n_bins)
			self.my_subsets[my_hex_style_id]['last_x_data'] = np.zeros(len(self.my_subsets[my_hex_style_id]['x_data']))
			self.my_subsets[my_hex_style_id]['y_data'] = {}
			self.my_subsets[my_hex_style_id]['offset'] = 0
			self.my_subsets[my_hex_style_id]['median_truncation'] = 1
			self.my_subsets[my_hex_style_id]['last_median_truncation'] = 1
			self.my_subsets[my_hex_style_id]["statistic_type"] = statistic_type
			self.my_subsets[my_hex_style_id]["last_statistic_type"] = statistic_type
			self.my_subsets[my_hex_style_id]["bin_start"] = bin_start
			self.my_subsets[my_hex_style_id]['bin_end'] = bin_end
			self.my_subsets[my_hex_style_id]['n_bins'] = n_bins 
			self.my_subsets[my_hex_style_id]['normalized'] = normalized
			self.my_subsets[my_hex_style_id]['subset_number'] = str(len(self.my_subsets))
		
		#otherwise store the hash values to prevent frivolous recalculation	
		else:
			self.my_subsets[my_hex_style_id]["x_id"] = my_hex_x_id
			self.my_subsets[my_hex_style_id]["y_id"] = my_hex_y_id


		#tell rest of code which subset is being used #associate hex style id with subset number
		if(Subset_Number>0 and Subset_Number<=len(self.my_subsets)):
			chosen_id = list(self.my_subsets.keys())[int(Subset_Number-1)]	#would like way that access "subset_number" entry to set this.
		else:
			#print("new subset line")		
		
			#print("subset number = "+str(self.my_subsets[my_hex_style_id]['subset_number']))

			this_layer_number = str(self.my_self.value.widget.selected_layer)[24:]	#uses the plot layers to select it
			#print("selected layer = " + this_layer_number)

			chosen_id_test = [i for i in self.my_subsets if this_layer_number == self.my_subsets[i]['subset_number']]

			if (len(chosen_id_test)==0):
				chosen_id_test = list(self.my_subsets.keys())[0]
		
			#print("chosen_id_test = "+str(chosen_id_test)+" and chosen id = "+str(chosen_id))
			chosen_id = chosen_id_test[0]
		

		##################################################################################
		##############If this is a known subset, load the settings to widget##############
		##################################################################################
		if((chosen_id==my_hex_style_id) and (self.last_chosen_id!=chosen_id) and (self.last_chosen_id!='0')):
		
			self.my_self.value.redraw_on_settings_change=False
			self.my_self.value.widget.offset = str(self.my_subsets[chosen_id]["offset"])
			self.my_self.value.widget.median_truncation = str(self.my_subsets[chosen_id]['median_truncation'])
			#self.my_self.value.widget.statistic_type = str(self.my_subsets[chosen_id]["statistic_type"])
			self.my_self.value.widget.bin_start = str(self.my_subsets[chosen_id]["bin_start"])
			self.my_self.value.widget.bin_end = str(self.my_subsets[chosen_id]["bin_end"])
			self.my_self.value.widget.n_bins = str(self.my_subsets[chosen_id]["n_bins"])
			self.my_self.value.widget.normalized = self.my_subsets[chosen_id]["normalized"]
			self.my_self.value.redraw_on_settings_change=True

		
		#apply the set parameters indicated in the argument to the identified members. should generally be off to prevent shitty values
		if(apply_settings):
			##################################################################################
			##############This code below is applied only on the selected subset##############
			##################################################################################
			#other plot_subset routines don't need to change this data.
			#applying new settings to data
			if((chosen_id==my_hex_style_id)and (self.last_chosen_id==chosen_id) ):
				#apply the offset
				self.my_subsets[chosen_id]["offset"] = offset

				#calculation setup: apply new bins
				self.my_subsets[chosen_id]['x_data'] = np.arange(bin_start,bin_end,(bin_end-bin_start)/n_bins)
				my_edges = self.my_subsets[chosen_id]['x_data']

				self.my_subsets[chosen_id]['median_truncation'] = median_truncation

				self.my_subsets[chosen_id]["statistic_type"] = statistic_type
				self.my_subsets[chosen_id]["bin_start"] = bin_start
				self.my_subsets[chosen_id]['bin_end'] = bin_end
				self.my_subsets[chosen_id]['n_bins'] = n_bins 
				self.my_subsets[chosen_id]['normalized'] = normalized			
			
			myValues = np.array([x,y]).transpose()

			#apply the median truncation to the user statistic function
			def t_func_wrapper(r):
				return t_func(r,self.my_subsets[chosen_id]['median_truncation'])
	
			#conditional below check if it's already been calculated.  if not, don't re-calculate. should always be recalculated or at least checked
			x_changed = (self.my_subsets[my_hex_style_id]['x_id']!=self.my_subsets[my_hex_style_id]['last_x_id'])	#these to save space
			y_changed = (self.my_subsets[my_hex_style_id]['y_id']!=self.my_subsets[my_hex_style_id]['last_y_id'])	#these to save space
			med_trunc_changed = (self.my_subsets[my_hex_style_id]['median_truncation']!=self.my_subsets[my_hex_style_id]['last_median_truncation']) 
			bins_changed = hash(frozenset(self.my_subsets[my_hex_style_id]['last_x_data']))!=hash(frozenset(self.my_subsets[my_hex_style_id]['x_data']))
			#this is where space is saved.
			if( (bins_changed or x_changed or y_changed or med_trunc_changed) and len(z)!=0):

				#calculation is placed in the subsets
				#square brackets around my_edges below is important
				self.my_subsets[my_hex_style_id]['y_data'] = vectorized_binned_statistic_dd(z,myValues,bins=[self.my_subsets[my_hex_style_id]['x_data']],statistic=t_func_wrapper)


		######################################################################
		##############This code below is applied on every subset##############
		######################################################################
		#displaying settings. needs to display every line otherwise it's deleted when plot_subset is called
		
		this_statistic_type = self.my_subsets[my_hex_style_id]["statistic_type"]
		if(normalized and len(self.my_subsets[my_hex_style_id]['y_data'])>0):
			self.to_display['d']  = normalize_statistic(self.my_subsets[my_hex_style_id]['y_data'][this_statistic_type])+self.my_subsets[my_hex_style_id]['offset']
		elif(not normalized and len(self.my_subsets[my_hex_style_id]['y_data'])>0):		
			self.to_display['d']  = self.my_subsets[my_hex_style_id]['y_data'][this_statistic_type]+self.my_subsets[my_hex_style_id]['offset']
		

		if(len(self.to_display)>0):
			axes.plot(self.my_subsets[my_hex_style_id]['x_data'][:-1],self.to_display['d'][::-1],c=style.color,marker='.',linewidth=2)

		
	
		#keeping track of last id to prevent frivolous recalculation 
		self.my_subsets[my_hex_style_id]['last_x_id'] = self.my_subsets[my_hex_style_id]['x_id']
		self.my_subsets[my_hex_style_id]['last_y_id'] = self.my_subsets[my_hex_style_id]['y_id']
		self.my_subsets[my_hex_style_id]['last_median_truncation'] = self.my_subsets[my_hex_style_id]['median_truncation']
		self.my_subsets[my_hex_style_id]['last_x_data'] = self.my_subsets[my_hex_style_id]['x_data']
		self.my_subsets[my_hex_style_id]["last_statistic_type"] = self.my_subsets[my_hex_style_id]["statistic_type"]
		if(chosen_id==my_hex_style_id):
			self.last_chosen_id = chosen_id

	def setup(self, axes):
		temp = 0 
		axes.set_ylim(-5, 15)
		axes.set_xlim(326, 347)
		#self.t.start()

	
