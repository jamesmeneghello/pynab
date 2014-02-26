import datetime
import time
import hashlib
import uuid
import regex
import math

import pytz
from bson.code import Code

from pynab import log
from pynab.db import db
import config
import pynab.nzbs
import pynab.categories
import pynab.nfos
import pynab.util
import pynab.rars


def strip_req(release):
    """Strips REQ IDs out of releases and cleans them up so they can be properly matched
    in post-processing."""
    regexes = [
        regex.compile('^a\.b\.mmEFNet - REQ (?P<reqid>.+) - (?P<name>.*)', regex.I)
    ]

    for r in regexes:
        result = r.search(release['search_name'])
        if result:
            result_dict = result.groupdict()
            if 'name' in result_dict and 'reqid' in result_dict:
                log.info('Found request {}, storing req_id and renaming...'.format(result_dict['name']))
                db.releases.update({'_id': release['_id']}, {
                    '$set': {
                        'search_name': result_dict['name'],
                        'req_id': result_dict['reqid']
                    }
                })
                return


def names_from_nfos(release):
    """Attempt to grab a release name from its NFO."""
    log.debug('Parsing NFO for release details in: {}'.format(release['search_name']))
    nfo = pynab.nfos.get(release['nfo']).decode('ascii', 'ignore')
    if nfo:
        return pynab.nfos.attempt_parse(nfo)
    else:
        log.debug('NFO not available for release: {}'.format(release['search_name']))
        return []


def names_from_files(release):
    """Attempt to grab a release name from filenames inside the release."""
    log.debug('Parsing files for release details in: {}'.format(release['search_name']))
    if release['files']['names']:
        potential_names = []
        for file in release['files']['names']:
            log.debug('Checking file name: {}'.format(file))

            name = pynab.rars.attempt_parse(file)

            if name:
                potential_names.append(name)

        return potential_names
    else:
        log.debug('File list was empty for release: {}'.format(release['search_name']))
        return []


def discover_name(release):
    """Attempts to fix a release name by nfo or filelist."""
    potential_names = [release['search_name'],]

    if 'files' in release:
        potential_names += names_from_files(release)

    if release['nfo']:
        potential_names += names_from_nfos(release)

    if len(potential_names) > 1:
        old_category = release['category']['_id']
        calculated_old_category = pynab.categories.determine_category(release['search_name'])

        log.debug('Release Name: {}'.format(release['search_name']))
        log.debug('Old Category: {:d} Recalculated Old Category: {:d}'.format(old_category, calculated_old_category))

        for name in potential_names:
            new_category = pynab.categories.determine_category(name)

            # the release may already be categorised by the group it came from
            # so if we check the name and it doesn't fit a category, it's probably
            # a shitty name
            if (math.floor(calculated_old_category / 1000) * 1000) == pynab.categories.CAT_PARENT_MISC:
                # sometimes the group categorisation is better than name-based
                # so check if they're in the same parent and that parent isn't misc
                if (math.floor(new_category / 1000) * 1000) == pynab.categories.CAT_PARENT_MISC:
                    # ignore this name, since it's apparently gibberish
                    continue
                else:
                    if (math.floor(new_category / 1000) * 1000) == (math.floor(old_category / 1000) * 1000):
                        # if they're the same parent, use the new category
                        search_name = name
                        category_id = new_category

                        log.debug('Found new name for {}: {} with category {:d}'.format(release['search_name'], search_name, category_id))

                        return search_name, category_id
                    else:
                        # if they're not the same parent and they're not misc, ignore
                        continue
            else:
                # the old name was apparently fine
                return True, False

    log.debug('No potential names found for release.')
    return None, None


def clean_release_name(name):
    """Strip dirty characters out of release names. The API
    will match against clean names."""
    chars = ['#', '@', '$', '%', '^', '§', '¨', '©', 'Ö']
    for c in chars:
        name = name.replace(c, '')
    return name.replace('_', ' ')


def process():
    """Helper function to begin processing binaries. Checks
    for 100% completion and will create NZBs/releases for
    each complete release. Will also categorise releases,
    and delete old binaries."""
    log.info('Processing complete binaries and generating releases...')
    start = time.clock()

    # mapreduce isn't really supposed to be run in real-time
    # then again, processing releases isn't a real-time op
    mapper = Code("""
        function() {
            var complete = true;
            var total_segments = 0;
            var available_segments = 0;

            parts_length = Object.keys(this.parts).length;

            // we should have at least one segment from each part
            if (parts_length >= this.total_parts) {
                for (var key in this.parts) {
                    segments_length = Object.keys(this.parts[key].segments).length;
                    available_segments += segments_length;

                    total_segments += this.parts[key].total_segments;
                    if (segments_length < this.parts[key].total_segments) {
                        complete = false
                    }
                }
            } else {
                complete = false
            }
            var completion = available_segments / parseFloat(total_segments) * 100.0;
            if (complete || completion >= """ + str(config.postprocess.get('min_completion', 99)) + """)
                emit(this._id, completion)

        }
    """)

    # no reduce needed, since we're returning single values
    reducer = Code("""function(key, values){}""")

    # returns a list of _ids, so we need to get each binary
    for result in db.binaries.inline_map_reduce(mapper, reducer):
        if result['value']:
            binary = db.binaries.find_one({'_id': result['_id']})

            # check to make sure we have over the configured minimum files
            nfos = []
            rars = []
            pars = []
            rar_count = 0
            par_count = 0
            zip_count = 0

            if 'parts' in binary:
                for number, part in binary['parts'].items():
                    if regex.search(pynab.nzbs.rar_part_regex, part['subject'], regex.I):
                        rar_count += 1
                    if regex.search(pynab.nzbs.nfo_regex, part['subject'], regex.I) and not regex.search(pynab.nzbs.metadata_regex,
                                                                                                part['subject'], regex.I):
                        nfos.append(part)
                    if regex.search(pynab.nzbs.rar_regex, part['subject'], regex.I) and not regex.search(pynab.nzbs.metadata_regex,
                                                                                                part['subject'], regex.I):
                        rars.append(part)
                    if regex.search(pynab.nzbs.par2_regex, part['subject'], regex.I):
                        par_count += 1
                        if not regex.search(pynab.nzbs.par_vol_regex, part['subject'], regex.I):
                            pars.append(part)
                    if regex.search(pynab.nzbs.zip_regex, part['subject'], regex.I) and not regex.search(pynab.nzbs.metadata_regex,
                                                                                                part['subject'], regex.I):
                        zip_count += 1

                log.debug('Binary {} has {} rars and {} rar_parts.'.format(binary['name'], len(rars), rar_count))

                if rar_count + zip_count < config.postprocess.get('min_archives', 1):
                    log.debug('Binary does not have the minimum required archives.')
                    db.binaries.remove({'_id': binary['_id']})
                    continue

                # generate a gid, not useful since we're storing in GridFS
                gid = hashlib.md5(uuid.uuid1().bytes).hexdigest()

                # clean the name for searches
                clean_name = clean_release_name(binary['name'])

                # if the regex used to generate the binary gave a category, use that
                category = None
                if binary['category_id']:
                    category = db.categories.find_one({'_id': binary['category_id']})

                # otherwise, categorise it with our giant regex blob
                if not category:
                    id = pynab.categories.determine_category(binary['name'], binary['group_name'])
                    category = db.categories.find_one({'_id': id})

                # if this isn't a parent category, add those details as well
                if 'parent_id' in category:
                    category['parent'] = db.categories.find_one({'_id': category['parent_id']})

                # create the nzb, store it in GridFS and link it here
                nzb, nzb_size = pynab.nzbs.create(gid, clean_name, binary)
                if nzb:
                    log.debug('Adding release: {0}'.format(clean_name))

                    db.releases.update(
                        {
                            'search_name': binary['name'],
                            'posted': binary['posted']
                        },
                        {
                            '$setOnInsert': {
                                'id': gid,
                                'added': pytz.utc.localize(datetime.datetime.now()),
                                'size': None,
                                'spotnab_id': None,
                                'completion': None,
                                'grabs': 0,
                                'passworded': None,
                                'file_count': None,
                                'tvrage': None,
                                'tvdb': None,
                                'imdb': None,
                                'nfo': None,
                                'tv': None,
                            },
                            '$set': {
                                'name': clean_name,
                                'search_name': clean_name,
                                'total_parts': binary['total_parts'],
                                'posted': binary['posted'],
                                'posted_by': binary['posted_by'],
                                'status': 1,
                                'updated': pytz.utc.localize(datetime.datetime.now()),
                                'group': db.groups.find_one({'name': binary['group_name']}, {'name': 1}),
                                'regex': db.regexes.find_one({'_id': binary['regex_id']}),
                                'category': category,
                                'nzb': nzb,
                                'nzb_size': nzb_size
                            }
                        },
                        upsert=True
                    )

                # delete processed binaries
                db.binaries.remove({'_id': binary['_id']})

    end = time.clock()
    log.info('Time elapsed: {:.2f}s'.format(end - start))
