#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_pynab
----------------------------------

Tests for `pynab` module.
"""

import unittest

from pynab import pynab
import pynab.db as db
import config as project_config

class TestPynab(unittest.TestCase):
    def setUp(self):
        self.mongo = db.DB(project_config.db)
        self.server = None

    def test_connect(self):
        self.server = pynab.connect(project_config.news)
        self.assertTrue(self.server)

    def test_capabilities(self):
        self.test_connect()
        print(self.server.getcapabilities())

    def test_fetch_headers(self):
        self.test_connect()
        group = 'alt.binaries.teevee'
        (_, _, first, last, _) = self.server.group(group)
        for x in range(2000000, 2020000, 10000):
            y = x + 10000-1
            binaries = pynab.scan(self.server, group, last-y, last-x)
            pynab.save_binaries(self.mongo, binaries)

    def test_prepare_binaries(self):
        pynab.prepare_binaries(self.mongo)

    def test_process_binaries(self):
        pynab.process_binaries(self.mongo)

    def test_all(self):
        self.test_fetch_headers()
        self.test_prepare_binaries()
        self.test_process_binaries()

    def tearDown(self):
        if self.server:
            self.server.quit()

if __name__ == '__main__':
    unittest.main()