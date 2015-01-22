import sys, os
from datetime import date
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

from pynab.db import engine

result = engine.execute('select pg_catalog.date(added),count(*) from releases group by pg_catalog.date(added)')

for item in result.fetchall():
    print ("%s %10d" % (item[0].strftime("%Y-%m-%d"), item[1]))
