#!/bin/bash

byobu -2 new-session -d -s pynab

byobu new-window -t pynab:1 -n 'Pynab'
byobu send-keys "tail -f /var/log/pynab/stats.csv" C-m
byobu split-window -h -t 0 "tail -f /var/log/pynab/backfill.log"

byobu split-window -v  -t 1 "tail -f /var/log/pynab/postprocess.log" 

byobu split-window -v  -t 2 "tail -f /var/log/pynab/update.log" 
byobu select-pane -t 0

# from http://stackoverflow.com/a/22566549
layout=a822,211x52,0,0{63x52,0,0,1,147x52,64,0[147x14,64,0,2,147x18,64,15,3,147x18,64,34,6]}
byobu select-layout "$layout"

byobu attach-session -t pynab
