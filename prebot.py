"""
Pynab Prebot

Starts a prebot that listens on the #nZEDbPRE channel.

Usage:
    prebot.py start

Options:
    -h --help       Show this screen.
    --version       Show version.

"""
# Thanks to Joel Rosdahl <joel@rosdahl.net> for this script
# Taken from https://bitbucket.org/jaraco/irc/src


import irc.bot
import irc.strings
from docopt import docopt

import pynab.pre
from pynab import log_init, log
import config


class TestBot(irc.bot.SingleServerIRCBot):
    def __init__(self, channel, nickname, server, port=6667):
        irc.bot.SingleServerIRCBot.__init__(self, [(server, port)], nickname, nickname)
        self.channel = channel

    def on_nicknameinuse(self, c, e):
        c.nick(c.get_nickname() + "_")

    def on_welcome(self, c, e):
        c.join(self.channel)

    def on_pubmsg(self, c, e):
        a = e.arguments[0]
        pynab.pre.nzedbirc(a)


def main():
    channel = config.prebot.get('channel')
    nick = config.prebot.get('nick')
    server = config.prebot.get('server')
    port = config.prebot.get('port')

    log.info("Pre: Bot Nick - {}".format(nick))
    bot = TestBot(channel, nick, server, port)
    bot.start()


if __name__ == '__main__':
    arguments = docopt(__doc__, version=pynab.__version__)

    if arguments['start']:
        log_init('prebot')
        if config.prebot.get('nick'):
            main()
        else:
            log.warn("Pre: Bot nick not set in config, please update and restart the bot")