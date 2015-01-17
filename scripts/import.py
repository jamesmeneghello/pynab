import argparse
import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

from pynab import log
import pynab.nzbs
import scripts.recategorise_everything

parser = argparse.ArgumentParser(
    description='Recursively import NZBs into Pynab. NOTE: DESTRUCTIVE. Will delete NZB upon successful import. Don\'t run it on a directory you may need to use again.')
parser.add_argument('directory')

if __name__ == '__main__':
    args = parser.parse_args()

    print(
        'NOTE: DESTRUCTIVE. Will delete NZB upon successful import. Don\'t run it on a directory you may need to use again.')
    input('To continue, press enter. To exit, press ctrl-c.')

    for root, dirs, files in os.walk(args.directory):
        for name in files:
            print('Importing {0}...'.format(os.path.join(root, name)))
            try:
                if pynab.nzbs.import_nzb_file(os.path.join(root, name)):
                    os.remove(os.path.join(root, name))
            except Exception as e:
                log.error(str(e))
                continue
                
    log.info('Import completed. Running scripts/recategorise_everything.py to fix release categories...')
    scripts.recategorise_everything.recategorise()
    log.info('Completed.')
