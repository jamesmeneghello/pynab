import pymongo
from pynab.db import db
from pynab import log


def create_indexes():
    """Ensures that indexes for collections exist.
    Add all new appropriate indexes here. Gets called
    once per script run."""
    # rather than scatter index creation everywhere, centralise it so it only runs once

    # categories
    db.categories.ensure_index('name', pymongo.ASCENDING)
    db.categories.ensure_index('parent_id', pymongo.ASCENDING)

    # regexes
    db.regexes.ensure_index('group_name', pymongo.ASCENDING)
    db.regexes.ensure_index('category_id', pymongo.ASCENDING)

    # groups
    db.groups.ensure_index('name', pymongo.ASCENDING)

    # users
    db.users.ensure_index('username', pymongo.ASCENDING)
    db.users.ensure_index('email', pymongo.ASCENDING)
    db.users.ensure_index('rsstoken', pymongo.ASCENDING)

    # tvrage
    db.tvrage.ensure_index('_id', pymongo.ASCENDING, background=True)
    db.tvrage.ensure_index('name', pymongo.ASCENDING, background=True)

    # tvdb
    db.tvdb.ensure_index('_id', pymongo.ASCENDING)
    db.tvdb.ensure_index('name', pymongo.ASCENDING)

    # blacklists
    db.blacklists.ensure_index('group_name', pymongo.ASCENDING)

    # imdb
    db.imdb.ensure_index('_id', pymongo.ASCENDING)
    db.imdb.ensure_index('name', pymongo.ASCENDING)

    # binaries
    db.binaries.ensure_index('name', pymongo.ASCENDING, background=True)
    db.binaries.ensure_index('group_name', pymongo.ASCENDING, background=True)
    db.binaries.ensure_index('total_parts', pymongo.ASCENDING, background=True)

    # parts
    db.parts.ensure_index('subject', pymongo.ASCENDING, background=True)
    db.parts.ensure_index('group_name', pymongo.ASCENDING, background=True)

    # releases
    db.releases.ensure_index('id', pymongo.ASCENDING, background=True)
    db.releases.ensure_index('name', pymongo.ASCENDING, background=True)
    db.releases.ensure_index('category._id', pymongo.ASCENDING, background=True)
    db.releases.ensure_index('rage._id', pymongo.ASCENDING, background=True)
    db.releases.ensure_index('imdb._id', pymongo.ASCENDING, background=True)
    db.releases.ensure_index('tvdb._id', pymongo.ASCENDING, background=True)
    db.releases.ensure_index([
                                 ('search_name', 'text')
                             ], background=True)
    db.releases.ensure_index([
                                 ('tvrage._id', pymongo.ASCENDING),
                                 ('category._id', pymongo.ASCENDING)
                             ], background=True)
    db.releases.ensure_index([
                                 ('posted', pymongo.ASCENDING),
                                 ('category._id', pymongo.ASCENDING)
                             ], background=True)
    db.releases.ensure_index([
                                 ('posted', pymongo.ASCENDING),
                                 ('tvrage._id', pymongo.ASCENDING),
                                 ('category._id', pymongo.ASCENDING)
                             ], background=True)
    db.releases.ensure_index('passworded', pymongo.ASCENDING, background=True)
    #TODO: add sparse indexes related to postproc


if __name__ == '__main__':
    log.info('Creating indexes...')
    create_indexes()
    log.info('Completed. Mongo will build indexes in the background.')
