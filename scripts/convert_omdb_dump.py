import sys
import os
import pymongo.errors

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

from pynab.db import db


def convert_omdb_dump():
    db.imdb.drop()
    with open('C:\\temp\\omdb.txt', encoding='latin1') as f:
        f.readline()
        for line in f:
            data = line.split('\t')
            imdb = {
                '_id': data[1],
                'name': data[2],
                'year': data[3],
                'genre': [d.strip() for d in data[6].split(',')]
            }
            try:
                db.imdb.insert(imdb)
            except pymongo.errors.DuplicateKeyError as e:
                pass
            print('{}'.format(data[2]))


if __name__ == '__main__':
    convert_omdb_dump()