#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'James Meneghello'
__email__ = 'murodese@gmail.com'
__version__ = '0.1.0'

import logging
import config

log = logging.getLogger(__name__)
logging.basicConfig(filename=config.site['logging_file'], level=config.site['logging_level'])