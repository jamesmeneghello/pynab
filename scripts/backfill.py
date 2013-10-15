import argparse
import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

import pynab.groups
from pynab.db import db

parser = argparse.ArgumentParser(description='''
Backfill:
Fetch and parse parts and messages for active groups.

Updating a specific group will force an update regardless of whether the group is active.
Updating all groups will only update active groups.
''')
parser.add_argument('group', nargs='?', help='Group to backfill (leave blank for all)')
parser.add_argument('date', nargs='?', help='Date to backfill to (leave blank to use default backfill_days)')

args = parser.parse_args()

if args.group:
    group = db.groups.find_one({'name': args.group})
    if group:
        if pynab.groups.backfill(group['name']):
            print('Group {0} successfully backfilled!'.format(group['name']))
        else:
            print('Problem backfilling group {0}.'.format(group['name']))
    else:
        print('No group called {0} exists in the db.'.format(args.group))
else:
    for group in db.groups.find({'active': 1}):
        if pynab.groups.backfill(group['name']):
            print('Group {0} successfully backfilled!'.format(group['name']))
        else:
            print('Problem backfilling group {0}.'.format(group['name']))