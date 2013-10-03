import cymysql
import pymongo
import bson
import pprint


def mysql_connect(mysql_config):
    mysql = cymysql.connect(
        host=mysql_config['host'],
        port=mysql_config['port'],
        user=mysql_config['user'],
        passwd=mysql_config['passwd'],
        db=mysql_config['db']
    )

    return mysql


def convert_groups(mysql, mongo):
    from_query = """
        SELECT name, first_record, last_record, minfilestoformrelease, minsizetoformrelease, active
        FROM groups;
    """

    cursor = mysql.cursor()
    cursor.execute(from_query)

    if 'groups' in mongo.db().collection_names():
        mongo.db().groups.drop()

    groups = []
    for r in cursor.fetchall():
        group = {
            'name': r[0],
            'first': r[1],
            'last': r[2],
            'min_files': r[3],
            'min_size': r[4],
            'active': r[5]
        }
        groups.append(group)

    mongo.db().groups.insert(groups)



def convert_categories(mysql, mongo):
    from_query = """
        SELECT ID, title, parentID, minsizetoformrelease, maxsizetoformrelease
        FROM category;
    """
    cursor = mysql.cursor()
    cursor.execute(from_query)

    if 'categories' in mongo.db().collection_names():
        mongo.db().categories.drop()

    categories = {}
    for r in cursor.fetchall():
        category = {
            'id': r[0],
            'name': r[1],
            'min_size': r[3],
            'max_size': r[4]
        }

        if r[2]:
            parent_id = mongo.db().categories.find_one({'name': categories[r[2]]['name']})['_id']
            category.update({'parent_id': parent_id})
        else:
            categories[r[0]] = category

        mongo.db().categories.insert(category)




def convert_regex(mysql, mongo):
    from_query = """
        SELECT groupname, regex, ordinal, releaseregex.status, category.title, releaseregex.description
        FROM releaseregex
            LEFT JOIN category ON releaseregex.CategoryID = category.ID
        ORDER BY groupname;
        """
    cursor = mysql.cursor()
    cursor.execute(from_query)

    if 'regexes' in mongo.db().collection_names():
        mongo.db().regexes.drop()

    regexes = []
    for r in cursor.fetchall():
        if r[4]:
            c_id = mongo.db().categories.find_one({'name': r[4]})['_id']
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

    mongo.db().regexes.insert(regexes)




def convert_blacklist(mysql, mongo):
    from_query = """
        SELECT groupname, regex, status, description
        FROM binaryblacklist
        ORDER BY id;
        """
    cursor = mysql.cursor()
    cursor.execute(from_query)

    if 'blacklists' in mongo.db().collection_names():
        mongo.db().blacklists.drop()

    blacklists = []
    for r in cursor.fetchall():
        blacklist = {
            'group_name': r[0],
            'regex': r[1],
            'status': r[2],
            'description': r[3]
        }

        blacklists.append(blacklist)

    mongo.db().blacklists.insert(blacklists)



def convert_users(mysql, mongo):
    from_query = """
        SELECT username, email, password, rsstoken, userseed, grabs
        FROM users
        ORDER BY id;
        """
    cursor = mysql.cursor()
    cursor.execute(from_query)

    if 'users' in mongo.db().collection_names():
        mongo.db().users.drop()

    users = []
    for r in cursor.fetchall():
        user = {
            'username': r[0],
            'email': r[1],
            'password': r[2],
            'rsstoken': r[3],
            'userseed': r[4],
            'grabs': r[5]
        }

        users.append(user)

    mongo.db().users.insert(users)



def convert_tvdb(mysql, mongo):
    from_query = """
        SELECT tvdbID, seriesname
        FROM thetvdb
        WHERE tvdbID != 0 AND seriesname != ""
        ORDER BY seriesname;
        """
    cursor = mysql.cursor()
    cursor.execute(from_query)

    if 'tvdb' in mongo.db().collection_names():
        mongo.db().tvdb.drop()

    tvdbs = []
    for r in cursor.fetchall():
        tvdb = {
            'id': r[0],
            'name': r[1]
        }

        tvdbs.append(tvdb)

    mongo.db().tvdb.insert(tvdbs)



def convert_tvrage(mysql, mongo):
    from_query = """
        SELECT rageID, releasetitle
        FROM tvrage
        WHERE rageID > 0
        ORDER BY rageID
        """
    cursor = mysql.cursor()
    cursor.execute(from_query)

    if 'tvrage' in mongo.db().collection_names():
        mongo.db().tvrage.drop()

    tvrages = []
    for r in cursor.fetchall():
        tvrage = {
            'id': r[0],
            'name': r[1]
        }

        tvrages.append(tvrage)

    mongo.db().tvrage.insert(tvrages)



def convert_imdb(mysql, mongo):
    from_query = """
        SELECT imdbID, title, year, language
        FROM movieinfo
        WHERE imdbID > 0
        ORDER BY imdbID
        """
    cursor = mysql.cursor()
    cursor.execute(from_query)

    if 'imdb' in mongo.db().collection_names():
        mongo.db().imdb.drop()

    imdbs = []
    for r in cursor.fetchall():
        imdb = {
            'id': r[0],
            'name': r[1],
            'year': r[2],
            'lang': r[3]
        }

        imdbs.append(imdb)

    mongo.db().imdb.insert(imdbs)



# the biggun'
def convert_releases(mysql, mongo):
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

    if 'releases' in mongo.db().collection_names():
        mongo.db().releases.drop()

    releases = []
    for r in cursor.fetchall():
        # get the easy ones out of the way first
        release = dict(id=r[0], name=r[1], search_name=r[2], total_parts=int(r[5]), size=int(r[6]), posted=r[7], spotnab_id=r[8],
                       posted_by=r[9], completion=r[10], grabs=r[21], passworded=r[22], file_count=r[23], status=r[24],
                       add_date=r[25])

        # the tricker ones: group
        release['group_id'] = mongo.db().groups.find_one({'name': r[4]})['_id']

        # category
        release['category_id'] = mongo.db().categories.find_one({'id': r[11]})['_id']

        # rageID
        if r[12]:
            release['tvrage'] = mongo.db().tvrage.find_one({'id': r[12]})
        else:
            release['tvrage'] = None

        # tvdbID
        if r[13]:
            release['tvdb'] = mongo.db().tvdb.find_one({'id': r[13]})
        else:
            release['tvdb'] = None

        # imdbID
        if r[14]:
            release['imdb'] = mongo.db().imdb.find_one({'id': r[14]})
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

    mongo.db().releases.insert(releases)
