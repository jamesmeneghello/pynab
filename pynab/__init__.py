#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'James Meneghello'
__email__ = 'murodese@gmail.com'
__version__ = '1.0.0'

import logging
import config
import logging.handlers

log = logging.getLogger(__name__)
log.setLevel(config.site['logging_level'])

if config.site['logging_file']:
    handler = logging.handlers.RotatingFileHandler(config.site['logging_file'], maxBytes=config.site['max_log_size'], backupCount=5)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    log.addHandler(handler)
else:
    logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s')
