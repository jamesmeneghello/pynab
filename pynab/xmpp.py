from datetime import datetime
from xml.sax.saxutils import escape
import ssl
import multiprocessing
import json

from sleekxmpp.xmlstream import ET, tostring
import sleekxmpp
import eventlet
import eventlet.wsgi

from pynab import log
from pynab.db import db_session, Category
import config


def process(queue):
    bot = NabBot(queue)
    bot.start()


class JSONPub:
    def __init__(self):
        self.event_queue = multiprocessing.Queue()

    def handler(self, env, start_response):
        release = json.loads(env['wsgi.input'].read().decode('utf-8'))
        self.event_queue.put([release['id'], release['name'], release['category_id']])

        start_response('200 OK', [('Content-Type', 'application/json')])
        return [json.dumps({'status': 'ok'}).encode('utf-8')]

    def start(self):
        multiprocessing.Process(target=process, args=(self.event_queue,)).start()
        eventlet.wsgi.server(eventlet.listen(config.bot.get('listen')), self.handler)


class NabBot:
    def __init__(self, q):
        jid = config.bot['jid']
        password = config.bot['password']
        host = config.bot['host']
        xmpp = PubsubClient(jid, password, host)
        xmpp.register_plugin('xep_0199')  # XMPP Ping
        xmpp.ssl_version = ssl.PROTOCOL_SSLv3

        self.q = q
        self.xmpp = xmpp
        self.categories = None

    def start(self):
        log.info("nabbot: xmpp bot started")
        if self.xmpp.connect():
            self.xmpp.process(block=False)  # pynab.xmpp is started in its own thread
            # self.create_nodes() #I have autocreate set, don't need to pre-populate
            self.handle_queue()
        else:
            log.error("nabbot: client didn't connect.")

    def stop(self):
        self.xmpp.disconnect()
        log.info("nabbot: client disconnected.")

    def publish(self, guid, name, catid):
        categories = self.get_categories()
        data = "<name>{}</name><guid>{}</guid>".format(escape(name), guid)
        log.info("nabbot: publishing {} to {}[{}] at {}".format(data, categories[catid], catid, datetime.now()))
        try:
            self.xmpp.publish(str(catid), data)
            pass
        except:
            pass

    def handle_queue(self):
        while True:
            item = self.q.get(block=True)
            log.debug("nabbot: got item: {}".format(item))
            if len(item) != 3: continue
            guid, name, catid = item

            if not catid:
                # Skip "None"
                continue
            self.publish(guid, name, catid)

    def pubsub_nodes(self):
        # make a set of all the pubsub nodes that exist already
        existing = set()
        result = self.xmpp.nodes()
        if result and result['disco_items'] and result['disco_items']['items']:
            for item in result['disco_items']['items']:
                existing.add(int(item[1]))
        return existing

    def create_nodes(self):
        categories = set(self.categories().keys())
        existing = self.pubsub_nodes()
        log.debug("nabbot: existing: {} :: categories: {}".format(existing, categories))
        for catid in categories - existing:
            log.warning("nabbot: creating node {}.".format(catid))
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


class PubsubClient(sleekxmpp.ClientXMPP):
    def __init__(self, jid, password, server, node=None, action='nodes', data=''):
        super(PubsubClient, self).__init__(jid, password)

        self.register_plugin('xep_0030')
        self.register_plugin('xep_0059')
        self.register_plugin('xep_0060')

        self.actions = ['nodes', 'create', 'delete',
                        'publish', 'get', 'retract',
                        'purge', 'subscribe', 'unsubscribe']

        self.action = action
        self.node = node
        self.data = data
        self.pubsub_server = server
        self.add_event_handler('session_start', self.start, threaded=True)

    def start(self, event):
        self.get_roster()
        self.send_presence()

        try:
            getattr(self, self.action)()
        except:
            log.error('pubsub: could not execute: %s' % self.action)

    def nodes(self):
        try:
            result = self['xep_0060'].get_nodes(self.pubsub_server, self.node)
            return result
        except:
            log.error('pubsub: could not retrieve node list.')

    def create(self, node=None):
        if not node:
            node = self.node
        try:
            self['xep_0060'].create_node(self.pubsub_server, node)
        except:
            log.error('pubsub: could not create node: %s' % node)

    def delete(self):
        try:
            self['xep_0060'].delete_node(self.pubsub_server, self.node)
            print('Deleted node: %s' % self.node)
        except:
            log.error('pubsub: could not delete node: %s' % self.node)

    def publish(self, node, data):
        payload = ET.fromstring("<test xmlns='test'>{}</test>".format(data))
        try:
            self['xep_0060'].publish(self.pubsub_server, node, payload=payload)
        except Exception as e:
            log.error('pubsub: could not publish to: {}'.format(node))
            log.error('Exception "{}" of type {}'.format(e, type(e)))

    def get(self):
        try:
            result = self['xep_0060'].get_item(self.pubsub_server, self.node, self.data)
            for item in result['pubsub']['items']['substanzas']:
                print('Retrieved item %s: %s' % (item['id'], tostring(item['payload'])))
        except:
            log.error('pubsub: could not retrieve item %s from node %s' % (self.data, self.node))

    def retract(self):
        try:
            result = self['xep_0060'].retract(self.pubsub_server, self.node, self.data)
            print('Retracted item %s from node %s' % (self.data, self.node))
        except:
            log.error('pubsub: could not retract item %s from node %s' % (self.data, self.node))

    def purge(self):
        try:
            result = self['xep_0060'].purge(self.pubsub_server, self.node)
            print('Purged all items from node %s' % self.node)
        except:
            log.error('pubsub: could not purge items from node %s' % self.node)

    def subscribe(self):
        try:
            result = self['xep_0060'].subscribe(self.pubsub_server, self.node)
            print('Subscribed %s to node %s' % (self.boundjid.bare, self.node))
        except:
            log.error('pubsub: could not subscribe %s to node %s' % (self.boundjid.bare, self.node))

    def unsubscribe(self):
        try:
            result = self['xep_0060'].unsubscribe(self.pubsub_server, self.node)
            print('Unsubscribed %s from node %s' % (self.boundjid.bare, self.node))
        except:
            log.error('pubsub: could not unsubscribe %s from node %s' % (self.boundjid.bare, self.node))