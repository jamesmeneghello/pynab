#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_scripts
----------------------------------

Tests for `scripts` module.
"""

import unittest

from scripts import convert_from_newznab
from pynab.db import db
import config as project_config


class TestScripts(unittest.TestCase):
    def setUp(self):
        self.test_connect()

    def test_connect(self):
        self.mysql = convert_from_newznab.mysql_connect(project_config.mysql)

        self.assertTrue(self.mysql)

    def test_convert_groups(self):
        convert_from_newznab.convert_groups(self.mysql)
        self.assertEqual(db.groups.count(), 23)

    def test_convert_categories(self):
        convert_from_newznab.convert_categories(self.mysql)
        self.assertEqual(db.categories.count(), 51)

    def test_convert_regex(self):
        convert_from_newznab.convert_regex(self.mysql)
        self.assertEqual(db.regexes.count(), 1736)

    def test_convert_users(self):
        convert_from_newznab.convert_users(self.mysql)
        self.assertEqual(db.users.count(), 28)

    def test_convert_tvdb(self):
        convert_from_newznab.convert_tvdb(self.mysql)
        self.assertEqual(db.tvdb.count(), 498)

    def test_convert_tvrage(self):
        convert_from_newznab.convert_tvrage(self.mysql)
        self.assertEqual(db.tvrage.count(), 14719)

    def test_convert_imdb(self):
        convert_from_newznab.convert_imdb(self.mysql)
        self.assertEqual(db.imdb.count(), 26771)

    def test_convert_releases(self):
        convert_from_newznab.convert_releases(self.mysql)

    def test_convert_all(self):
        self.test_convert_groups()
        self.test_convert_categories()
        self.test_convert_regex()
        self.test_convert_users()
        self.test_convert_tvdb()
        self.test_convert_tvrage()
        self.test_convert_imdb()
        self.test_convert_releases()

    def tearDown(self):
        self.mysql.close()


if __name__ == '__main__':
    unittest.main()