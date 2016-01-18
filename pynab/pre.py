# import re
import bs4
import regex
import requests

from pynab import log, releases
from pynab.db import db_session, Pre


def nzedbirc(unformattedPre):
    formattedPre = parseNzedbirc(unformattedPre)

    if formattedPre is not None:
        with db_session() as db:
            p = db.query(Pre).filter(Pre.name == formattedPre['name']).first()
        
            if not p:
                p = Pre(**formattedPre)
            else:
                for k, v in formattedPre.items():
                    setattr(p, k, v)

            try:
                db.add(p)
                log.info("pre: Inserted/Updated - {}".format(formattedPre["name"]))
            except Exception as e:
                log.debug("pre: Error - {}".format(e))


#Message legend: DT: PRE Time(UTC) | TT: Title | SC: Source | CT: Category | RQ: Requestid | SZ: Size | FL: Files | FN: Filename
#Sample: NEW: [DT: 2015-01-09 16:08:45][TT: Sample-Release][SC: sample-source][CT: 0DAY][RQ: N/A][SZ: N/A][FL: N/A][FN: N/A]
def parseNzedbirc(unformattedPre):
    PRE_REGEX = regex.compile(
        '(?P<preType>.+): \[DT: (?<pretime>.+)\] \[TT: (?P<name>.+)\] \[SC: (?P<source>.+)\] \[CT: (?P<category>.+)\] \[RQ: (?P<request>.+)\] \[SZ: (?P<size>.+)\] \[FL: (?P<files>.+)\] \[FN: (?P<filename>.+)\]')

    formattedPre = {}

    try:
        formattedPre = PRE_REGEX.search(unformattedPre).groupdict()
    except Exception as e:
        log.debug("pre: Error parsing nzedbirc - {}".format(e))
        formattedPre = None

    if formattedPre is not None:
        if formattedPre['preType'] == "NUK":
            formattedPre['nuked'] = True
        else:
            formattedPre['nuked'] = False

        #Deal with splitting out requests if they exist
        if formattedPre['request'] != "N/A":
            formattedPre['requestid'] = formattedPre['request'].split(":")[0]
            formattedPre['requestgroup'] = formattedPre['request'].split(":")[1]
        else:
            formattedPre['requestid'] = None

        formattedPre['searchname'] = releases.clean_release_name(formattedPre['name'])

        #remove any columns we dont need. Perhaps a way to filter these out via regex? Or a way to ignore via sqlalchemy
        formattedPre.pop("preType", None)
        formattedPre.pop("size", None)
        formattedPre.pop("files", None)
        formattedPre.pop("request", None)

        return formattedPre
    else:
        return None


# orlydb scraping
# Returns the category of a pre if there is a match
def orlydb(name, search_name):
    # BeautifulSoup is required
    try:
        from bs4 import BeautifulSoup
    except:
        log.error("BeautifulSoup is required to use orlydb scraping: pip install beautifulsoup4")

    try:
        preHTML = requests.get('http://orlydb.com/?q={}'.format(search_name))
    except:
        log.debug("Error connecting to orlydb")
        return False

    soup = bs4.BeautifulSoup(preHTML.read())
    releases = soup.find(id="releases").findAll("div")

    rlsDict = {}
    rlsname = None
    for rls in releases:
        # Try/except used to filter out None types
        # pretime left as may be used later
        try:
            rlsname = rls.find("span", {"class": "release"}).get_text()
            # pretime = rls.find("span", {"class" : "timestamp"}).get_text()
            category = rls.find("span", {"class": "section"}).find("a").get_text()

            # If the release matches what is passed, return the category in a dict
            # This could be a problem if 2 pre's have the same name but different categories, chances are slim though
            if rlsname == name:
                rlsDict["category"] = category
        except Exception as e:
            log.debug("Error parsing to orlydb reponse: {}".format(e))
            return False

    if rlsDict:
        log.info("Orlydb pre found: {}".format(rlsname))
        return rlsDict
    else:
        return False