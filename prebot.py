# Thanks to Joel Rosdahl <joel@rosdahl.net> for this script
# Taken from https://bitbucket.org/jaraco/irc/src

import irc.bot
import irc.strings
import string
import random
import pynab.pre
from pynab import log_init


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
    channel = "#nZEDbPRE"
    nickname = ''.join([random.choice(string.ascii_letters + string.digits) for n in range(8)])
    print(nickname)
    bot = TestBot(channel, nickname, "irc.synirc.net", 6667)
    bot.start()

if __name__ == "__main__":
    log_init('prebot')
    main()