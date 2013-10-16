import argparse
import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

import pynab.users

parser = argparse.ArgumentParser(description='''Create a new user.''')
parser.add_argument('email', help='Email address of user')

args = parser.parse_args()

if args.email:
    key = pynab.users.create(args.email)
    print('User created. API key is: {}'.format(key))