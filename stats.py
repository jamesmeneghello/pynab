import config
import random
import time
from colorama import init, Fore
init()
from pynab.db import Part, Binary, Release, db_session

def getStats():
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


if config.stats.get('write_csv', True):
    logging_dir = os.path.dirname(config.log.get('logging_file'))
    csv_path = os.path.join(logging_dir, "stats.csv")

    if os.path.exists(csv_path):
        csv = open(csv_path, 'a')
    else:
        # write header if we are creating the file
        csv = open(csv_path, 'a')
        csv.write("Parts,part_diff,Binaries,bin_diff,Releases,rel_diff")

while True:
    parts, binaries, releases = getStats()    

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
        csv.write("%d,%d,%d,%d,%d,%d\n" % (parts, p_diff, binaries, b_diff, releases, r_diff))

    last_parts    = parts
    last_binaries = binaries
    last_releases = releases
    loop_num += 1

    time.sleep(config.stats.get('sleep_time', 300))

csv.close()
