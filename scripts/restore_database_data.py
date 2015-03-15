#!/usr/bin/env python3
"""
Restore Database Data

Restore critical data necessary for a working installation.  You will need to
also import a set of NZB files or just start scanning/backfilling.

Usage:
  restore_database_data.py [--users=FILE] [--groups=FILE] [--categories=FILE] [--movie=FILE] [--tvshow=FILE]

Options:
  -h --help             Show help
  --version             Show version
  --users=FILE          Data file for user data
  --groups=FILE         Data file for group data
  --categories=FILE     Data file for category data
  --movie=FILE          Data file for movie data
  --tvshow=FILE         Data file for tvshow data

"""

import gzip
import json
import os
import sys

from docopt import docopt

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

import pynab
from pynab.db import db_session, truncate_table, engine, Group, User, TvShow, Movie, Category

dbmap = {
    'users': User,
    'groups': Group,
    'categories': Category,
    'movie': Movie,
    'tvshow': TvShow
}

if __name__ == '__main__':

    arguments = docopt(__doc__, version=pynab.__version__)
    print("""
    Restore Database Data script.
    Please note that this script is destructive.
    Any tables specified on the command line will be cleared and replaced.
    """)
    input('To continue, press enter.  To exit, press ctrl-c.')

    print("WARNING: Depending on how much data you have, this may take awhile.")

    with db_session() as db:
        for table in dbmap:
            arg = '--%s' % (table,)
            if arguments[arg]:
                filename = arguments[arg]
                try:
                    if filename.endswith('.gz'):
                        with gzip.open(filename) as infile:
                            data = json.loads(infile.read().decode('utf=8'))
                    else:
                        with open(filename) as infile:
                            data = json.load(infile)
                except Exception as e:
                    # Even though we failed to open the file, other files may be
                    # fine so just issue the warning and continue along.
                    print("Failed to open {}: {}\nSkipping table {}.".format(filename,
                                                                             e,
                                                                             table))
                    continue

                if truncate_table(engine, dbmap[table]):
                    print("Truncated {} table.".format(table))
                else:
                    # database may now be in a bad state, best to exit and let
                    # the user sort things out.
                    print("Failed to truncate {} table, exiting.".format(table))
                    sys.exit(0)

                try:
                    engine.execute(dbmap[table].__table__.insert(), data)
                except Exception as e:
                    print("Problem inserting data into table {}: {}".format(table,
                                                                            e))
