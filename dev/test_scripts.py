#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_scripts
----------------------------------

Tests for `scripts` module.
"""

import unittest

import config as project_config
import pynab.util
from scripts import convert_from_newznab


class TestScripts(unittest.TestCase):
    def setUp(self):
        self.test_connect()

    def test_connect(self):
        self.mysql = convert_from_newznab.mysql_connect(project_config.mysql)

        self.assertTrue(self.mysql)

    def test_convert_groups(self):
        convert_from_newznab.convert_groups(self.mysql)

    def test_convert_categories(self):
        convert_from_newznab.convert_categories(self.mysql)

    def test_convert_regex(self):
        convert_from_newznab.convert_regex(self.mysql)

    def test_convert_blacklist(self):
        convert_from_newznab.convert_blacklist(self.mysql)

    def test_convert_users(self):
        convert_from_newznab.convert_users(self.mysql)

    def test_convert_tvdb(self):
        convert_from_newznab.convert_tvdb(self.mysql)

    def test_convert_tvrage(self):
        convert_from_newznab.convert_tvrage(self.mysql)

    def test_convert_imdb(self):
        convert_from_newznab.convert_imdb(self.mysql)

    def test_update_regex(self):
        pynab.util.update_regex()

    def test_update_blacklist(self):
        pynab.util.update_blacklist()

    def test_convert_all(self):
        self.test_convert_groups()
        self.test_convert_categories()
        self.test_convert_regex()
        self.test_convert_blacklist()
        self.test_convert_users()
        self.test_convert_tvdb()
        self.test_convert_tvrage()
        self.test_convert_imdb()

    def tearDown(self):
        self.mysql.close()


if __name__ == '__main__':
    unittest.main()