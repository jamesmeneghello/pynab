import regex
import requests

from pynab.db import db_session, Regex, Blacklist, engine
from pynab import log
import config
import db.regex


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
        regex_url = config.postprocess.get('regex_url')
        if regex_url:
            response = requests.get(regex_url)
            lines = response.text.splitlines()

            # get the revision by itself
            first_line = lines.pop(0)
            revision = regex.search('\$Rev: (\d+) \$', first_line)
            if revision:
                revision = int(revision.group(1))
                log.info('Regex at revision: {:d}'.format(revision))

            # and parse the rest of the lines, since they're an sql dump
            regexes = []
            for line in lines:
                reg = regex.search('\((\d+), \'(.*)\', \'(.*)\', (\d+), (\d+), (.*), (.*)\);$', line)
                if reg:
                    try:
                        if reg.group(6) == 'NULL':
                            description = ''
                        else:
                            description = reg.group(6).replace('\'', '')

                        regexes.append({
                            'id': int(reg.group(1)),
                            'group_name': reg.group(2),
                            'regex': reg.group(3).replace('\\\\', '\\'),
                            'ordinal': int(reg.group(4)),
                            'status': bool(reg.group(5)),
                            'description': description
                        })
                    except:
                        log.error('Problem importing regex dump.')
                        return False

            # if the parsing actually worked
            if len(regexes) > 0:
                curr_total = db.query(Regex).count()
                change = len(regexes) - curr_total

                # this will show a negative if we add our own, but who cares for the moment
                log.info('Retrieved {:d} regexes, {:d} new.'.format(len(regexes), change))

                ids = []
                regexes = modify_regex(regexes)
                for reg in regexes:
                    r = Regex(**reg)
                    ids.append(r.id)
                    db.merge(r)

                removed = db.query(Regex).filter(~Regex.id.in_(ids)).filter(Regex.id <= 100000).update({Regex.status: False}, synchronize_session='fetch')

                db.commit()

                log.info('Disabled {:d} removed regexes.'.format(removed))

                return True
        else:
            log.error('No config item set for regex_url - do you own newznab plus?')
            return False


def modify_regex(regexes):
    for key, replacement in db.regex.replacements.items():
        regexes[key] = replacement

    return regexes


