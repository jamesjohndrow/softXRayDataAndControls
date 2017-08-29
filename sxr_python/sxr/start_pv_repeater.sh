#!/bin/bash

echo "Set up pyca for PYTHON 2.7.2"
source /reg/g/pcds/setup/pyca27.sh


export EPICS_CA_MAX_ARRAY_BYTES=8000000
export PSPKG_ROOT=/reg/common/package

export PSPKG_RELEASE="sxr-1.1.0"

source $PSPKG_ROOT/etc/set_env.sh

# Add script's directory to PYTHON path
SCRIPTDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd && echo x)"
SCRIPTDIR="${SCRIPTDIR%x}"
pythonpathmunge $SCRIPTDIR


python scripts/pv_repeater.py

