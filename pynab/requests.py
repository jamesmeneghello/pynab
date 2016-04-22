import regex

from pynab import log
from pynab.db import db_session, Release, Pre, Group, windowed_query
import config


GROUP_ALIASES = {
    # from: to
    'alt.binaries.etc': 'alt.binaries.teevee',
}

GROUP_REQUEST_REGEXES = {
    'alt.binaries.etc': '^(\d{4,8})$',
    'alt.binaries.teevee': '^(\d{4,8})$',
    'alt.binaries.moovee': '^(\d{4,8})$',
}


def process(limit=None):
    """Process releases for requests"""

    with db_session() as db:
        requests = {}
        for group, reg in GROUP_REQUEST_REGEXES.items():
            # noinspection PyComparisonWithNone
            query = db.query(Release).join(Group).filter(Group.name==group).filter(Release.pre_id == None).\
                filter(Release.category_id == '8010').filter("releases.name ~ '{}'".format(reg))

            for release in windowed_query(query, Release.id, config.scan.get('binary_process_chunk_size')):
                # check if it's aliased
                if release.group.name in GROUP_ALIASES:
                    group_name = GROUP_ALIASES[release.group.name]
                else:
                    group_name = release.group.name

                if group_name not in requests:
                    requests[group_name] = {}

                result = regex.search(reg, release.name)
                if result:
                    requests[group_name][result.group(0)] = release

        else:
            log.info("requests: no release requests to process")

        # per-group
        for group_name, group_requests in requests.items():
            # query for the requestids
            if requests:
                pres = db.query(Pre).filter(Pre.requestgroup==group_name).filter(Pre.requestid.in_(group_requests.keys())).all()
            else:
                log.info("requests: no pre requests found")
                pres = []

            # loop through and associate pres with their requests
            for pre in pres:
                # no longer need to check group
                updated_release = group_requests.get(str(pre.requestid))
                updated_release.pre_id = pre.id
                updated_release.name = pre.name
                updated_release.search_name = pre.searchname
                db.merge(updated_release)
                log.info("requests: found pre request id {} ({}) for {}".format(pre.requestid, group_name,
                                                                                updated_release.name))

            db.commit()
