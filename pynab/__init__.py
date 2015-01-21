#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'James Meneghello'
__email__ = 'murodese@gmail.com'
__version__ = '1.4.0'

import logging
import config
import logging.handlers
import os
import colorlog
import sys


def log_init(log_name):
    global log_descriptor, log

    logging_file = os.path.join(logging_dir, log_name + '.log')
    handler = logging.handlers.RotatingFileHandler(logging_file, maxBytes=config.log.get('max_log_size', 50*1024*1024), backupCount=5, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    log.addHandler(handler)
    log_descriptor = handler.stream.fileno()
    log.info('log: started pynab logger')


log = logging.getLogger(__name__)
log.setLevel(config.log.get('logging_level', logging.DEBUG))

logging_dir = config.log.get('logging_dir')
log_descriptor = None

# catch old configs
if config.log.get('logging_file') and not config.log.get('logging_dir'):
    logging_dir = os.path.dirname(os.path.abspath(config.log.get('logging_file')))

if logging_dir:
    name, _ = os.path.splitext(os.path.basename(sys.argv[0].rstrip(os.sep)))

    try:
        if not os.path.exists(logging_dir):
            os.makedirs(logging_dir)
    except Exception as e:
        print('error: logfile not accessible. permissions error?')
        print(e)
        exit(1)

    log_init(name)

elif config.log.get('colors', False):
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    log.addHandler(handler)
else:
    formatter = colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s - %(levelname)s - %(reset)s %(blue)s%(message)s",
        datefmt=None,
        reset=True,
        log_colors={
            'DEBUG':    'cyan',
            'INFO':     'green',
            'WARNING':  'yellow',
            'ERROR':    'red',
            'CRITICAL': 'red',
        }
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    log.addHandler(handler)

# set up root_dir for use with templates etc
root_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
