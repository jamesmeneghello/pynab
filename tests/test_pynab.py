#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_pynab
----------------------------------

Tests for `pynab` module.
"""

import unittest

from pynab import pynab
import config


class TestPynab(unittest.TestCase):
    def setUp(self):
        self.test_connect()

    def test_connect(self):
        self.server = pynab.connect(config.news)
        self.assertTrue(self.server)

    def test_capabilities(self):
        print(self.server.getcapabilities())

    def test_fetch_headers(self):
        pass

    def tearDown(self):
        self.server.quit()

if __name__ == '__main__':
    unittest.main()