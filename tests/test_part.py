#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_part
----------------------------------

Tests for `part` module.
"""

import unittest

from pynab.part import Part
from pynab.segment import Segment
from pynab.db import db

class TestPart(unittest.TestCase):
    def setUp(self):
        db.parts.save({'subject': 'bob', 'total_segments': 5, 'group_name': 'alt.binaries.fred'})
        db.parts.save({'subject': 'max', 'total_segments': 3, 'group_name': 'alt.binaries.bob'})

    def test_set(self):
        p = Part.get_one(subject='bob')
        self.assertEqual(p.subject, 'bob')

    def test_get(self):
        p = Part.get(subject={'$regex': 'bo'})
        self.assertEqual(len(p), 1)

        p = Part.get()
        self.assertEqual(len(p), 2)

    def test_get_extra(self):
        p = Part.get(subject='bob', exhaust=True)
        self.assertEqual(len(p), 1)

    def test_transform(self):
        s = Segment('asd', 1, 123)
        p = Part('roger', segments=[s, ])
        p.save()

        print(Part.get_one(subject='roger').dict())

    def test_dict(self):
        s = Segment('asd', 1, 123)
        p = Part('roger', segments=[s, ])
        import pprint
        pprint.pprint(p.dict())

    def tearDown(self):
        db.parts.drop()
    
if __name__ == '__main__':
    unittest.main()