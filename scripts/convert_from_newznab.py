"""
Functions to convert a Newznab installation to Pynab.

NOTE: DESTRUCTIVE. DO NOT RUN ON ACTIVE PYNAB INSTALL.
(unless you know what you're doing)

Note 2:
If there are duplicate rageID/tvdbID/imdbID's in their
respective tables, you'll need to trim duplicates first
or these scripts will fail. You can do so with:

alter ignore table tvrage add unique key (rageid);

If they're running InnoDB you can't always do this, so
you'll need to do:

alter table tvrage engine myisam;
alter ignore table tvrage add unique key (rageid);
alter table tvrage engine innodb;

"""

# if you're using pycharm, don't install the bson package
# it comes with pymongo
import cymysql
import bson
from pynab.db import db


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
    cursor = mysql.cursor()
    cursor.execute(from_query)

    if 'users' in db.collection_names():
        db.users.drop()

    users = []
    for r in cursor.fetchall():
        user = {
            'username': r[0],
            'email': r[1],
            'password': r[2],
            'api_key': r[3],
            'seed': r[4],
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

    db.tvdb.insert(tvdbs)


def convert_tvrage(mysql):
    """Converts Newznab tvrage table into Pynab format."""
    from_query = """
        SELECT rageID, releasetitle
        FROM tvrage
        WHERE rageID > 0
        ORDER BY rageID
        """
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

    db.tvrage.insert(tvrages)


def convert_imdb(mysql):
    """Converts Newznab imdb table into Pynab format."""
    from_query = """
        SELECT imdbID, title, year, language
        FROM movieinfo
        WHERE imdbID > 0
        ORDER BY imdbID
        """
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
            'lang': r[3]
        }

        imdbs.append(imdb)

    db.imdb.insert(imdbs)


# the biggun'
def convert_releases(mysql):
    """Converts Newznab releases table into Pynab format.
    Probably a bad idea - import the NZBs instead."""
    from_query = """
        SELECT releases.gid, releases.name, releases.searchname,
            releases.groupID, groups.name,
            releases.totalpart, releases.size, releases.postdate, releases.guid,
            releases.fromname, releases.completion,
            releases.categoryID,
            releases.rageID,
            releases.tvdbID,
            releases.imdbID,
            releasenfo.nfo,
            releases.seriesfull, releases.season, releases.episode, releases.tvtitle, releases.tvairdate,
            releases.grabs, releases.passwordstatus, releases.rarinnerfilecount, releases.relstatus,
            releases.adddate
        FROM releases
            LEFT JOIN groups ON groups.id = releases.groupID
            LEFT JOIN category ON category.id = releases.categoryID
            LEFT JOIN releaseregex ON releaseregex.id = releases.regexID
            LEFT JOIN releasenfo ON releasenfo.id = releases.releasenfoID
        ORDER BY releases.id
        """
    cursor = mysql.cursor()
    cursor.execute(from_query)

    if 'releases' in db.collection_names():
        db.releases.drop()

    releases = []
    for r in cursor.fetchall():
        # get the easy ones out of the way first
        release = dict(id=r[0], name=r[1], search_name=r[2], total_parts=int(r[5]), size=int(r[6]), posted=r[7],
                       spotnab_id=r[8],
                       posted_by=r[9], completion=r[10], grabs=r[21], passworded=r[22], file_count=r[23], status=r[24],
                       add_date=r[25])

        # the tricker ones: group
        release['group_id'] = db.groups.find_one({'name': r[4]})['_id']

        # category
        release['category_id'] = r[11]

        # rageID
        if r[12]:
            release['tvrage'] = db.tvrage.find_one({'_id': r[12]})
        else:
            release['tvrage'] = None

        # tvdbID
        if r[13]:
            release['tvdb'] = db.tvdb.find_one({'_id': r[13]})
        else:
            release['tvdb'] = None

        # imdbID
        if r[14]:
            release['imdb'] = db.imdb.find_one({'_id': r[14]})
        else:
            release['imdb'] = None

        # releaseNFO - store nfo as binary
        if r[15]:
            release['nfo'] = bson.Binary(r[15])
        else:
            release['nfo'] = None

        # store tv data
        if r[16]:
            tv = {
                'series_full': r[16],
                'season': r[17],
                'episode': r[18],
                'title': r[19],
                'air_date': r[20]
            }

            release['tv'] = tv
        else:
            release['tv'] = None

        releases.append(release)

    db.releases.insert(releases)
