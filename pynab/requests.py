from pynab import log
from pynab.db import db_session, Release, Pre


def process(limit=None):
    """Process releases for requests"""

    with db_session() as db:
        query = db.query(Release).filter(Release.name.like('REQ:%')).filter(Release.pre_id == None).filter(
            Release.category_id == '8010')

        if limit:
            releases = query.order_by(Release.posted.desc()).limit(limit)
        else:
            releases = query.order_by(Release.posted.desc()).all()

        # create a dict of request id's and releases
        requests = {}

        if releases:
            for release in releases:
                requests[int(release.name.split(': ')[1])] = release
        else:
            log.info("requests: no release requests to process")

        # query for the requestids
        if requests:
            pres = db.query(Pre).filter(Pre.requestid.in_(requests.keys())).all()
        else:
            log.info("requests: no pre requests found")
            pres = []

        # loop through and associate pres with their requests
        for pre in pres:
            if pre.requestgroup == requests.get(pre.requestid).group.name:
                updaterelease = requests.get(pre.requestid)
                updaterelease.pre_id = pre.id
                db.merge(updaterelease)
                log.info("requests: found pre request id {} ({}) for {}".format(pre.requestid, pre.requestgroup,
                                                                                updaterelease.name))
            else:
                log.info("requests: no pre request found for {}".format(requests.get(pre.requestid).name))

        db.commit()