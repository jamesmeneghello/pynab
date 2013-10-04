#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_pynab
----------------------------------

Tests for `pynab` module.
"""

import unittest
import pprint

from pynab import pynab
from pynab.server import Server
from pynab.segment import Segment
from pynab.part import Part
from pynab.binary import Binary
from pynab.release import Release
from pynab.db import db


class TestPynab(unittest.TestCase):
    def setUp(self):
        self.server = None

    def test_connect(self):
        self.server = Server()
        self.server.connect()

    def test_capabilities(self):
        self.test_connect()
        print(self.server.connection.getcapabilities())

    def test_scan_and_save(self):
        self.test_connect()
        group = 'alt.binaries.teevee'
        (_, _, first, last, _) = self.server.connection.group(group)
        all_parts = []
        for x in range(0, 10000, 5000):
            y = x + 5000-1
            parts = self.server.scan(group, last-y, last-x)
            print(parts)

        save_parts = [p.dict() for p in all_parts]
        db.parts.insert(save_parts)

    def test_b_process(self):
        Binary.process()

    def test_r_process(self):
        Release.process()

    def test_stuff(self):
        s1 = Segment('rgr')
        p1 = Part('buttes', segments=[s1])
        b1 = Binary('asd', parts=[p1])
        b1.save()


        s2 = Segment('asd')
        p2 = Part('buttes', segments=[s1, s2])
        b1.parts.append(p2)
        b1.save()

        b3 = Binary.get_one(name='asd')
        pprint.pprint(b3.parts)


    def tearDown(self):
        if self.server:
            self.server.connection.quit()

if __name__ == '__main__':
    unittest.main()