#!/bin/bash
export LD_LIBRARY_PATH=/reg/neh/home/cpo/junk
echo `hostname`
source /reg/g/psdm/etc/psconda.sh
python counter.py

##############################
####this is command line######
#`which mpirun` --oversubscribe -H daq-amo-mon02,daq-amo-mon03,daq-amo-mon04,daq-amo-mon05,daq-amo-mon06 -n 4 ./counter.sh
#`which mpirun` --oversubscribe -H daq-amo-mon04,daq-amo-mon05,daq-amo-mon06 -n 3 ./counter.sh
