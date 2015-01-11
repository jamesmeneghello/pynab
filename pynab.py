import config
from subprocess import Popen, call
import sys
import argparse

if __name__ == '__main__':
    argparser = argparse.ArgumentParser(description="Pynab main scanning script")
    argparser.add_argument('-u', '--update', action='store_true', help='update pynab')
    args = argparser.parse_args()

    if args.update:
        call('git pull', shell=True)
        call('alembic upgrade head', shell=True)
        call('pip3 install -r requirements.txt', shell=True)
        print('pynab updated! if there were errors, you might need to re-run `pip3 install -r requirements.txt` with sudo.')
        sys.exit()
    else:
        if config.monitor.get('type') == 'teamocil':
            if not config.scan.get('pid_file') or not config.postprocess.get('pid_file') or not config.log.get('logging_file'):
                print('error: a pid_file or logging_file config option is not set in config.py')
                sys.exit()
            Popen('python3 start.py -d', stdout=None, stderr=None, stdin=None, shell=True)
            Popen('python3 postprocess.py -d', stdout=None, stderr=None, stdin=None, shell=True)
            print('teamocil started')
        elif config.monitor.get('type') == 'screen':
            Popen('screen -d -m -S start python3 start.py', stdout=None, stderr=None, stdin=None, shell=True)
            Popen('screen -d -m -S postprocess python3 postprocess.py', stdout=None, stderr=None, stdin=None, shell=True)
            print('Pynab started. If you\'re not using file logging, you can access the shells with screen -r start or screen -r postprocess.')
            sys.exit()
        elif config.monitor.get('type') == 'windows':
            Popen('start python scan.py -d', stdout=None, stderr=None, stdin=None, shell=True)
            Popen('start python postprocess.py -d', stdout=None, stderr=None, stdin=None, shell=True)
            Popen('start python api.py', stdout=None, stderr=None, stdin=None, shell=True)
            print('Pynab started. You can use process manager to kill spawned processes (called python.exe).')
            print('Make sure that your PATH has python set to a python3 directory.')
            sys.exit()
        else:
            print('error: no monitor type set in config.py')

