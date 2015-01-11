import config
from subprocess import Popen, call
import argparse
import sys


class PynabCLI:
    def __init__(self):
        self.monitor = config.monitor.get('type')

        parser = argparse.ArgumentParser(
            description='A Python/Postgres Usenet Indexer',
            usage='''pynab <command> [<args>]

            The most commonly used pynab commands are:
                start       Begin scanning and post-processing
                stop        Stop all running processes (scan/postproc/api)
                scan        Start scanning (only)
                postprocess Post-process releases (only)
                api         Start the API (only if not uwsgi)
                update      Update pynab
                user        Manage users
            '''
        )
        parser.add_argument('command', help='Subcommand to run')
        args = parser.parse_args(sys.argv[1:2])
        if not hasattr(self, args.command):
            print('Unrecognised command.')
            parser.print_help()
            exit(1)
        getattr(self, args.command)()

    def start(self):
        self.scan()
        self.postprocess()

    def scan(self):
        if self.monitor == 'zdaemon':
            call('zdaemon -Czdaemon/scan.conf start', shell=True)
        elif self.monitor == 'windows':
            Popen('start python scan.py -d', stdout=None, stderr=None, stdin=None, shell=True)

    def postprocess(self):
        if self.monitor == 'zdaemon':
            call('zdaemon -Czdaemon/postprocess.conf start', shell=True)
        elif self.monitor == 'windows':
            Popen('start python postprocess.py -d', stdout=None, stderr=None, stdin=None, shell=True)

    def api(self):
        if self.monitor == 'zdaemon':
            call('zdaemon -Czdaemon/api.conf start', shell=True)
        elif self.monitor == 'windows':
            Popen('start python api.py', stdout=None, stderr=None, stdin=None, shell=True)

    def stop(self):
        if self.monitor == 'zdaemon':
            call('zdaemon -Czdaemon/scan.conf stop', shell=True)
            call('zdaemon -Czdaemon/postprocess.conf stop', shell=True)
            call('zdaemon -Czdaemon/api.conf stop', shell=True)
        elif self.monitor == 'windows':
            print('can\'t stop on windows! do it yourself. if i did it, i could close things you don\'t want closed.')

    def update(self):
        call('git pull', shell=True)
        call('alembic upgrade head', shell=True)
        call('pip3 install -r requirements.txt', shell=True)
        print('Pynab updated! if there were errors, you might need to re-run `pip3 install -r requirements.txt` with sudo.')
        exit()

    def user(self):
        class PynabUserCli:
            def __init__(self):
                parser = argparse.ArgumentParser(description='Modify pynab users',
                                                 usage='''
                                                 User commands available:
                                                    create      Creates a user, given an email
                                                    delete      Deletes a user, given an email
                                                 ''')
                parser.add_argument('command', help='Subcommand to run')
                args = parser.parse_args(sys.argv[2:3])
                if not hasattr(self, args.command):
                    print('Unrecognised command.')
                    parser.print_help()
                    exit(1)
                getattr(self, args.command)()

            def create(self):
                parser = argparse.ArgumentParser(description='Create a user')
                parser.add_argument('email')
                args = parser.parse_args(sys.argv[3:])
                if args.email:
                    import pynab.users
                    key = pynab.users.create(args.email)
                    print('User created. API key is: {}'.format(key))

            def delete(self):
                parser = argparse.ArgumentParser(description='Delete a user')
                parser.add_argument('email')
                args = parser.parse_args(sys.argv[3:])
                if args.email:
                    from pynab.db import db_session, User
                    with db_session() as db:
                        deleted = db.query(User).filter(User.email==args.email).delete()
                        if deleted:
                            print('User deleted.')
                            db.commit()
                        else:
                            print('No user by that email.')

        PynabUserCli()

if __name__ == '__main__':
    if config.monitor.get('type') == 'zdaemon':
        if not config.scan.get('pid_file') or not config.postprocess.get('pid_file') or not config.log.get('logging_file'):
            print('error: a pid_file or logging_file config option is not set in config.py')
            exit(1)
    elif not config.monitor.get('type') or (config.monitor.get('type') != 'windows' and config.monitor.get('type') != 'zdaemon'):
        print('error: no monitor type set in config.py')
        exit(1)
    PynabCLI()

