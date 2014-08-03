#!/bin/bash
screen -d -m -S start python3 start.py
screen -d -m -S postprocess python3 postprocess.py
#screen -d -m -S backfill python3 backfill.py