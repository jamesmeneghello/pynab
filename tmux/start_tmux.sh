#!/bin/bash

# find the pynab logs
SCRIPT_PATH=$( readlink -m $( type -p $0 ))      # Full path to script
SCRIPT_DIR=$( dirname ${SCRIPT_PATH} )           # Directory script is run in
LOGGING_DIR=$( grep logging_dir $SCRIPT_DIR/../config.py | awk -F\' '{print $4 }' )

byobu -2 new-session -d -s pynab

byobu new-window -t pynab:1 -n 'Pynab'
byobu send-keys "tail -f $LOGGING_DIR/stats.csv" C-m

byobu split-window -h -t 0 "tail -f $LOGGING_DIR/backfill.log"
byobu split-window -v  -t 1 "tail -f $LOGGING_DIR/postprocess.log" 
byobu split-window -v  -t 2 "tail -f $LOGGING_DIR/update.log" 

byobu select-pane -t 0

# from http://stackoverflow.com/a/22566549
layout=a822,211x52,0,0{63x52,0,0,1,147x52,64,0[147x14,64,0,2,147x18,64,15,3,147x18,64,34,6]}
byobu select-layout "$layout"

byobu attach-session -t pynab
