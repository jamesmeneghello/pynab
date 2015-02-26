#!/usr/bin/python3
"""Pynab, a Python/Postgres Usenet Indexer

Usage:
    pynab.py start|stop|scan|postprocess|api|update|backfill|pubsub|regex|prebot|checkconfig|stats
    pynab.py user list
    pynab.py user (create|delete|info) <email>
    pynab.py group list
    pynab.py group (enable|disable|reset|info|add|remove) <group>

Options:
    -h --help       Show this screen.
    --version       Show version.

"""

from subprocess import Popen, call
import os

from docopt import docopt

import config
import pynab.util

def scan():
    if monitor == 'supervisor':
        call('supervisorctl start pynab:scan', shell=True)
    elif monitor == 'windows':
        Popen('start "Pynab Update (close to quit)" python scan.py', stdout=None, stderr=None, stdin=None, shell=True)


def backfill():
    if monitor == 'supervisor':
        call('supervisorctl start pynab:backfill', shell=True)
    elif monitor == 'windows':
        program = 'start "Pynab Backfill (close to quit)" python scan.py backfill'
        Popen(program, stdout=None, stderr=None, stdin=None, shell=True)


def postprocess():
    if monitor == 'supervisor':
        call('supervisorctl start pynab:postproc', shell=True)
    elif monitor == 'windows':
        Popen('start "Pynab Post-Process (close to quit)" python postprocess.py', stdout=None, stderr=None, stdin=None,
              shell=True)


def api():
    if monitor == 'supervisor':
        call('supervisorctl start pynab:api', shell=True)
    elif monitor == 'windows':
        Popen('start "Pynab API (close to quit)" python api.py', stdout=None, stderr=None, stdin=None, shell=True)


def pubsub():
    if monitor == 'supervisor':
        call('supervisorctl start pynab:pubsub', shell=True)
    elif monitor == 'windows':
        Popen('start "Pynab PubSub (close to quit)" python pubsub.py start', stdout=None, stderr=None, stdin=None,
              shell=True)


def prebot():
    if monitor == 'supervisor':
        call('supervisorctl start pynab:prebot', shell=True)
    elif monitor == 'windows':
        Popen('start "Pynab prebot (close to quit)" python prebot.py start', stdout=None, stderr=None, stdin=None,
              shell=True)


def stats():
    if monitor == 'supervisor':
        call('supervisorctl start pynab:stats', shell=True)
    elif monitor == 'windows':
        Popen('start "Pynab stats (close to quit)" python scripts/stats.py start', stdout=None, stderr=None, stdin=None,
              shell=True)


def stop():
    if monitor == 'supervisor':
        call('supervisorctl stop pynab:*', shell=True)
    elif monitor == 'windows':
        print('can\'t stop on windows! do it yourself. if i did it, i could close things you don\'t want closed.')


def update():
    call('git pull', shell=True)
    call('alembic upgrade head', shell=True)
    call('pip3 install -q -r requirements.txt', shell=True)
    print('Pynab updated! if there were errors, you might need to re-run `pip3 install -r requirements.txt` with sudo.')

def list_users():
    import pynab.users
    user_list = pynab.users.list()
    if user_list:
        for user in user_list:
            print("Email: %s\tAPI Key: %s\tGrabs: %s" % (user[0],
                                                         user[1],
                                                         user[2]))
    else:
        print('No users found.')

def create_user(email):
    import pynab.users

    key = pynab.users.create(email)
    print('user created. key: {}'.format(key))


def delete_user(email):
    import pynab.users
    ret = pynab.users.delete(email)
    if ret:
        print('User deleted.')
    else:
        print('User not found.')

def info_user(email):
    import pynab.users
    user = pynab.users.info(email)
    if user:
        print("Email: %s\tAPI Key: %s\tGrabs: %s" % (user[0],
                                                     user[1],
                                                     user[2]))
    else:
        print('User not found.')

def add_group(group):
    import pynab.groupctl
    if pynab.groupctl.add_group(group):
        print('group added and activated.')
    else:
        print('group not added.')

def remove_group(group):
    import pynab.groupctl
    if pynab.groupctl.remove_group(group):
        print('group removed.')
    else:
        print('group does not exist.')

def enable_group(group):
    import pynab.groupctl
    if pynab.groupctl.enable_group(group):
        print('group enabled.')
    else:
        print('group does not exist.')


def disable_group(group):
    import pynab.groupctl
    if pynab.groupctl.disable_group(group):
        print('group disabled.')
    else:
        print('group does not exist.')

def reset_group(group):
    import pynab.groupctl
    if pynab.groupctl.disable_group(group):
        print('group first/last reset.')
    else:
        print('group does not exist.')

def group_info(group):
    import pynab.groupctl
    group = pynab.groupctl.group_info(group)
    if group:
        print("%s\t%s\t%s\t%s" % (group.name,
                                  group.active,
                                  group.first,
                                  group.last))
    else:
        print('group does not exist.')

def group_list():
    import pynab.groupctl
    groups = pynab.groupctl.group_list()
    if groups:
        for group in groups:
            print("%s\t%s\t%s\t%s" % (group.name,
                                      group.active,
                                      group.first,
                                      group.last))
    else:
        print('no groups configured.')

def checkconfig():
    from pynab import check_config

    check_config()
    print('Config appears ok!')


def update_regex():
    pynab.util.update_regex()


if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    monitor = config.monitor.get('type', None)

    if monitor and not (monitor == 'windows' or monitor == 'supervisor'):
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
        elif arguments['info']:
            info_user(arguments['<email>'])
        elif arguments['list']:
            list_users()
    elif arguments['group']:
        if arguments['enable']:
            enable_group(arguments['<group>'])
        elif arguments['disable']:
            disable_group(arguments['<group>'])
        elif arguments['reset']:
            reset_group(arguments['<group>'])
        elif arguments['info']:
            group_info(arguments['<group>'])
        elif arguments['list']:
            group_list()
        elif arguments['add']:
            add_group(arguments['<group>'])
        elif arguments['remove']:
            remove_group(arguments['<group>'])
    elif arguments['regex']:
        update_regex()
    elif arguments['checkconfig']:
        checkconfig()

    exit(0)
