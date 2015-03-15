#!/usr/bin/env python3
"""
Backup Database Data

Backup user critical data necessary for restoring an installation to working
order.  NOTE: This does not include NZB files, you need to export those
separately.

Usage:
  backup_database_data.py [--gzip] [--no-users] [--no-groups] [--no-categories] [--no-movie] [--no-tvshow] PATH

Arguments:
  PATH                Path where backup data will be written

Options:
  -h --help           Show help
  --version           Show version
  --gzip              Gzip each output file
  --no-users          Do not backup user data
  --no-groups         Do not backup group data
  --no-categories     Do not backup category data
  --no-movie          Do not backup movie data
  --no-tvshow         Do not backup tvshow data

"""

import gzip
import json
import os
import sys

from docopt import docopt
from sqlalchemy.ext.declarative import DeclarativeMeta

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

import pynab
from pynab.db import db_session, Group, User, TvShow, Movie, Category

# Custom encoder to handles outputing for just our basic columns
class BackupEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj.__class__, DeclarativeMeta):
            fields = dict()
            for col in obj.__class__.__table__.columns:
                data = obj.__getattribute__(col.name)
                try:
                    # this will fail on non-encodable values, like other classes
                    json.dumps(data)
                    fields[col.name] = data
                except TypeError:
                    fields[col.name] = None
            # a json-encodable dict
            return fields
        return json.JSONEncoder.default(self, obj)


filemap = {
    'users': (User, 'users.dat'),
    'groups': (Group, 'groups.dat'),
    'categories': (Category, 'categories.dat'),
    'movie': (Movie, 'movie.dat'),
    'tvshow': (TvShow, 'tvshow.dat'),
}

def data_filename(table, use_gzip):
    filename = '/'.join([arguments['PATH'], filemap[table][1]])
    if use_gzip:
        filename += '.gz'
    return filename

if __name__ == '__main__':

    arguments = docopt(__doc__, version=pynab.__version__)

    if not os.path.isdir(arguments['PATH']):
        raise Exception("{} is not a vaid path.".format(arguments['PATH']))
    if not os.access(arguments['PATH'], os.W_OK):
        raise Exception("Unable to write files to {}.".format(arguments['PATH']))

    if arguments['--gzip']:
        use_gzip = True
    else:
        use_gzip = False

    print("WARNING: Depending on how much data you have, this may take awhile.")

    with db_session() as db:
        for table in filemap:
            argcheck = '--no-%s' % (table,)
            if not arguments[argcheck]:
                print("Querying data from {} table.".format(table))
                data = db.query(filemap[table][0]).all()
                filename = data_filename(table, use_gzip)
                print("Backing up {} data to {}.".format(table, filename))
                if use_gzip:
                    with gzip.GzipFile(filename, 'w') as outfile:
                        outfile.write(bytes(json.dumps(data, cls=BackupEncoder),
                                            "utf-8"))
                else:
                    with open(filename, 'w') as outfile:
                        outfile.write(json.dumps(data, indent=4, cls=BackupEncoder))
