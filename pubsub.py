"""
Pynab XMPP PubSub

Starts a JSON listener and XMPP bot that use pubsub to report
new releases to an XMPP server. Config in config.py.

Usage:
    pubsub.py start

Options:
    -h --help       Show this screen.
    --version       Show version.

"""

import pynab.xmpp
from docopt import docopt

if __name__ == '__main__':
    arguments = docopt(__doc__, version=pynab.__version__)
    if arguments['start']:
        server = pynab.xmpp.JSONPub()
        server.start()