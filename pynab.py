import config
from subprocess import Popen, call
import argparse
import sys

try:
    import zdaemon.zdctl
except ImportError:
    print('missing zdaemon, run update.')
    exit(1)

class PynabCLI:
    def __init__(self):
        self.monitor = config.monitor.get('type')

        parser = argparse.ArgumentParser(
            description='A Python/Postgres Usenet Indexer',
            usage='''pynab <command> [<args>]

            The most commonly used pynab commands are:
                start       Begin scanning and post-processing
                stop        Stop any running processes
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
            Popen('zdaemon -Czdaemon/scan.conf start')
        elif self.monitor == 'windows':
            Popen('start python scan.py -d', stdout=None, stderr=None, stdin=None, shell=True)

    def postprocess(self):
        if self.monitor == 'zdaemon':
            pass
        elif self.monitor == 'windows':
            Popen('start python postprocess.py -d', stdout=None, stderr=None, stdin=None, shell=True)

    def api(self):
        if self.monitor == 'zdaemon':
            pass
        elif self.monitor == 'windows':
            Popen('start python api.py', stdout=None, stderr=None, stdin=None, shell=True)

    def update(self):
        call('git pull', shell=True)
        call('alembic upgrade head', shell=True)
        call('pip3 install -r requirements.txt', shell=True)
        print('Pynab updated! if there were errors, you might need to re-run `pip3 install -r requirements.txt` with sudo.')
        exit()

if __name__ == '__main__':
    if config.monitor.get('type') == 'zdaemon':
        if not config.scan.get('pid_file') or not config.postprocess.get('pid_file') or not config.log.get('logging_file'):
            print('error: a pid_file or logging_file config option is not set in config.py')
            exit(1)
    elif not config.monitor.get('type'):
        print('error: no monitor type set in config.py')
        exit(1)
    PynabCLI()

