#!/bin/bash

tmux new -s pynab \; attach \; new-window "teamocil --layout teamocil/standard.yml"
