import regex
import gzip

import pynab.nzbs
import pynab.util
from pynab import log
from pynab.db import db_session, Release, Group, NZB, SFV, MetaBlack
from pynab.server import Server
import pynab.releases

SFV_MAX_FILESIZE = 50000

SFV_REGEX = [
    regex.compile('((?>\w+[.\-_])+(?:\w+-\d*[a-zA-Z][a-zA-Z0-9]*)+(\.rar ))', regex.I),
]


def attempt_parse(sfv):
    potential_names = []

    for regex in SFV_REGEX:
        result = regex.search(sfv)
        if result:
            potential_names.append(result.group(0))

    return potential_names


def get(sfv):
    """Un-gzips an SFV."""
    return gzip.decompress(sfv.data)


def process(limit=None, category=0):
    """Process releases for SFV parts and download them."""

    with Server() as server:
        with db_session() as db:
            query = db.query(Release).join(Group).join(NZB).filter(Release.sfv==None).filter(Release.sfv_metablack_id==None)
            if category:
                query = query.filter(Release.category_id == int(category))
            if limit:
                releases = query.order_by(Release.posted.desc()).limit(limit)
            else:
                releases = query.order_by(Release.posted.desc()).all()

            for release in releases:
                found = False

                nzb = pynab.nzbs.get_nzb_details(release.nzb)
                if nzb:
                    sfvs = []
                    for sfv in nzb['sfvs']:
                        for part in sfv['segments']:
                            if int(part['size']) > SFV_MAX_FILESIZE:
                                continue
                            sfvs.append(part)

                    for sfv in sfvs:
                        try:
                            article = server.get(release.group.name, [sfv['message_id'], ])
                        except:
                            article = None

                        if article:
                            data = gzip.compress(article.encode('utf-8'))
                            sfv = SFV(data=data)
                            db.add(sfv)

                            release.sfv = sfv
                            release.sfv_metablack_id = None
                            db.add(release)

                            log.info('sfv: [{}] - [{}] - sfv added'.format(
                                release.id,
                                release.search_name
                            ))
                            found = True
                            break

                    if not found:
                        log.warning('sfv: [{}] - [{}] - no sfvs in release'.format(
                            release.id,
                            release.search_name
                        ))
                        mb = MetaBlack(sfv=release, status='IMPOSSIBLE')
                        db.add(mb)
                db.commit()