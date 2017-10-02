## Add the number of cores and the host IPs in place of question marks in lines 9 and 10
. /reg/neh/operator/amoopr/experiments/amolq1415/setup-bash-slac.sh
#. setup-bash.sh
echo Running `pwd`/monitor_wrapper.sh
echo '#!/bin/bash' > `pwd`/monitor_wrapper.sh
echo '# Auto-generated file from run_onda_photofragmentation_slac.sh' >> `pwd`/monitor_wrapper.sh
echo '. /reg/neh/operator/amoopr/experiments/amolq1415/setup-bash-slac.sh' >> `pwd`/monitor_wrapper.sh
echo python /reg/neh/operator/amoopr/experiments/amolq1415/onda-20170713-photofragmentation/onda.py 'shmem=psana.0:stop=no' >> `pwd`/monitor_wrapper.sh
chmod +x `pwd`/monitor_wrapper.sh
#`which mpirun` --oversubscribe --map-by ppr:4:node --host daq-amo-mon04,daq-amo-mon05,daq-amo-mon06 `pwd`/monitor_wrapper.sh
`which mpirun` --oversubscribe --map-by ppr:4:node --host daq-amo-mon06 `pwd`/monitor_wrapper.sh
