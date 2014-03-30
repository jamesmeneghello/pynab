import sys
import os
import json

if __name__ == '__main__':
    print('Welcome to Pynab.')
    print('-----------------')
    print()
    print('Please ensure that you have copied and renamed config.sample.py to config.py before proceeding.')
    print('You need to put in your details, too. If you are migrating from Newznab, check out scripts/convert_from_newznab.py first.')
    print()
    print('This script is destructive. Ensure that the database credentials and settings are correct.')
    print('The supplied database really should be empty, but it\'ll just drop anything it wants to overwrite.')
    print()
    input('To continue, press enter. To exit, press ctrl-c.')

    sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

    import config
    from pynab.db import Base, engine, Session, User, Group, Category, TvShow, Movie
    import pynab.util

    db = Session()

    print('Building tables...')
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    print('Installing admin user...')
    with open('db/initial/users.json', encoding='utf-8', errors='ignore') as f:
        data = json.load(f)
        try:
            engine.execute(User.__table__.insert(), data)
        except Exception as e:
            print('Problem inserting data into database: {}'.format(e))
            sys.exit(0)

    print('Copying groups into db...')
    with open('db/initial/groups.json', encoding='utf-8', errors='ignore') as f:
        data = json.load(f)
        try:
            engine.execute(Group.__table__.insert(), data)
        except Exception as e:
            print('Problem inserting data into database: {}'.format(e))
            sys.exit(0)

    print('Copying categories into db...')
    with open('db/initial/categories.json', encoding='utf-8', errors='ignore') as f:
        data = json.load(f)
        try:
            engine.execute(Category.__table__.insert(), data)
        except Exception as e:
            print('Problem inserting data into database: {}'.format(e))
            sys.exit(0)

    """
    print('Copying TV data into db...')
    with open('db/initial/tvshows.json', encoding='utf-8', errors='ignore') as f:
        data = json.load(f)
        try:
            engine.execute(TvShow.__table__.insert(), data)
        except Exception as e:
            print('Problem inserting data into database: {}'.format(e))
            sys.exit(0)

    print('Copying movie data into db...')
    with open('db/initial/movies.json', encoding='utf-8', errors='ignore') as f:
        data = json.load(f)
        try:
            engine.execute(Movie.__table__.insert(), data)
        except Exception as e:
            print('Problem inserting data into database: {}'.format(e))
            sys.exit(0)
    """

    if config.postprocess.get('regex_url'):
        print('Updating regex...')
        pynab.util.update_regex()
    else:
        print('Could not update regex - no update url/key in config.py.')
        print('If you don\'t have one, buy a Newznab+ license or find your own regexes.')
        print('You won\'t be able to build releases without appropriate regexes.')

    if config.postprocess.get('blacklist_url'):
        print('Updating binary blacklist...')
        pynab.util.update_blacklist()
    else:
        print(
            'Could not update blacklist. Try the URL in config.py manually - if it doesn\'t work, post an issue on Github.')

    print('Install complete.')
    print('Now: activate some groups, activate desired blacklists, and run start.py with python3.')
