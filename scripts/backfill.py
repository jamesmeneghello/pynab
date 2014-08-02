import argparse
import os
import sys
import dateutil.parser
import pytz

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

import pynab.groups
from pynab.db import db_session, Group

parser = argparse.ArgumentParser(description='''
Backfill:
Fetch and parse parts and messages for active groups.

Updating a specific group will force an update regardless of whether the group is active.
Updating all groups will only update active groups.
''')
parser.add_argument('-g', '--group', nargs='?', help='Group to backfill (leave blank for all)')
parser.add_argument('-d', '--date', nargs='?', help='Date to backfill to (leave blank to use default backfill_days)')

args = parser.parse_args()

with db_session() as db:
    print('Starting backfill. Ensure that dead_binary_age is set to 0 in config.py!')
    if args.group:
        group = db.query(Group).filter(Group.name==args.group).first()
        if group:
            if args.date:
                args.date = pytz.utc.localize(dateutil.parser.parse(args.date))
            else:
                args.date = None
            if pynab.groups.backfill(group.name, args.date):
                print('Group {0} successfully backfilled!'.format(group.name))
            else:
                print('Problem backfilling group {0}.'.format(group.name))
        else:
            print('No group called {0} exists in the db.'.format(args.group))
    else:
        for group in db.query(Group).filter(Group.active==True).all():
            if pynab.groups.backfill(group.name):
                print('Group {0} successfully backfilled!'.format(group.name))
            else:
                print('Problem backfilling group {0}.'.format(group.name))