import sys
import json

if __name__ == '__main__':
    print('Welcome to Pynab.')
    print('-----------------')
    print()
    print('Please ensure that you have copied and renamed config.sample.py to config.py before proceeding.')
    print(
        'You need to put in your details, too. If you are migrating from Newznab, check out scripts/convert_from_newznab.py first.')
    print()
    print('This script is destructive. Ensure that the database credentials and settings are correct.')
    print('The supplied database really should be empty, but it\'ll just drop anything it wants to overwrite.')
    print()
    input('To continue, press enter. To exit, press ctrl-c.')

    try:
        import config
        from pynab.db import db
        import pynab.util
        import scripts.ensure_indexes
    except ImportError:
        print('Could not load config.py.')
        sys.exit(0)

    print('Copying users into Mongo...')
    with open('db/initial/users.json', encoding='utf-8', errors='ignore') as f:
        data = json.load(f)
        try:
            db.users.drop()
            db.users.insert(data)
        except:
            print('Problem inserting data into MongoDB.')
            sys.exit(0)

    print('Copying groups into Mongo...')
    with open('db/initial/groups.json', encoding='utf-8', errors='ignore') as f:
        data = json.load(f)
        try:
            db.groups.drop()
            db.groups.insert(data)
        except:
            print('Problem inserting data into MongoDB.')
            sys.exit(0)

    print('Copying categories into Mongo...')
    with open('db/initial/categories.json', encoding='utf-8', errors='ignore') as f:
        data = json.load(f)
        try:
            db.categories.drop()
            db.categories.insert(data)
        except:
            print('Problem inserting data into MongoDB.')
            sys.exit(0)

    print('Copying tvrage into Mongo...')
    with open('db/initial/tvrage.json', encoding='utf-8', errors='ignore') as f:
        data = json.load(f)
        try:
            db.tvrage.drop()
            db.tvrage.insert(data)
        except:
            print('Problem inserting data into MongoDB.')
            sys.exit(0)

    print('Copying imdb into Mongo...')
    with open('db/initial/imdb.json', encoding='utf-8', errors='ignore') as f:
        data = json.load(f)
        try:
            db.imdb.drop()
            db.imdb.insert(data)
        except:
            print('Problem inserting data into MongoDB.')
            sys.exit(0)

    print('Copying tvdb into Mongo...')
    with open('db/initial/tvdb.json', encoding='utf-8', errors='ignore') as f:
        data = json.load(f)
        try:
            db.tvdb.drop()
            db.tvdb.insert(data)
        except:
            print('Problem inserting data into MongoDB.')
            sys.exit(0)

    if config.site['regex_url']:
        print('Updating regex...')
        pynab.util.update_regex()
    else:
        print('Could not update regex - no update url/key in config.py.')
        print('If you don\'t have one, buy a Newznab+ license or find your own regexes.')
        print('You won\'t be able to build releases without appropriate regexes.')

    if config.site['blacklist_url']:
        print('Updating binary blacklist...')
        pynab.util.update_blacklist()
    else:
        print(
            'Could not update blacklist. Try the URL in config.py manually - if it doesn\'t work, post an issue on Github.')

    print('Creating indexes on collections...')
    scripts.ensure_indexes.create_indexes()

    print('Install theoretically completed - the rest of the collections will be made as they\'re needed.')
    print('Now: activate some groups, activate desired blacklists, and run start.py with python3.')
