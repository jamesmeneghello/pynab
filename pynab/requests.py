from pynab import log
from pynab.db import db_session, Release, Pre
from pynab.server import Server


def get(release):
    """Get Release Name from Pre Request"""
    return release.pre.name

def process(limit=None, category=0):
    """Process releases for requests"""

    with Server() as server:
        with db_session() as db:
            query = db.query(Release).filter(Release.name.like('%REQ:%')).filter(Release.pre_id==None).filter(Release.category_id=='8010')

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
                log.info("Requests: No release requests to process")

            # query for the requestids
            if requests:
                pres = db.query(Pre).filter(Pre.requestid.in_(requests.keys())).all()
            else:
                log.info("Requests: No pre requests found")
                pres = []
            
            # loop through and associate pres with their requests
            for pre in pres:

                if pre.requestid in requests and pre.requestgroup == requests.get(pre.requestid).group.name:
                    updaterelease = requests.get(pre.requestid)
                    updaterelease.pre_id = pre.id
                    db.add(updaterelease) 
                    log.info("Requests: Found pre request id {} for {}".format(pre.requestid, updaterelease.name))
                else:
                    log.info("Requests: No pre request found for {}".format(requests.get(pre.requestid).name))
            
            db.commit()        