"""
Functions to convert a Newznab installation to Pynab.

NOTE: DESTRUCTIVE. DO NOT RUN ON ACTIVE PYNAB INSTALL.
(unless you know what you're doing)

"""

# if you're using pycharm, don't install the bson package
# it comes with pymongo
import os
import sys

import cymysql
import pymongo.errors


sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

from pynab.db import db
import config


def dupe_notice():
    error_text = '''
        If there are duplicate rageID/tvdbID/imdbID's in their
        respective tables, you'll need to trim duplicates first
        or these scripts will fail. You can do so with:

        alter ignore table tvrage add unique key (rageid);

        If they're running InnoDB you can't always do this, so
        you'll need to do:

        alter table tvrage engine myisam;
        alter ignore table tvrage add unique key (rageid);
        alter table tvrage engine innodb;
    '''

    print(error_text)


def mysql_connect(mysql_config):
    mysql = cymysql.connect(
        host=mysql_config['host'],
        port=mysql_config['port'],
        user=mysql_config['user'],
        passwd=mysql_config['passwd'],
        db=mysql_config['db']
    )

    return mysql


def convert_groups(mysql):
    """Converts Newznab groups table into Pynab. Only really
    copies backfill records and status."""
    # removed minsize/minfiles, since we're not really using them
    # most of the groups I index don't come up with too many stupid
    # releases, so if anyone has problem groups they can re-add it
    from_query = """
        SELECT name, first_record, last_record, active
        FROM groups;
    """

    print('Converting groups...')

    cursor = mysql.cursor()
    cursor.execute(from_query)

    if 'groups' in db.collection_names():
        db.groups.drop()

    groups = []
    for r in cursor.fetchall():
        group = {
            'name': r[0],
            'first': r[1],
            'last': r[2],
            'active': r[3]
        }
        groups.append(group)

    db.groups.insert(groups)


def convert_categories(mysql):
    """Convert Newznab categories table into Pynab."""
    from_query = """
        SELECT ID, title, parentID, minsizetoformrelease, maxsizetoformrelease
        FROM category;
    """

    print('Converting categories...')

    cursor = mysql.cursor()
    cursor.execute(from_query)

    if 'categories' in db.collection_names():
        db.categories.drop()

    categories = {}
    for r in cursor.fetchall():
        category = {
            '_id': r[0],
            'name': r[1],
            'parent_id': r[2],
            'min_size': r[3],
            'max_size': r[4]
        }

        db.categories.insert(category)


def convert_regex(mysql):
    """Converts Newznab releaseregex table into Pynab form. We leave the regex in
    PHP-form because it includes case sensitivity flags etc in the string."""
    from_query = """
        SELECT groupname, regex, ordinal, releaseregex.status, category.title, releaseregex.description
        FROM releaseregex
            LEFT JOIN category ON releaseregex.CategoryID = category.ID
        ORDER BY groupname;
        """

    print('Converting regex...')

    cursor = mysql.cursor()
    cursor.execute(from_query)

    if 'regexes' in db.collection_names():
        db.regexes.drop()

    regexes = []
    for r in cursor.fetchall():
        if r[4]:
            c_id = db.categories.find_one({'name': r[4]})['_id']
        else:
            c_id = None

        regex = {
            'group_name': r[0],
            'regex': r[1],
            'ordinal': r[2],
            'status': r[3],
            'description': r[5],
            'category_id': c_id
        }

        regexes.append(regex)

    db.regexes.insert(regexes)


def convert_blacklist(mysql):
    """Converts Newznab binaryblacklist table into Pynab format.
    This isn't actually used yet."""
    from_query = """
        SELECT groupname, regex, status, description
        FROM binaryblacklist
        ORDER BY id;
        """

    print('Converting blacklist...')

    cursor = mysql.cursor()
    cursor.execute(from_query)

    if 'blacklists' in db.collection_names():
        db.blacklists.drop()

    blacklists = []
    for r in cursor.fetchall():
        blacklist = {
            'group_name': r[0],
            'regex': r[1],
            'status': r[2],
            'description': r[3]
        }

        blacklists.append(blacklist)

    db.blacklists.insert(blacklists)


def convert_users(mysql):
    """Converts Newznab users table into Pynab format. More or less
    of this may be necessary depending on what people want. I'm pretty
    much just after bare API access, so we only really need rsstoken."""
    from_query = """
        SELECT username, email, password, rsstoken, userseed, grabs
        FROM users
        ORDER BY id;
        """

    print('Converting users...')

    cursor = mysql.cursor()
    cursor.execute(from_query)

    if 'users' in db.collection_names():
        db.users.drop()

    users = []
    for r in cursor.fetchall():
        user = {
            'email': r[1],
            'api_key': r[3],
            'grabs': r[5]
        }

        users.append(user)

    db.users.insert(users)


def convert_tvdb(mysql):
    """Converts Newznab tvdb table into Pynab format. Actually
    useful, since we re-use the same data regardless."""
    from_query = """
        SELECT tvdbID, seriesname
        FROM thetvdb
        WHERE tvdbID != 0 AND seriesname != ""
        ORDER BY seriesname;
        """

    print('Converting tvdb...')

    cursor = mysql.cursor()
    cursor.execute(from_query)

    if 'tvdb' in db.collection_names():
        db.tvdb.drop()

    tvdbs = []
    for r in cursor.fetchall():
        tvdb = {
            '_id': r[0],
            'name': r[1]
        }

        tvdbs.append(tvdb)

    try:
        db.tvdb.insert(tvdbs)
    except pymongo.errors.DuplicateKeyError:
        print('Error: Duplicate keys in TVDB MySQL table.')
        dupe_notice()
        print('Stopping script...')
        sys.exit(1)


def convert_tvrage(mysql):
    """Converts Newznab tvrage table into Pynab format."""
    from_query = """
        SELECT rageID, releasetitle
        FROM tvrage
        WHERE rageID > 0
        ORDER BY rageID
        """

    print('Converting tvrage...')

    cursor = mysql.cursor()
    cursor.execute(from_query)

    if 'tvrage' in db.collection_names():
        db.tvrage.drop()

    tvrages = []
    for r in cursor.fetchall():
        tvrage = {
            '_id': r[0],
            'name': r[1]
        }

        tvrages.append(tvrage)

    try:
        db.tvrage.insert(tvrages)
    except pymongo.errors.DuplicateKeyError:
        print('Error: Duplicate keys in TVRage MySQL table.')
        dupe_notice()
        print('Stopping script...')
        sys.exit(1)


def convert_imdb(mysql):
    """Converts Newznab imdb table into Pynab format."""
    from_query = """
        SELECT imdbID, title, year, language, genre
        FROM movieinfo
        WHERE imdbID > 0
        ORDER BY imdbID
        """

    print('Converting imdb...')

    cursor = mysql.cursor()
    cursor.execute(from_query)

    if 'imdb' in db.collection_names():
        db.imdb.drop()

    imdbs = []
    for r in cursor.fetchall():
        imdb = {
            '_id': r[0],
            'name': r[1],
            'year': r[2],
            'lang': r[3],
            'genre': [g.strip() for g in r[4].split(',')]
        }

        imdbs.append(imdb)

    try:
        db.imdb.insert(imdbs)
    except pymongo.errors.DuplicateKeyError:
        print('Error: Duplicate keys in IMDB MySQL table.')
        dupe_notice()
        print('Stopping script...')
        sys.exit(1)


if __name__ == '__main__':
    print('Convert Newznab to Pynab script.')
    print('Please note that this script is destructive and will wipe the following Mongo collections:')
    print('Groups, Categories, Regexes, Blacklists, Users, TVRage, IMDB, TVDB.')
    print('If you don\'t want some of these to be replaced, edit this script and comment those lines out.')
    print('Also ensure that you\'ve edited config.py to include the details of your MySQL server.')
    input('To continue, press enter. To exit, press ctrl-c.')

    mysql = mysql_connect(config.mysql)

    # comment lines out if you don't want those collections replaced
    convert_groups(mysql)
    convert_categories(mysql)
    convert_regex(mysql)
    convert_blacklist(mysql)
    convert_imdb(mysql)
    convert_tvdb(mysql)
    convert_tvrage(mysql)
    convert_users(mysql)

    print('Completed transfer. You can think about shutting down / removing MySQL from your server now.')
    print('Unless you\'re using it for something else, in which case that\'d be dumb.')