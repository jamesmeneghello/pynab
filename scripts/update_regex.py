import argparse
import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

import pynab.util

parser = argparse.ArgumentParser(description='''
Updates regex collection.
''')

args = parser.parse_args()

pynab.util.update_regex()