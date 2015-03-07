from pynab import log
from pynab.db import db_session, Release, Pre, Group


GROUP_ALIASES = {
    # from: to
    'alt.binaries.etc': 'alt.binaries.teevee',
}


def process(limit=None):
    """Process releases for requests"""

    with db_session() as db:
        query = db.query(Release).join(Group).filter(Release.name.like('REQ:%')).filter(Release.pre_id == None).filter(
            Release.category_id == '8010')

        if limit:
            releases = query.order_by(Release.posted.desc()).limit(limit)
        else:
            releases = query.order_by(Release.posted.desc()).all()

        # create a dict of request id's and releases
        requests = {}

        if releases:
            for release in releases:
                # check if it's aliased
                if release.group.name in GROUP_ALIASES:
                    group_name = GROUP_ALIASES[release.group.name]
                else:
                    group_name = release.group.name

                if group_name not in requests:
                    requests[group_name] = {}

                try:
                    requests[group_name][int(release.name.split(': ')[1])] = release
                except ValueError:
                    # request hash?
                    continue

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
                updated_release = group_requests.get(pre.requestid)
                updated_release.pre_id = pre.id
                db.merge(updated_release)
                log.info("requests: found pre request id {} ({}) for {}".format(pre.requestid, group_name,
                                                                                updated_release.name))

            db.commit()