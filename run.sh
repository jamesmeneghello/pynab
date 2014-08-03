#!/bin/bash
screen -d -m -S start python3 start.py
screen -d -m -S postprocess python3 postprocess.py
#screen -d -m -S backfill python3 backfill.py
echo Pynab started. If you\'re not using file logging, you can access the shells with screen -r start or screen -r postprocess.
