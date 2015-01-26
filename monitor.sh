#!/bin/bash

#
# discover pynab paths
#
SCRIPT_PATH=$( readlink -m $( type -p $0 ))      # Full path to script
SCRIPT_DIR=$( dirname ${SCRIPT_PATH} )           # Directory script is run in
LOGGING_DIR=$( grep \'logging_dir\' $SCRIPT_DIR/config.py | awk -F\' '{print $4 }' )

#
# Find byobu or tmux
#
BYOBU=$( which byobu )

if [ "$BYOBU" != "" ]  ; then 
    echo "Found byobu"
    echo
    echo "Byobu keys:"
    echo "   Alt-F1             Help / Show all keys"
    echo "   Alt-Left/Right     move to next/prev window"
    echo
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
# MAIN window
#
$CMD -2 new-session -d -s pynab -n 'MAIN' "tail -F $LOGGING_DIR/stats.log"
$CMD split-window -h "echo 'WARNING|ERROR|CRITICAL errors from all logs' ; tail -F $LOGGING_DIR/*.log  | egrep \"WARNING|ERROR|CRITICAL\""

$CMD resize-pane -t 0 -x 87    # fixed width stats pane won't survive window resize
$CMD select-pane -t 1

#
# LOGS window - four even-horizontal panes
#
$CMD new-window -t 1 -n 'LOGS' "tail -F $LOGGING_DIR/postprocess.log" 
$CMD split-window -v "tail -F $LOGGING_DIR/backfill.log" 
$CMD split-window -v "tail -F $LOGGING_DIR/update.log"
$CMD select-layout even-vertical
$CMD split-window -h "tail -F $LOGGING_DIR/prebot.log"
$CMD select-pane -t 0                                   # highlight 
$CMD split-window -h "bash"                             # split top window and add this
$CMD select-pane -t 2                                   # highlight 

$CMD select-window -t 'MAIN'

$CMD attach-session -t pynab


# from http://stackoverflow.com/a/22566549
#
# To adjust the layout of panes, if you have the same number as in this script, you can 
# optionally run "tmux list-windows" and copy the output into the layout line below rather
# than messing with tmux layouts, which are clunky.
#
# layout=a822,211x52,0,0{63x52,0,0,1,147x52,64,0[147x14,64,0,2,147x18,64,15,3,147x18,64,34,6]}
# $CMD select-layout "$layout"

