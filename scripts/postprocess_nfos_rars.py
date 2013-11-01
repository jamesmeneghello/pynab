import argparse
import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

import pynab.groups
import pynab.nfos
import pynab.rars

parser = argparse.ArgumentParser(description='''
Post-process NFOs and RARs for a particular category.

Note that this will process all of the releases in the specified category,
and could take a long time.
''')
parser.add_argument('category', help='(Sub)Category ID to post-process')

args = parser.parse_args()

if args.category:
    pynab.nfos.process(0, args.category)
    pynab.rars.process(0, args.category)