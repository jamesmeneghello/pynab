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


def check_config():
    config = __import__('config')
    config_sample = __import__('config_sample')
    exclude = lambda x: '__' not in x and x != 'logging'

    missing = False
    top_level = set(filter(exclude, dir(config_sample))) - set(filter(exclude, dir(config)))
    if top_level:
        print('Top level config items missing: \'{}\''.format(', '.join(top_level)))
        missing = True

    reverse_level = set(filter(exclude, dir(config_sample))) - set(filter(exclude, dir(config)))
    if reverse_level:
        print('Some extra top level config items that should be deleted: \'{}\''.format(', '.join(reverse_level)))

    for item in filter(exclude, dir(config)):
        inner_level = set(getattr(config_sample, item).keys()) - set(getattr(config, item).keys())
        if inner_level:
            print('Config element \'{}\' is missing: {}'.format(item, ', '.join(inner_level)))
            missing = True

    if missing:
        print('Check config_sample.py and copy missing items to config.py before running again.')
        exit(1)


def log_init(log_name, format='%(asctime)s %(levelname)s %(message)s'):
    if config.log.get('logging_dir', None):
        global log

        logging_file = os.path.join(logging_dir, log_name + '.log')
        handler = logging.handlers.RotatingFileHandler(logging_file, maxBytes=config.log.get('max_log_size', 50*1024*1024), backupCount=5, encoding='utf-8')
        handler.setFormatter(logging.Formatter(format, '%Y-%m-%d %H:%M:%S'))
        log.handlers = []
        log.addHandler(handler)

    log.info('log: started pynab logger')


log = logging.getLogger(__name__)
log.setLevel(config.log.get('logging_level', logging.DEBUG))

logging_dir = config.log.get('logging_dir', None)
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

elif not config.log.get('colors', False):
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%Y-%m-%d %H:%M:%S'))
    log.addHandler(handler)
else:
    formatter = colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s - %(levelname)s - %(reset)s %(blue)s%(message)s",
        '%Y-%m-%d %H:%M:%S',
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

check_config()
