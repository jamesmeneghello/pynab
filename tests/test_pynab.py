#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_pynab
----------------------------------

Tests for `pynab` module.
"""

import unittest
import pprint

from pynab.server import Server
from pynab.db import db
import pynab.binaries
import pynab.releases
import pynab.parts
import pynab.categories
import pynab.groups
import pynab.nzb
import pynab.tvrage
import pynab.imdb


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
        groups = ['alt.binaries.teevee', 'alt.binaries.e-book', 'alt.binaries.moovee']
        for group in groups:
            (_, _, first, last, _) = self.server.connection.group(group)
            for x in range(0, 20000, 10000):
                y = x + 10000 - 1
                parts = self.server.scan(group, last - y, last - x)
                pynab.parts.save_all(parts)

    def test_process_binaries(self):
        pynab.binaries.process()

    def test_process_releases(self):
        pynab.releases.process()

    def test_all(self):
        self.test_fetch_headers()
        self.test_process_binaries()
        self.test_process_releases()

    def test_print_binaries(self):
        pprint.pprint([b for b in db.binaries.find()])

    def test_day_to_post(self):
        self.test_connect()
        self.server.day_to_post('alt.binaries.teevee', 5)

    def test_group_update(self):
        pynab.groups.update('alt.binaries.e-book.technical')

    def test_group_backfill(self):
        pynab.groups.backfill('alt.binaries.teevee')

    def test_nzb_import(self):
        pynab.nzb.import_nzb('c:\\temp\\nzbs\\The.Legend.of.Korra.S02E05.720p.WEB-DL.DD5.1.H.264-BS.nzb')

    def test_nfo_scan(self):
        release = db.releases.find_one()
        #pynab.nfos.scan(release)

    def test_tvrage_process(self):
        pynab.tvrage.process(100)

    def test_omdb_search(self):
        print(pynab.imdb.search('South Park Bigger Longer Uncut', '1999'))

    def test_omdb_get_details(self):
        print(pynab.imdb.get_details('tt1285016'))

    def test_nzb_get(self):
        release = db.releases.find_one()
        pprint.pprint(pynab.nzb.get_nzb_dict(release['nzb']))

    def tearDown(self):
        try:
            self.server.connection.quit()
        except:
            pass


if __name__ == '__main__':
    unittest.main()