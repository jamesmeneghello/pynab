import argparse
import os
import sys
import uuid

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

from pynab.db import db_session, Release

# http://stackoverflow.com/questions/11415570/directory-path-types-with-argparse
class writeable_dir(argparse.Action):
    def __call__(self,parser, namespace, values, option_string=None):
        prospective_dir=values
        if not os.path.isdir(prospective_dir):
            raise argparse.ArgumentTypeError("writeable_dir:{0} is not a valid path".format(prospective_dir))
        if os.access(prospective_dir, os.W_OK):
            setattr(namespace,self.dest,prospective_dir)
        else:
            raise argparse.ArgumentTypeError("writeable_dir:{0} is not a writeable dir".format(prospective_dir))


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
            if args.verbose:
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
    parser = argparse.ArgumentParser()

    parser.add_argument("export_path", metavar="PATH",
                        help="Path where nzb files will be exported.",
                        action=writeable_dir)

    parser.add_argument("--verbose","-v", action="store_true",
                        help="Turn on verbose output.")

    args = parser.parse_args()

    export_nzbs(args.export_path)
