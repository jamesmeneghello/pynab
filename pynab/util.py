import regex

import requests

from pynab.db import db
from pynab import log
import config


class Match(object):
    """Holds a regex match result so we can use it in chained if statements."""

    def __init__(self):
        self.match_obj = None

    def match(self, *args, **kwds):
        self.match_obj = regex.search(*args, **kwds)
        return self.match_obj is not None


def update_blacklist():
    """Check for Blacklist update and load them into Mongo."""
    if 'blacklist_url' in config.site:
        log.info('Starting blacklist update...')
        response = requests.get(config.site['blacklist_url'])
        lines = response.text.splitlines()

        for line in lines:
            elements = line.split('\t\t')
            if len(elements) == 4:
                log.debug('Updating blacklist {}...'.format(elements[1]))
                db.blacklists.update(
                    {
                        'regex': elements[1]
                    },
                    {
                        '$setOnInsert': {
                            'status': 0
                        },
                        '$set': {
                            'group_name': elements[0],
                            'regex': elements[1],
                            'description': elements[3],
                        }
                    },
                    upsert=True
                )
        return True
    else:
        log.error('No blacklist update url in config.')
        return False


def update_regex():
    """Check for NN+ regex update and load them into Mongo."""
    if 'regex_url' in config.site:
        log.info('Starting regex update...')
        response = requests.get(config.site['regex_url'])
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

                    if reg.group(7) == 'NULL':
                        category_id = None
                    else:
                        category_id = int(reg.group(7))

                    regexes.append({
                        '_id': int(reg.group(1)),
                        'group_name': reg.group(2),
                        'regex': reg.group(3).replace('\\\\', '\\'),
                        'ordinal': int(reg.group(4)),
                        'status': int(reg.group(5)),
                        'description': description,
                        'category_id': category_id
                    })
                except:
                    log.error('Problem importing regex dump.')
                    return False

        # if the parsing actually worked
        if len(regexes) > 0:
            curr_total = db.regexes.count()
            change = len(regexes) - curr_total

            # this will show a negative if we add our own, but who cares for the moment
            log.info('Retrieved {:d} regexes, {:d} new.'.format(len(regexes), change))

            if change != 0:
                log.info('We either lost or gained regex, so dump them and reload.')

                db.regexes.remove({'_id': {'$lte': 100000}})
                db.regexes.insert(regexes)

                return True
            else:
                log.info('Appears to be no change, leaving alone.')
                return False
    else:
        log.error('No config item set for regex_url - do you own newznab plus?')
        return False

