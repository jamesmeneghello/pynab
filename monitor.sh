#!/bin/bash

#
# Find byobu or tmux
#
BYOBU=$( which byobu )

if [ "$BYOBU" != "" ]  ; then 
    echo "Found byobu"
    CMD=$BYOBU
else
    TMUX=$( which tmux )
    if [ "$TMUX" = "" ] ; then
        echo "ERROR: You need to tmux or tmux+byobu installed to use this."
        exit 1
    fi
    CMD=$TMUX
    echo "Boybu not installed.  Using tmux."
fi


#
# find the pynab logs
#
SCRIPT_PATH=$( readlink -m $( type -p $0 ))      # Full path to script
SCRIPT_DIR=$( dirname ${SCRIPT_PATH} )           # Directory script is run in
LOGGING_DIR=$( grep logging_dir $SCRIPT_DIR/config.py | awk -F\' '{print $4 }' )


#
# start the byobu/tmux session
#
$CMD -2 new-session -d -s pynab
$CMD new-window -n 'Pynab'

$CMD send-keys "python3 $SCRIPT_DIR/scripts/stats.py" C-m

$CMD split-window -h -t 0 "tail -f $LOGGING_DIR/backfill.log"

# set the three panes to take even thirds of the vertical space. Second log pane uses 
# 66% of first. Next uses 1/2 of it or 33% of total.
$CMD split-window -v  -t 1 -p 66 "tail -f $LOGGING_DIR/postprocess.log" 
$CMD split-window -v  -t 2 -p 50 "tail -f $LOGGING_DIR/update.log" 

$CMD select-pane -t 0

$CMD resize-pane -t 0 -x 63    # fixed width stats pane. it won't survive window resize
$CMD attach-session -t pynab

# from http://stackoverflow.com/a/22566549
#
# To adjust the layout of panes, if you have the same number as in this script, you can 
# optionally run "tmux list-windows" and copy the output into the layout line below.
#
# layout=a822,211x52,0,0{63x52,0,0,1,147x52,64,0[147x14,64,0,2,147x18,64,15,3,147x18,64,34,6]}
# $CMD select-layout "$layout"

