# Thanks to Joel Rosdahl <joel@rosdahl.net> for this script
# Taken from https://bitbucket.org/jaraco/irc/src

import irc.bot
import irc.strings
from irc.client import ip_numstr_to_quad, ip_quad_to_numstr
import string
import random
import pynab.pre
from pynab import log, log_descriptor
import argparse

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

def daemonize(pidfile):
    try:
        import traceback
        from daemonize import Daemonize

        fds = []
        if log_descriptor:
            fds = [log_descriptor]

        daemon = Daemonize(app='prebot', pid=pidfile, action=main, keep_fds=fds)
        daemon.start()
    except SystemExit:
        raise
    except:
        log.critical(traceback.format_exc())

def main():
    import sys

    channel = "#nZEDbPRE"
    nickname = ''.join([random.choice(string.ascii_letters + string.digits) for n in range(8)])
    log.info("Pre: Bot Nick - {}".format(nickname))
    bot = TestBot(channel, nickname, "irc.synirc.net", 6667)
    bot.start()

if __name__ == '__main__':
    argparser = argparse.ArgumentParser(description="Pynab prebot")
    argparser.add_argument('-d', '--daemonize', action='store_true', help='run as a daemon')
    argparser.add_argument('-p', '--pid-file', help='pid file (when -d)')

    args = argparser.parse_args()
    if args.daemonize:
        pidfile = args.pid_file or config.scan.get('pid_file')
        if not pidfile:
            log.error("A pid file is required to run as a daemon, please supply one either in the config file '{}' or as argument".format(config.__file__))
        else:
            daemonize(pidfile)
    else:
        main()