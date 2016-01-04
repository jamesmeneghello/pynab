#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_pynab
----------------------------------

Tests for `pynab` module.
"""

import unittest
from pprint import pformat

from pynab.server import Server
from pynab.db import db_session
import pynab.parts
from pynab import log
import regex
from pynab.categories import extract_features

class TestPynab(unittest.TestCase):
    def setUp(self):
        self.server = None

    def test_connect(self):
        self.server = Server()
        self.server.connect()
        self.assertTrue(self.server)

    def test_capabilities(self):
        self.test_connect()
        print(self.server.connection.getcapabilities())

    def test_fetch_headers(self):
        self.test_connect()
        groups = ['alt.binaries.teevee']
        for group in groups:
            (_, _, first, last, _) = self.server.connection.group(group)
            for x in range(0, 40000, 20000):
                y = x + 20000 - 1
                parts = self.server.scan(group, last - y, last - x)
                pynab.parts.save_all(parts)

    def test_group_update(self):
        import pynab.groups
        pynab.groups.update('alt.binaries.teevee')

    def test_request_process(self):
        import pynab.requests
        pynab.requests.process()

    def test_update_pres(self):
        from scripts.nzedb_pre_import import largeNzedbPre, nzedbPre
        largeNzedbPre()
        nzedbPre()

    def test_process_binaries(self):
        import pynab.binaries
        pynab.binaries.process()

    def test_process_releases(self):
        import pynab.releases
        pynab.releases.process()

    def test_update_blacklist(self):
        import pynab.util
        pynab.util.update_blacklist()

    def test_update_regex(self):
        import pynab.util
        pynab.util.update_regex()

    def test_process_requests(self):
        import pynab.requests
        pynab.requests.process()

    def test_quick_postproc(self):
        import scripts.quick_postprocess

        scripts.quick_postprocess.local_postprocess()

    def test_process_ids(self):
        import pynab.ids

        pynab.ids.process('movie')

    def test_remove_metablacks(self):
        from pynab.db import MetaBlack
        with db_session() as db:
            db.query(MetaBlack).delete()
            db.commit()

    def test_search_releases(self):
        from sqlalchemy_searchable import search
        from pynab.db import Release

        with db_session() as db:
            q = db.query(Release)
            q = search(q, 'engaged e06')
            print(q.first().search_name)

    def test_nzb_parse(self):
        import pynab.nzbs
        from pynab.db import NZB

        with db_session() as db:
            nzb = db.query(NZB).filter(NZB.id==1).one()
            import pprint
            pprint.pprint(pynab.nzbs.get_nzb_details(nzb))

    def test_scrape_nzbsu(self):
        import requests
        import time
        from bs4 import BeautifulSoup

        url = 'https://api.nzb.su/api?apikey=4d901407e99ae6c942416585c8a44673'
        ua = {'User-agent': 'CouchPotato 3.0.1'}
        results = []

        for category in [5020,5030,5040,5050,5060,5070,5080,2010,2020,2030,2040,2050,2060,2070,4010,4020,4030,1010,1020,1030,1050,1080,1090,1100,4050,3010,3020,3030,3040,3050,7010,7020,7030,6010,6020,6030,6040,6050,6060,6070,8010]:
            data = requests.get(url + '&t=search&cat={}&o=json'.format(category), headers=ua).json()
            if 'item' in data['channel']:
                results.extend(data['channel']['item'])

        with open('dog_releases.csv', 'w', encoding='utf-8') as f:
            f.write('"r","name","name","category_id","name","name"\r\n')
            # turn results into useful data
            for i, result in enumerate(results):
                try:
                    resp = requests.get(url + '&t=details&id={}'.format(result['attr'][3]['@attributes']['value']), headers=ua)
                    soup = BeautifulSoup(resp.text)
                    group = soup.find(attrs={'name':'group'})['value']
                    f.write('"{}","{}","{}","{}","{}","{}"\r\n'.format(i, result['title'], group, result['attr'][1]['@attributes']['value'], *result['category'].split(' > ')))
                    time.sleep(5)
                except:
                    continue

    def test_categorise(self):
        import nltk
        import regex
        import csv
        import random
        import pprint

        #def determine_category(name, group_name=''):

        def load_data(filename):
            with open(filename, encoding='utf-8') as f:
                f.readline()
                csvfile = csv.reader(f, delimiter=',', quotechar='"')
                data = []
                for line in csvfile:
                    features = extract_features(line[1])
                    features['group'] = line[2]
                    features['name'] = line[1]
                    data.append((features, line[3]))

                random.shuffle(data)

            return data

        train_data = load_data('tagged_releases_train.csv')
        test_data = load_data('tagged_releases_test.csv')
        nzbsu_data = load_data('tagged_releases_test_nzbsu.csv')

        train_set = train_data
        test_set = test_data
        nzbsu_set = nzbsu_data

        classifier = nltk.NaiveBayesClassifier.train(train_set)

        from pickle import dump
        with open('release_categoriser.pkl', 'wb') as out:
            dump(classifier, out, -1)

        errors = []
        for features, tag in nzbsu_set:
            guess = classifier.classify(features)
            if guess[:2] != tag[:2]:
                errors.append((tag, guess, features))

        for tag, guess, features in errors:
            print('correct={} guess={} name={}'.format(tag, guess, features['name'].encode('utf-8')))

        print(classifier.show_most_informative_features())
        print('test: {}'.format(nltk.classify.accuracy(classifier, test_set)))
        print('test: {}'.format(nltk.classify.accuracy(classifier, nzbsu_set)))

    def test_load_and_categorise(self):
        from pynab.db import db_session, Release, Group, windowed_query
        from pickle import load

        with open('release_categoriser.pkl', 'rb') as cat_file:
            categoriser = load(cat_file)

        with db_session() as db:
            errors = []
            i = 0
            query = db.query(Release).join(Group)
            count = query.count()
            for result in windowed_query(query, Release.id, 500):
                features = extract_features(result.name)
                features['group'] = result.group.name
                features['name'] = result.name

                guess = categoriser.classify(features)
                if guess[:2] != str(result.category_id)[:2]:
                    errors.append((result.category_id, guess, features))

                i += 1
                if i % 500 == 0:
                    print('{} - {:.3f}%'.format((i/count)*100, (1 - (len(errors) / i)) * 100))

        for tag, guess, features in errors:
            print('correct={} guess={} name={}'.format(tag, guess, features['name'].encode('utf-8')))

        print('accuracy={}'.format(1 - (len(errors)/i)))

    def tearDown(self):
        try:
            self.server.connection.quit()
        except:
            pass


if __name__ == '__main__':
    unittest.main()