import config
import random
import os, sys, time
from colorama import init, Fore
init()
from pynab.db import Part, Binary, Release, db_session
from imp import reload

config_time = os.stat(config.__file__).st_mtime

def get_config_changes():
    global config_time

    if os.stat(config.__file__).st_mtime > config_time:
        reload(config)
        config_time = os.stat(config.__file__).st_mtime


def get_stats():
    with db_session() as db:
        # parts
        parts = db.query(Part).count()

        # binaries
        binaries = db.query(Binary).count()

        # backlog = db.query(Release).filter(Release.passworded=='UNKNOWN').count()

        # processed releases
        releases = db.query(Release).count()

        return parts, binaries, releases

#
# Give the numbers some color
#
def colored(num):
    if num == 0:
        return Fore.GREEN + " " + Fore.RESET
    if num > 0:
        return Fore.GREEN + "+" + str(num) + Fore.RESET
    if num < 0:
        return Fore.RED + str(num) + Fore.RESET

def printHeader():
    print ("%-21s|%-21s|%s" % (" Parts", " Binaries", " Releases"))


last_parts = 0
last_binaries = 0
last_releases = 0
first_loop = True
loop_num = 1

printHeader()


logging_dir = os.path.dirname(config.log.get('logging_file'))
csv_path = os.path.join(logging_dir, "stats.csv")

# write header if we are creating the file
if config.stats.get('write_csv', True):
    if not os.path.exists(csv_path):
        csv = open(csv_path, 'a')
        csv.write("Date,Parts,part_diff,Binaries,bin_diff,Releases,rel_diff\n")
        csv.close()

while True:
    parts, binaries, releases = get_stats()    

    if not first_loop:
        p_diff = parts - last_parts 
        b_diff = binaries - last_binaries
        r_diff = releases - last_releases
    else:
        first_loop = False
        p_diff = 0
        b_diff = 0
        r_diff = 0

    if loop_num % config.stats.get('header_every_nth', 0) == 0:
        printHeader()

    print ("%10d %20s|%10d %20s|%10d %6s" % (parts, colored(p_diff), binaries, colored(b_diff), releases, colored(r_diff)))

    # write to csv file
    if config.stats.get('write_csv', True):
        csv = open(csv_path, 'a')
        csv.write("%s,%d,%d,%d,%d,%d,%d\n" % (time.strftime("%Y-%m-%d %H:%M:%S"),parts, p_diff, binaries, b_diff, releases, r_diff))
        csv.close()

    last_parts    = parts
    last_binaries = binaries
    last_releases = releases
    loop_num += 1

    time.sleep(config.stats.get('sleep_time', 300))
    get_config_changes()
