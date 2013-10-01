import cymysql
import pymongo
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
    mongo.db().groups.ensure_index('name', pymongo.ASCENDING)


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

    mongo.db().categories.create_index('name', pymongo.ASCENDING)
    mongo.db().categories.create_index('parent_id', pymongo.ASCENDING)


def convert_regex(mysql, mongo):
    from_query = """
        SELECT groupname, regex, ordinal, releaseregex.status, category.title
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
            'category_id': c_id
        }

        regexes.append(regex)

    mongo.db().regexes.insert(regexes)

    mongo.db().regexes.create_index('group_name', pymongo.ASCENDING)
    mongo.db().regexes.create_index('category_id', pymongo.ASCENDING)
