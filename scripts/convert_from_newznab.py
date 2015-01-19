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


sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

from pynab.db import db_session, Group, Category, Release, User, TvShow, Movie
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

    print('Converting groups...')

    with db_session() as db:
        from_query = """
            SELECT name, first_record, last_record, active
            FROM groups;
        """
        cursor = mysql.cursor()
        cursor.execute(from_query)

        for r in cursor.fetchall():
            g = db.query(Group).filter(Group.name==r[0]).first()
            if not g:
                g = Group(name=r[0])

            g.first = r[1]
            g.last = r[2]
            g.active = bool(r[3])

            db.add(g)


def convert_categories(mysql):
    """Convert Newznab categories table into Pynab."""

    print('Converting categories...')

    with db_session() as db:
        from_query = """
            SELECT ID, title, parentID, minsizetoformrelease, maxsizetoformrelease
            FROM category;
        """

        cursor = mysql.cursor()
        cursor.execute(from_query)

        db.query(Category).delete()

        for r in cursor.fetchall():
            c = Category(
                id=r[0],
                name=r[1],
                parent_id=r[2],
                min_size=r[3],
                max_size=r[4]
            )

            db.add(c)


def convert_users(mysql):
    """Converts Newznab users table into Pynab format. More or less
    of this may be necessary depending on what people want. I'm pretty
    much just after bare API access, so we only really need rsstoken."""

    print('Converting users...')

    with db_session() as db:

        from_query = """
            SELECT username, email, password, rsstoken, userseed, grabs
            FROM users
            ORDER BY id;
        """

        cursor = mysql.cursor()
        cursor.execute(from_query)

        db.query(User).delete()

        for r in cursor.fetchall():
            u = User(
                email=r[1],
                api_key=r[3],
                grabs=r[5]
            )
            db.add(u)


def convert_tvrage(mysql):
    """Converts Newznab tvrage table into Pynab format."""

    print('Converting tvrage...')

    with db_session() as db:
        from_query = """
            SELECT rageID, releasetitle, country
            FROM tvrage
            WHERE rageID > 0
            ORDER BY rageID
        """
        cursor = mysql.cursor()
        cursor.execute(from_query)

        for r in cursor.fetchall():
            tvshow = db.query(TvShow).filter(TvShow.id==r[0]).first()
            if not tvshow:
                # only add it if it doesn't exist, don't update it
                tvshow = TvShow(id=r[0], name=r[1], country=r[2])
                db.add(tvshow)


def convert_imdb(mysql):
    """Converts Newznab imdb table into Pynab format."""

    print('Converting imdb...')

    with db_session() as db:
        from_query = """
            SELECT imdbID, title, year, language, genre
            FROM movieinfo
            WHERE imdbID > 0
            ORDER BY imdbID
        """

        cursor = mysql.cursor()
        cursor.execute(from_query)

        for r in cursor.fetchall():
            movie = db.query(Movie).filter(Movie.id==r[0]).first()
            if not movie:
                movie = Movie(
                    id=r[0],
                    name=r[1],
                    year=r[2],
                    genre=r[4]
                )
                db.add(movie)


if __name__ == '__main__':
    print('Convert Newznab to Pynab script.')
    print('Please note that this script is destructive and will wipe the following Postgre tables:')
    print('Groups, Categories, Users, TVRage, IMDB.')
    print('If you don\'t want some of these to be replaced, edit this script and comment those lines out.')
    print('Also ensure that you\'ve edited config.py to include the details of your MySQL server.')
    input('To continue, press enter. To exit, press ctrl-c.')

    mysql = mysql_connect(config.mysql)

    # comment lines out if you don't want those collections replaced
    convert_groups(mysql)
    convert_categories(mysql)
    convert_imdb(mysql)
    convert_tvrage(mysql)
    convert_users(mysql)

    print('Completed transfer. You can think about shutting down / removing MySQL from your server now.')
    print('Unless you\'re using it for something else, in which case that\'d be dumb.')