import logging
import time
import unittest

from pynab.db import db
from pynab import tvrage 


tvrage.log.setLevel(logging.DEBUG)

class TestTvRage(unittest.TestCase):
    def test_search(self):
        for release in db.releases.find({'tvrage.possible': {'$exists': False}}):
            show = tvrage.parse_show(release['search_name'])
            if show:
                rage_data = tvrage.search(show)
                time.sleep(1)

if __name__ == '__main__':
    unittest.main()