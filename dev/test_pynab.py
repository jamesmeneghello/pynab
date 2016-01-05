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


    def tearDown(self):
        try:
            self.server.connection.quit()
        except:
            pass


if __name__ == '__main__':
    unittest.main()