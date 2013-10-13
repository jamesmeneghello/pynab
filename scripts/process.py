import argparse
import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), ''))

import pynab.binaries
import pynab.releases

parser = argparse.ArgumentParser(description='''
Process binaries and releases for all parts stored in the database.

This pretty much just runs automatically and does its own thing.
''')

args = parser.parse_args()

pynab.binaries.process()
pynab.releases.process()