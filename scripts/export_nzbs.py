#!/usr/bin/env python3
"""
Usage:
  export_nzbs.py [--verbose] PATH

Arguments:
  PATH          Path where exported NZBs will be written

Options:
  -h --help     Show help
  -v --verbose  Verbose output
"""

import os
import sys
import uuid

from docopt import docopt

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

import pynab

def create_path(base_path, fileid):
    path = '/'.join([base_path, fileid[:1]])
    os.makedirs(path, exist_ok=True)
    return path

def export_nzbs(base_path):
    with db_session() as db:
        total_releases = db.query(Release).count()
        print("Exporting nzb files for {} releases, this may take awhile.".format(total_releases))
        count = 0
        error = 0
        for release in db.query(Release).all():
            fileid = str(uuid.uuid4()).replace('-', '')+str(release.nzb_id)+".gz"
            path = create_path(base_path, fileid)
            filepath = '/'.join([path, fileid])
            if arguments['--verbose']:
                print("Release ID: %s\nPath: %s" % (release.nzb_id, filepath))
            try:
                with open(filepath, 'wb') as f:
                    f.write(release.nzb.data)
                count += 1
            except:
                print("Error exporting nzb for release {}.".format(release.id))
                error += 1
    print("Exported {} nzbs, {} errors.".format(count, error))


if __name__ == '__main__':
    arguments = docopt(__doc__, version=pynab.__version__)

    if not os.path.isdir(arguments['PATH']):
        raise Exception("{} is not a vaid path.".format(arguments['PATH']))
    if not os.access(arguments['PATH'], os.W_OK):
        raise Exception("Unable to write files to {}.".format(arguments['PATH']))

    export_nzbs(arguments['PATH'])
