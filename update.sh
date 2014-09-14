#!/bin/bash
git pull
alembic upgrade head
pip3 install -r requirements.txt