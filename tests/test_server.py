#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_server
----------------------------------

Tests for `server` module.
"""

import unittest
import pprint
from pynab.server import Server
from pynab.db import db

class TestServer(unittest.TestCase):
    def setUp(self):
        self.server = Server()
        self.server.connect()

    def test_scan(self):
        group = 'alt.binaries.teevee'
        (_, _, first, last, _) = self.server.connection.group(group)

        binaries = []
        for x in range(0, 200, 100):
            y = x + 100-1
            binaries = self.server.scan(group, last-y, last-x)

        self.assertNotEqual(len(binaries), 0)

    def tearDown(self):
        pass
    
if __name__ == '__main__':
    unittest.main()