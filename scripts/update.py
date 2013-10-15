import argparse
import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

import pynab.groups
from pynab.db import db

parser = argparse.ArgumentParser(description='''
Fetch and parse parts and messages for active groups.

Updating a specific group will force an update regardless of whether the group is active.
Updating all groups will only update active groups.
''')
parser.add_argument('group', nargs='?', help='Group to update (leave blank for all)')

args = parser.parse_args()

if args.group:
    group = db.groups.find_one({'name': args.group})
    if group:
        if pynab.groups.update(group['name']):
            print('Group {0} successfully updated!'.format(group['name']))
        else:
            print('Problem updating group {0}.'.format(group['name']))
    else:
        print('No group called {0} exists in the db.'.format(args.group))
else:
    for group in db.groups.find({'active': 1}):
        if pynab.groups.update(group['name']):
            print('Group {0} successfully updated!'.format(group['name']))
        else:
            print('Problem updating group {0}.'.format(group['name']))