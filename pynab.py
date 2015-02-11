#!/usr/bin/python3
"""Pynab, a Python/Postgres Usenet Indexer

Usage:
    pynab.py start|stop|scan|postprocess|api|update|backfill|pubsub|regex|prebot|checkconfig|stats
    pynab.py user (create|delete) <email>
    pynab.py group (enable|disable|reset) <group>

Options:
    -h --help       Show this screen.
    --version       Show version.

"""

import config
from subprocess import Popen, call
from docopt import docopt
import os

import pynab.util
from pynab.db import db_session, User, Group


def scan():
    if monitor == 'supervisor':
        call('supervisorctl start pynab-scan', shell=True)
    elif monitor == 'windows':
        Popen('start "Pynab Update (close to quit)" python scan.py', stdout=None, stderr=None, stdin=None, shell=True)


def backfill():
    if monitor == 'supervisor':
        call('supervisorctl start pynab-backfill', shell=True)
    elif monitor == 'windows':
        program = 'start "Pynab Backfill (close to quit)" python scan.py backfill'
        Popen(program, stdout=None, stderr=None, stdin=None, shell=True)


def postprocess():
    if monitor == 'supervisor':
        call('supervisorctl start pynab-postproc', shell=True)
    elif monitor == 'windows':
        Popen('start "Pynab Post-Process (close to quit)" python postprocess.py', stdout=None, stderr=None, stdin=None, shell=True)


def api():
    if monitor == 'supervisor':
        call('supervisorctl start pynab-api', shell=True)
    elif monitor == 'windows':
        Popen('start "Pynab API (close to quit)" python api.py', stdout=None, stderr=None, stdin=None, shell=True)


def pubsub():
    if monitor == 'supervisor':
        call('supervisorctl start pynab-pubsub', shell=True)
    elif monitor == 'windows':
        Popen('start "Pynab PubSub (close to quit)" python pubsub.py start', stdout=None, stderr=None, stdin=None, shell=True)


def prebot():
    if monitor == 'supervisor':
        call('supervisorctl start pynab-prebot', shell=True)
    elif monitor == 'windows':
        Popen('start "Pynab prebot (close to quit)" python prebot.py start', stdout=None, stderr=None, stdin=None, shell=True)


def stats():
    if monitor == 'supervisor':
        call('supervisorctl start pynab-stats', shell=True)
    elif monitor == 'windows':
        Popen('start "Pynab stats (close to quit)" python scripts/stats.py start', stdout=None, stderr=None, stdin=None, shell=True)


def stop():
    if monitor == 'supervisor':
        call('supervisorctl stop pynab-all', shell=True)
    elif monitor == 'windows':
        print('can\'t stop on windows! do it yourself. if i did it, i could close things you don\'t want closed.')


def update():
    call('git pull', shell=True)
    call('alembic upgrade head', shell=True)
    call('pip3 install -q -r requirements.txt', shell=True)
    print('Pynab updated! if there were errors, you might need to re-run `pip3 install -r requirements.txt` with sudo.')


def create_user(email):
    import pynab.users
    key = pynab.users.create(email)
    print('user created. key: {}'.format(key))


def delete_user(email):
    with db_session() as db:
        deleted = db.query(User).filter(User.email==email).delete()
        if deleted:
            db.commit()
            print('user deleted.')
        else:
            print('user not found.')


def enable_group(group):
    with db_session() as db:
        group = db.query(Group).filter(Group.name==group).first()
        if group:
            group.active = True
            db.add(group)
            db.commit()
            print('group enabled.')
        else:
            print('group does not exist.')


def disable_group(group):
    with db_session() as db:
        group = db.query(Group).filter(Group.name==group).first()
        if group:
            group.active = False
            db.add(group)
            db.commit()
            print('group disabled.')
        else:
            print('group does not exist.')


def reset_group(group):
    with db_session() as db:
        group = db.query(Group).filter(Group.name==group).first()
        if group:
            group.first = 0
            group.last = 0
            db.add(group)
            db.commit()
            print('group first/last reset.')
        else:
            print('group does not exist.')


def checkconfig():
    from pynab import check_config
    check_config()
    print('Config appears ok!')


def update_regex():
    pynab.util.update_regex()


if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    monitor = config.monitor.get('type', None)

    if monitor and not (monitor == 'windows' or monitor == 'zdaemon'):
        print('error: no monitor type set in config.py')
        exit(1)
    elif monitor == 'windows' and config.log.get('logging_file'):
        print('To view console output in command windows, turn off the logging file!')

    arguments = docopt(__doc__, version=pynab.__version__)

    if arguments['start']:
        scan()
        postprocess()
        prebot()
        if monitor == 'windows':
            api()
        if config.bot.get('enabled', False):
            pubsub()
        stats()
    elif arguments['stop']:
        stop()
    elif arguments['scan']:
        scan()
    elif arguments['backfill']:
        backfill()
    elif arguments['postprocess']:
        postprocess()
    elif arguments['api']:
        api()
    elif arguments['pubsub']:
        pubsub()
    elif arguments['prebot']:
        prebot()
    elif arguments['stats']:
        stats()
    elif arguments['update']:
        update()
        checkconfig()
    elif arguments['user']:
        if arguments['create']:
            create_user(arguments['<email>'])
        elif arguments['delete']:
            delete_user(arguments['<email>'])
    elif arguments['group']:
        if arguments['enable']:
            enable_group(arguments['<group>'])
        elif arguments['disable']:
            disable_group(arguments['<group>'])
        elif arguments['reset']:
            reset_group(arguments['<group>'])
    elif arguments['regex']:
        update_regex()
    elif arguments['checkconfig']:
        checkconfig()
    
    exit(0)
