#!/usr/bin/python3
"""Pynab, a Python/Postgres Usenet Indexer

Usage:
    pynab.py start|stop|scan|postprocess|api|update
    pynab.py user (create|delete) <email>
pynab.py group (enable|disable) <group>
Options:
    -h --help       Show this screen.
    --version       Show version.

"""

import config
from subprocess import Popen, call
from docopt import docopt
import os

import pynab
from pynab.db import db_session, User, Group


def scan():
    if monitor == 'zdaemon':
        call('zdaemon -Czdaemon/scan.conf start', shell=True)
    elif monitor == 'windows':
        Popen('start "Pynab Scan (close to quit)" python scan.py', stdout=None, stderr=None, stdin=None, shell=True)


def postprocess():
    if monitor == 'zdaemon':
        call('zdaemon -Czdaemon/postprocess.conf start', shell=True)
    elif monitor == 'windows':
        Popen('start "Pynab Post-Process (close to quit)" python postprocess.py', stdout=None, stderr=None, stdin=None, shell=True)


def api():
    if monitor == 'zdaemon':
        call('zdaemon -Czdaemon/api.conf start', shell=True)
    elif monitor == 'windows':
        Popen('start "Pynab API (close to quit)" python api.py', stdout=None, stderr=None, stdin=None, shell=True)


def stop():
    if monitor == 'zdaemon':
        call('zdaemon -Czdaemon/scan.conf stop', shell=True)
        call('zdaemon -Czdaemon/postprocess.conf stop', shell=True)
        call('zdaemon -Czdaemon/api.conf stop', shell=True)
    elif monitor == 'windows':
        print('can\'t stop on windows! do it yourself. if i did it, i could close things you don\'t want closed.')


def update():
    call('git pull', shell=True)
    call('alembic upgrade head', shell=True)
    call('pip3 install -q -r requirements.txt', shell=True)
    print('Pynab updated! if there were errors, you might need to re-run `pip3 install -r requirements.txt` with sudo.')
    exit()


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


if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    monitor = config.monitor.get('type', None)

    if monitor and not (monitor == 'windows' or monitor == 'zdaemon'):
        print('error: no monitor type set in config.py')
        exit(1)
    elif monitor == 'windows' and config.log.get('logging_file'):
        print('To view console output in command windows, turn off the logging file!')
    elif not monitor:
        print('error: missing monitor in config.py')
        exit(1)
    else:
        if not config.scan.get('pid_file') or not config.postprocess.get('pid_file') or not config.log.get('logging_file'):
            print('error: a pid_file or logging_file config option is not set in config.py')
            exit(1)

    arguments = docopt(__doc__, version=pynab.__version__)

    if arguments['start']:
        scan()
        postprocess()
        if monitor == 'windows':
            api()
    elif arguments['stop']:
        stop()
    elif arguments['scan']:
        scan()
    elif arguments['postprocess']:
        postprocess()
    elif arguments['api']:
        api()
    elif arguments['update']:
        update()
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
    
    exit(0)
