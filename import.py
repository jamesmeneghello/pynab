import argparse
import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), ''))

import pynab.nzb

parser = argparse.ArgumentParser(description='Recursively import NZBs into Pynab.')
parser.add_argument('directory')

args = parser.parse_args()

for root, dirs, files in os.walk(args.directory):
    for name in files:
        print('Importing {0}...'.format(os.path.join(root, name)))
        if pynab.nzb.import_nzb(os.path.join(root, name)):
            os.remove(os.path.join(root, name))

print('Import completed. Consider running scripts/process_uncategorised.py now to fix release categories.')