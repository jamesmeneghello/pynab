"""
Functions to convert a Newznab installation to Pynab.

NOTE: DESTRUCTIVE. DO NOT RUN ON ACTIVE PYNAB INSTALL.
(unless you know what you're doing)

"""

import argparse
import os
import sys

try:
    import cymysql
except:
    print("cymysql is required for conversion: pip install cymysql")
    exit(-1)


sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

from pynab.db import db_session, Group, Category, Release, User, TvShow, Movie
import config

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

    parser = argparse.ArgumentParser()

    parser.add_argument("mysql_host",
                        help="Newznab MySQL Hostname")
    parser.add_argument("mysql_db",
                        help="Newznab MySQL Database Name")

    parser.add_argument("--mysql-user", dest="mysql_user",
                        help="Newznab MySQL Username")
    parser.add_argument("--mysql-passwd", dest="mysql_passwd",
                        help="Newznab MySQL Password")
    parser.add_argument("--mysql-port", default=3306, type=int,
                        dest="mysql_port",
                        help="Newznab MySQL Port (default: 3306)")

    parser.add_argument("--no-users", action="store_true", dest="no_users",
                        help="Turn off users conversion.")
    parser.add_argument("--no-groups", action="store_true", dest="no_groups",
                        help="Turn off groups conversion.")
    parser.add_argument("--no-categories", action="store_true",
                        dest="no_categories",
                        help="Turn off categories conversion.")
    parser.add_argument("--no-imdb", action="store_true", dest="no_imdb",
                        help="Turn off IMDB conversion.")
    parser.add_argument("--no-tvrage", action="store_true", dest="no_tvrage",
                        help="Turn off TVRage conversion.")

    args = parser.parse_args()

    print('Convert Newznab to Pynab script.')
    print('Please note that this script is destructive.')
    print('The following Postgres tables will be wiped:')
    print('\tGroups\n\tCategories\n\tUsers\n\tTVRage\n\tIMDB.')
    print('If you don\'t want some of these to be replaced, use the --no-<table> option.')
    print('See --help for more information.')
    print('')
    input('To continue, press enter. To exit, press ctrl-c.')

    mysql = cymysql.connect(host=args.mysql_host,
                            port=args.mysql_port,
                            user=args.mysql_user,
                            passwd=args.mysql_passwd,
                            db=args.mysql_db)

    if not args.no_users:
        convert_users(mysql)
    if not args.no_groups:
        convert_groups(mysql)
    if not args.no_categories:
        convert_categories(mysql)
    if not args.no_imdb:
        convert_imdb(mysql)
    if not args.no_tvrage:
        convert_tvrage(mysql)

    print('Completed transfer.')
