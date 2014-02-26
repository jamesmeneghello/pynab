#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'James Meneghello'
__email__ = 'murodese@gmail.com'
__version__ = '1.1.0'

import logging
import config
import logging.handlers

log = logging.getLogger(__name__)
log.setLevel(config.log.get('logging_level', logging.DEBUG))

logging_file = config.log.get('logging_file')
log_descriptor = None

if logging_file:
    handler = logging.handlers.RotatingFileHandler(logging_file, maxBytes=config.log.get('max_log_size', 50*1024*1024), backupCount=5, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    log.addHandler(handler)
    log_descriptor = handler.stream.fileno()
else:
    logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s')
