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

from docopt import docopt

import pynab.xmpp

from pynab import log_init


if __name__ == '__main__':
    arguments = docopt(__doc__, version=pynab.__version__)
    if arguments['start']:
        log_init('pubsub')
        server = pynab.xmpp.JSONPub()
        server.start()