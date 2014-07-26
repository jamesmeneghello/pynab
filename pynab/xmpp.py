import regex
import unicodedata
import difflib
from datetime import datetime

import requests
import pytz

from pynab import log
from pynab.db import db_session, Category
import config

from pynab.pubsub_client import PubsubClient
from xml.sax.saxutils import escape
import ssl

def process(q):
    bot = NabBot(q)
    bot.start()

class NabBot():

    def __init__(self, q):
        jid = config.bot['jid']
        password = config.bot['password']
        host = config.bot['host']
        xmpp = PubsubClient(jid, password, host)
        xmpp.register_plugin('xep_0199') # XMPP Ping
        xmpp.ssl_version = ssl.PROTOCOL_SSLv3

        self.q = q
        self.xmpp = xmpp
        self.categories = None

    def start(self):
        log.info("XMPP NabBot started.")
        if self.xmpp.connect():
            self.xmpp.process(block=False) # pynab.xmpp is started in its own thread
            #self.create_nodes() #I have autocreate set, don't need to pre-populate
            self.handle_queue()
        else:
            log.error("XMPP client didn't connect.")

    def stop(self):
        self.xmpp.disconnect()
        log.info("XMPP client disconnected.")


    def publish(self, guid, name, catid):
        categories = self.get_categories()
        data = "<name>{}</name><guid>{}</guid>".format(escape(name), guid)
        log.info("Publishing {} to {}[{}] at {}".format(data, categories[catid], catid, datetime.now()))
        try:
            self.xmpp.publish(str(catid), data)
        except:
            pass

    def handle_queue(self):
        while True:
            item = self.q.get(block=True)
            log.debug("Got item: {}".format(item))
            if len(item) != 3: continue
            guid, name, catid = item

            if not catid: continue # Skip "None"
            self.publish(guid, name, catid)

    def pubsub_nodes(self):
        #make a set of all the pubsub nodes that exist already
        existing = set()
        result = self.xmpp.nodes()
        if result and result['disco_items'] and result['disco_items']['items']:
            for item in result['disco_items']['items']:
                existing.add(int(item[1]))
        return existing

    def create_nodes(self):
        categories = set(self.categories().keys())
        existing = self.pubsub_nodes()
        log.debug("existing: {} :: categories: {}".format(existing, categories))
        for catid in categories - existing:
            log.warning("Creating node {}.".format(catid))
            self.xmpp.create(catid)

    def get_categories(self):
        if self.categories:
            return self.categories
        else:
            self.categories = {}
            with db_session() as db:
                for category in db.query(Category).all():
                    self.categories[int(category.id)] = category.name
            return self.categories

