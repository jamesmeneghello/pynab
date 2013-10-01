#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_scripts
----------------------------------

Tests for `scripts` module.
"""

import unittest

from scripts import convert_from_newznab
from pynab import db
import config as project_config


class TestScripts(unittest.TestCase):
    def setUp(self):
        self.test_connect()

    def test_connect(self):
        self.mysql = convert_from_newznab.mysql_connect(project_config.mysql)
        self.mongo = db.DB(project_config.db)

        self.assertTrue(self.mysql)
        self.assertTrue(self.mongo)

    def test_convert_groups(self):
        convert_from_newznab.convert_groups(self.mysql, self.mongo)

    def test_convert_categories(self):
        convert_from_newznab.convert_categories(self.mysql, self.mongo)
        self.assertEqual(self.mongo.db().categories.count(), 51)

    def test_convert_regex(self):
        convert_from_newznab.convert_regex(self.mysql, self.mongo)

    def tearDown(self):
        self.mongo.close()
        self.mysql.close()

if __name__ == '__main__':
    unittest.main()