import argparse
import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

from pynab import log
import pynab.nzb
import scripts.process_uncategorised

parser = argparse.ArgumentParser(description='Recursively import NZBs into Pynab.')
parser.add_argument('directory')

if __name__ == '__main__':
    args = parser.parse_args()

    for root, dirs, files in os.walk(args.directory):
        for name in files:
            print('Importing {0}...'.format(os.path.join(root, name)))
            if pynab.nzb.import_nzb(os.path.join(root, name)):
                os.remove(os.path.join(root, name))

    log.info('Import completed. Running scripts/process_uncategorised.py to fix release categories...')
    scripts.process_uncategorised.fix_uncategorised()
    log.info('Completed.')