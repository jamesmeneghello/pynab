import os
import sys
import time

from imp import reload
import colorama

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

from pynab.db import Part, Binary, Release, db_session
import config


def get_config_changes():
    """
    Check if config has changed and re-import.
    """
    global config_time
    if os.stat(config.__file__).st_mtime > config_time:
        reload(config)
        config_time = os.stat(config.__file__).st_mtime


def get_stats():
    """
    Retrieve relevant stats for display.
    """
    with db_session() as db:
        parts = db.query(Part).count()
        binaries = db.query(Binary).count()
        releases = db.query(Release).count()
        # backlog = db.query(Release).filter(Release.passworded=='UNKNOWN').count()
        # other-misc releases, ie. hashed, yet-to-be renamed or just bad releases
        others = db.query(Release).filter(Release.category_id==8010).count()

        return parts, binaries, releases, others


def colored(num):
    """
    Colour the numbers depending on value.
    """
    if num == 0:
        return '{}.{}'.format(colorama.Fore.GREEN, colorama.Fore.RESET)
    if num > 0:
        return '{}+{}{}'.format(colorama.Fore.GREEN, num, colorama.Fore.RESET)
    if num < 0:
        return '{}{}{}'.format(colorama.Fore.RED, num, colorama.Fore.RESET)


def build_header():
    """
    Generate a header string.
    """
    return '{:^21}|{:^21}|{:^21}|{:^21}'.format('Parts', 'Binaries', 'Releases', 'Other-Misc Releases')


if __name__ == '__main__':
    colorama.init()
    config_time = os.stat(config.__file__).st_mtime

    logging_dir = config.log.get('logging_dir')
    csv_path = os.path.join(logging_dir, 'stats.csv')

    print(build_header())

    i = 1
    first = True

    last_parts = 0
    last_binaries = 0
    last_releases = 0
    last_others = 0

    while True:
        parts, binaries, releases, others = get_stats()

        if not first:
            p_diff = parts - last_parts
            b_diff = binaries - last_binaries
            o_diff = others - last_others
            r_diff = releases - last_releases
        else:
            first = False
            p_diff = 0
            b_diff = 0
            r_diff = 0
            o_diff = 0

        if i % config.stats.get('header_every_nth', 0) == 0:
            i = 1
            print(build_header())

        print('{:^10} {:^20}|{:^10} {:^20}|{:^10} {:^20}|{:^10} {:^20}'.format(
            parts, colored(p_diff),
            binaries, colored(b_diff),
            releases, colored(r_diff),
            others, colored(o_diff)
        ))

        # write to csv file
        if config.stats.get('write_csv', True):
            # write the header if we're creating the file
            if not os.path.exists(csv_path):
                csv = open(csv_path, 'w')
                csv.write('Date,Parts,part_diff,Binaries,bin_diff,Releases,rel_diff,Other-Misc Releases,bad_diff\n')
                csv.close()

            csv = open(csv_path, 'a')
            csv.write('{},{},{},{},{},{},{},{},{}\n'.format(
                time.strftime("%Y-%m-%d %H:%M:%S"),
                parts, p_diff,
                binaries, b_diff,
                releases, r_diff,
                others, o_diff
            ))
            csv.close()

        last_parts = parts
        last_binaries = binaries
        last_releases = releases
        last_others = others
        i += 1

        time.sleep(config.stats.get('sleep_time', 300))
        get_config_changes()
