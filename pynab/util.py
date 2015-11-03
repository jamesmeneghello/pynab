import regex
import requests
from pympler import summary, muppy
import psutil

from pynab.db import db_session, Regex, Blacklist, engine
from pynab import log
import config
import db.regex as regex_data


class Match(object):
    """Holds a regex match result so we can use it in chained if statements."""

    def __init__(self):
        self.match_obj = None

    def match(self, *args, **kwds):
        self.match_obj = regex.search(*args, **kwds)
        return self.match_obj is not None


def update_blacklist():
    """Check for Blacklist update and load them into db."""
    blacklist_url = config.postprocess.get('blacklist_url')
    if blacklist_url:
        response = requests.get(blacklist_url)
        lines = response.text.splitlines()

        blacklists = []
        for line in lines:
            elements = line.split('\t\t')
            if len(elements) == 4:
                blacklists.append({
                    'group_name': elements[0],
                    'regex': elements[1],
                    'description': elements[3],
                    'status': False
                })

        engine.execute(Blacklist.__table__.insert(), blacklists)

        return True
    else:
        log.error('No blacklist update url in config.')
        return False


def update_regex():
    """Check for NN+ regex update and load them into db."""
    with db_session() as db:
        regex_type = config.postprocess.get('regex_type')
        regex_url = config.postprocess.get('regex_url')
        if regex_url:
            regexes = {}
            response = requests.get(regex_url)
            lines = response.text.splitlines()

            # get the revision or headers by itself
            first_line = lines.pop(0)

            if regex_type == 'nzedb':
                for line in lines:
                    try:
                        id, group, reg, status, desc, ordinal = tuple(line.split('\t'))
                    except ValueError:
                        # broken line
                        continue

                    regexes[int(id)] = {
                        'id': int(id),
                        'group_name': group.replace('^', '').replace('\\', '').replace('$', ''),
                        'regex': reg.replace('\\\\', '\\'),
                        'ordinal': ordinal,
                        'status': bool(status),
                        'description': desc[:255]
                    }
            else:
                revision = regex.search('\$Rev: (\d+) \$', first_line)
                if revision:
                    revision = int(revision.group(1))
                    log.info('Regex at revision: {:d}'.format(revision))

                # and parse the rest of the lines, since they're an sql dump
                for line in lines:
                    reg = regex.search('\((\d+), \'(.*)\', \'(.*)\', (\d+), (\d+), (.*), (.*)\);$', line)
                    if reg:
                        try:
                            if reg.group(6) == 'NULL':
                                description = ''
                            else:
                                description = reg.group(6).replace('\'', '')

                            regexes[int(reg.group(1))] = {
                                'id': int(reg.group(1)),
                                'group_name': reg.group(2),
                                'regex': reg.group(3).replace('\\\\', '\\'),
                                'ordinal': int(reg.group(4)),
                                'status': bool(reg.group(5)),
                                'description': description
                            }
                        except:
                            log.error('Problem importing regex dump.')
                            return False

            # if the parsing actually worked
            if len(regexes) > 0:
                db.query(Regex).filter(Regex.id<100000).delete()

                log.info('Retrieved {:d} regexes.'.format(len(regexes)))

                ids = []
                regexes = modify_regex(regexes, regex_type)
                for reg in regexes.values():
                    r = Regex(**reg)
                    ids.append(r.id)
                    db.merge(r)

                log.info('Added/modified {:d} regexes.'.format(len(regexes)))

            # add pynab regex
            for reg in regex_data.additions:
                r = Regex(**reg)
                db.merge(r)

            log.info('Added/modified {:d} Pynab regexes.'.format(len(regex_data.additions)))
            db.commit()

            return True
        else:
            log.error('No config item set for regex_url - do you own newznab plus?')
            return False


def modify_regex(regexes, type):
    reps = None
    if type == 'nzedb':
        reps = regex_data.nzedb_replacements
    else:
        reps = regex_data.nn_replacements

    for key, replacement in reps.items():
        regexes[key] = replacement

    return regexes


# both from: http://www.mobify.com/blog/sqlalchemy-memory-magic/
def get_virtual_memory_usage_kb():
    """The process's current virtual memory size in Kb, as a float."""
    return float(psutil.Process().memory_info()[1]) / 1024.0


def memory_usage(where):
    """Print out a basic summary of memory usage."""
    mem_summary = summary.summarize(muppy.get_objects())
    log.debug("Memory summary: {}".format(where))
    summary.print_(mem_summary, limit=2)
    log.debug("VM: {:2f}Mb".format(get_virtual_memory_usage_kb() / 1024.0))

def smart_truncate(content, length, suffix=''):
    return content if len(content) <= length else content[:length-len(suffix)].rsplit(' ', 1)[0] + suffix