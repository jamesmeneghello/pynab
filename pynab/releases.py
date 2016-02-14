import time
import math
import base64

import regex
from requests_futures.sessions import FuturesSession
from sqlalchemy.orm import *

from pynab import log
from pynab.db import to_json, db_session, engine, Binary, Part, Release, Group, Category, Blacklist, _create_hash
import pynab.categories
import pynab.nzbs
import pynab.rars
import pynab.nfos
import pynab.sfvs
import pynab.requests
import config


def names_from_nfos(release):
    """Attempt to grab a release name from its NFO."""
    nfo = pynab.nfos.get(release.nfo).decode('ascii', 'ignore')
    if nfo:
        return pynab.nfos.attempt_parse(nfo)
    else:
        return []


def names_from_files(release):
    """Attempt to grab a release name from filenames inside the release."""
    potential_names = []
    for file in release.files:
        name = pynab.rars.attempt_parse(file.name)
        if name:
            potential_names.append(name)
    return potential_names


def names_from_sfvs(release):
    """Attempt to grab a release name from supplied SFV (if it exists)."""
    sfv = pynab.sfvs.get(release.sfv).decode('ascii', 'ignore')
    if sfv:
        return pynab.sfvs.attempt_parse(sfv)
    else:
        return []


def discover_name(release):
    """Attempts to fix a release name by nfo, filelist or sfv."""
    potential_names = [release.search_name, ]

    # base64-decode the name in case it's that
    try:
        n = release.name
        missing_padding = 4 - len(release.name) % 4
        if missing_padding:
            n += '=' * missing_padding
        n = base64.b64decode(n.encode('utf-8'))
        potential_names.append(n.decode('utf-8'))
    except:
        pass

    # add a reversed name, too
    potential_names.append(release.name[::-1])

    if release.files:
        potential_names += names_from_files(release)

    if release.nfo:
        potential_names += names_from_nfos(release)

    if release.sfv:
        potential_names += names_from_sfvs(release)

    if release.pre:
        potential_names.append(release.pre.name)

    if len(potential_names) > 1:
        old_category = release.category_id
        calculated_old_category = pynab.categories.determine_category(release.search_name)

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
                    if (math.floor(new_category / 1000) * 1000) == (math.floor(old_category / 1000) * 1000) \
                            or (math.floor(old_category / 1000) * 1000) == pynab.categories.CAT_PARENT_MISC:
                        # if they're the same parent, use the new category
                        # or, if the old category was misc>other, fix it
                        search_name = name
                        category_id = new_category

                        log.info('release: [{}] - rename: {} ({} -> {} -> {})'.format(
                            release.search_name,
                            search_name,
                            old_category,
                            calculated_old_category,
                            category_id
                        ))

                        return search_name, category_id
                    else:
                        # if they're not the same parent and they're not misc, ignore
                        continue
            else:
                # the old name was apparently fine
                log.debug('release: [{}] - old name was fine'.format(
                    release.search_name
                ))
                return False, calculated_old_category

    log.debug('release: no good name candidates [{}]'.format(
        release.search_name
    ))
    return None, None


def clean_release_name(name):
    """Strip dirty characters out of release names. The API
    will match against clean names."""
    chars = ['#', '@', '$', '%', '^', '§', '¨', '©', 'Ö']
    for c in chars:
        name = name.replace(c, '')
    return name.replace('_', ' ').replace('.', ' ').replace('-', ' ')


def process():
    """Helper function to begin processing binaries. Checks
    for 100% completion and will create NZBs/releases for
    each complete release. Will also categorise releases,
    and delete old binaries."""

    # TODO: optimise query usage in this, it's using like 10-15 per release

    binary_count = 0
    added_count = 0

    if config.scan.get('publish', False):
        request_session = FuturesSession()
    else:
        request_session = None

    start = time.time()

    with db_session() as db:
        binary_query = """
            SELECT
                binaries.id, binaries.name, binaries.posted, binaries.total_parts
            FROM binaries
            INNER JOIN (
                SELECT
                    parts.id, parts.binary_id, parts.total_segments, count(*) as available_segments
                FROM parts
                    INNER JOIN segments ON parts.id = segments.part_id
                GROUP BY parts.id
                ) as parts
                ON binaries.id = parts.binary_id
            GROUP BY binaries.id
            HAVING count(*) >= binaries.total_parts AND (sum(parts.available_segments) / sum(parts.total_segments)) * 100 >= {}
            ORDER BY binaries.posted DESC
        """.format(config.postprocess.get('min_completion', 100))

        # pre-cache blacklists and group them
        blacklists = db.query(Blacklist).filter(Blacklist.status == True).all()
        for blacklist in blacklists:
            db.expunge(blacklist)

        # cache categories
        parent_categories = {}
        for category in db.query(Category).all():
            parent_categories[category.id] = category.parent.name if category.parent else category.name

        # for interest's sakes, memory usage:
        # 38,000 releases uses 8.9mb of memory here
        # no real need to batch it, since this will mostly be run with
        # < 1000 releases per run
        for completed_binary in engine.execute(binary_query).fetchall():
            # some optimisations here. we used to take the binary id and load it
            # then compare binary.name and .posted to any releases
            # in doing so, we loaded the binary into the session
            # this meant that when we deleted it, it didn't cascade
            # we had to submit many, many delete queries - one per segment/part
            # by including name/posted in the big query, we don't load that much data
            # but it lets us check for a release without another query, and means
            # that we cascade delete when we clear the binary

            # first we check if the release already exists
            r = db.query(Release).filter(Release.name == completed_binary[1]).filter(
                Release.posted == completed_binary[2]
            ).first()

            if r:
                # if it does, we have a duplicate - delete the binary
                db.query(Binary).filter(Binary.id == completed_binary[0]).delete()
            else:
                # get an approx size for the binary without loading everything
                # if it's a really big file, we want to deal with it differently
                binary = db.query(Binary).filter(Binary.id == completed_binary[0]).first()

                # get the group early for use in uniqhash
                group = db.query(Group).filter(Group.name == binary.group_name).one()

                # check if the uniqhash already exists too
                dupe_release = db.query(Release).filter(Release.uniqhash == _create_hash(binary.name, group.id, binary.posted)).first()
                if dupe_release:
                    db.query(Binary).filter(Binary.id == completed_binary[0]).delete()
                    continue

                # this is an estimate, so it doesn't matter too much
                # 1 part nfo, 1 part sfv or something similar, so ignore two parts
                # take an estimate from the middle parts, since the first/last
                # have a good chance of being something tiny
                # we only care if it's a really big file
                # abs in case it's a 1 part release (abs(1 - 2) = 1)
                # int(/2) works fine (int(1/2) = 0, array is 0-indexed)
                try:
                    est_size = (abs(binary.total_parts - 2) *
                                binary.parts[int(binary.total_parts / 2)].total_segments *
                                binary.parts[int(binary.total_parts / 2)].segments[0].size)
                except IndexError:
                    log.error('release: binary [{}] - couldn\'t estimate size - bad regex: {}?'.format(binary.id, binary.regex_id))
                    continue

                oversized = est_size > config.postprocess.get('max_process_size', 10 * 1024 * 1024 * 1024)

                if oversized and not config.postprocess.get('max_process_anyway', True):
                    log.debug('release: [{}] - removed (oversized)'.format(binary.name))
                    db.query(Binary).filter(Binary.id == completed_binary[0]).delete()
                    db.commit()
                    continue

                if oversized:
                    # for giant binaries, we do it differently
                    # lazyload the segments in parts and expunge when done
                    # this way we only have to store binary+parts
                    # and one section of segments at one time
                    binary = db.query(Binary).options(
                        subqueryload('parts'),
                        lazyload('parts.segments'),
                    ).filter(Binary.id == completed_binary[0]).first()
                else:
                    # otherwise, start loading all the binary details
                    binary = db.query(Binary).options(
                        subqueryload('parts'),
                        subqueryload('parts.segments'),
                        Load(Part).load_only(Part.id, Part.subject, Part.segments),
                    ).filter(Binary.id == completed_binary[0]).first()

                blacklisted = False
                for blacklist in blacklists:
                    if regex.search(blacklist.group_name, binary.group_name):
                        # we're operating on binaries, not releases
                        field = 'name' if blacklist.field == 'subject' else blacklist.field
                        if regex.search(blacklist.regex, getattr(binary, field)):
                            log.debug('release: [{}] - removed (blacklisted: {})'.format(binary.name, blacklist.id))
                            db.query(Binary).filter(Binary.id == binary.id).delete()
                            db.commit()
                            blacklisted = True
                            break

                if blacklisted:
                    continue

                binary_count += 1

                release = Release()
                release.name = binary.name
                release.original_name = binary.name
                release.posted = binary.posted
                release.posted_by = binary.posted_by
                release.regex_id = binary.regex_id
                release.grabs = 0

                # this counts segment sizes, so we can't use it for large releases
                # use the estimate for min_size and firm it up later during postproc
                if oversized:
                    release.size = est_size
                else:
                    release.size = binary.size()

                # check against minimum size for this group
                undersized = False
                for size, groups in config.postprocess.get('min_size', {}).items():
                    if binary.group_name in groups:
                        if release.size < size:
                            undersized = True
                            break

                if undersized:
                    log.debug('release: [{}] - removed (smaller than minimum size for group)'.format(
                        binary.name
                    ))
                    db.query(Binary).filter(Binary.id == binary.id).delete()
                    db.commit()
                    continue

                # check to make sure we have over the configured minimum files
                # this one's okay for big releases, since we're only looking at part-level
                rars = []
                rar_count = 0
                zip_count = 0
                nzb_count = 0

                for part in binary.parts:
                    if pynab.nzbs.rar_part_regex.search(part.subject):
                        rar_count += 1
                    if pynab.nzbs.rar_regex.search(part.subject) and not pynab.nzbs.metadata_regex.search(part.subject):
                        rars.append(part)
                    if pynab.nzbs.zip_regex.search(part.subject) and not pynab.nzbs.metadata_regex.search(part.subject):
                        zip_count += 1
                    if pynab.nzbs.nzb_regex.search(part.subject):
                        nzb_count += 1

                # handle min_archives
                # keep, nzb, under
                status = 'keep'
                archive_rules = config.postprocess.get('min_archives', 1)
                if isinstance(archive_rules, dict):
                    # it's a dict
                    if binary.group_name in archive_rules:
                        group = binary.group_name
                    else:
                        group = '*'

                    # make sure the catchall exists
                    if group not in archive_rules:
                        archive_rules[group] = 1

                    # found a special rule
                    if rar_count + zip_count < archive_rules[group]:
                        if nzb_count > 0:
                            status = 'nzb'
                        else:
                            status = 'under'
                else:
                    # it's an integer, globalise that shit yo
                    if rar_count + zip_count < archive_rules:
                        if nzb_count > 0:
                            status = 'nzb'
                        else:
                            status = 'under'

                # if it's an nzb or we're under, kill it
                if status in ['nzb', 'under']:
                    if status == 'nzb':
                        log.debug('release: [{}] - removed (nzb only)'.format(binary.name))
                    elif status == 'under':
                        log.debug('release: [{}] - removed (less than minimum archives)'.format(binary.name))

                    db.query(Binary).filter(Binary.id == binary.id).delete()
                    db.commit()
                    continue

                # clean the name for searches
                release.search_name = clean_release_name(binary.name)

                # assign the release group
                release.group = group

                # give the release a category
                release.category_id = pynab.categories.determine_category(binary.name, binary.group_name)

                # create the nzb, store it and link it here
                # no need to do anything special for big releases here
                # if it's set to lazyload, it'll kill rows as they're used
                # if it's a small release, it'll go straight from memory
                nzb = pynab.nzbs.create(release.search_name, parent_categories[release.category_id], binary)

                if nzb:
                    added_count += 1

                    log.info('release: [{}]: added release ({} rars, {} rarparts)'.format(
                        release.search_name,
                        len(rars),
                        rar_count
                    ))

                    release.nzb = nzb

                    # save the release
                    db.add(release)

                    try:
                        db.flush()
                    except Exception as e:
                        # this sometimes raises if we get a duplicate
                        # this requires a post of the same name at exactly the same time (down to the second)
                        # pretty unlikely, but there we go
                        log.debug('release: [{}]: duplicate release, discarded'.format(release.search_name))
                        db.rollback()

                    # delete processed binaries
                    db.query(Binary).filter(Binary.id == binary.id).delete()

                    # publish processed releases?
                    if config.scan.get('publish', False):
                        futures = [request_session.post(host, data=to_json(release)) for host in
                                   config.scan.get('publish_hosts')]

            db.commit()

    end = time.time()
    log.info('release: added {} out of {} binaries in {:.2f}s'.format(
        added_count,
        binary_count,
        end - start
    ))
