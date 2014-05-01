#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'James Meneghello'
__email__ = 'murodese@gmail.com'
__version__ = '1.2.0'

import logging
import config
import logging.handlers
import os
import colorlog
import inspect
import sys

log = logging.getLogger(__name__)
log.setLevel(config.log.get('logging_level', logging.DEBUG))

logging_file = config.log.get('logging_file')
log_descriptor = None

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

if logging_file:
    frame = inspect.currentframe()
    info=inspect.getouterframes(frame)
    c=0
    for n in info:
        if n[4] and c > 1: # c > 1 skips this module itself
            if n[3] == '<module>': # from my testing (on Windows), the first module found is the calling module
                break
        c += 1
    if c >= len(info):
        sys.exit(1)
    name, _ = os.path.splitext(os.path.basename(inspect.stack()[c][1].rstrip(os.sep)))
    file, ext = os.path.splitext(config.log.get('logging_file'))
    logging_file = ''.join([file, '_', name, ext])

    handler = logging.handlers.RotatingFileHandler(logging_file, maxBytes=config.log.get('max_log_size', 50*1024*1024), backupCount=5, encoding='utf-8')
    handler.setFormatter(formatter)
    log.addHandler(handler)
    log_descriptor = handler.stream.fileno()
else:
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    log.addHandler(handler)

# set up root_dir for use with templates etc
root_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
