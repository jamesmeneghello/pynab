"""
Pynab nzedb pre import

Imports pre files from nzedb dropbox

Usage:
    nzedb_pre_import.py large|small

Options:
    -h --help       Show this screen.
    --version       Show version.

"""
# This is quite possibly the most hilariously complex import process...
# What I can gather as the column names from the csv, in case anyone else wants to do this.
# title 1, nfo, size, files, filename 9, nuked 11, nukereason, category 15 , predate 17, source 19, requestid 21, groupname 23

import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

from pynab.db import db_session, engine, Pre, copy_file
from pynab import releases
import urllib
import regex
import json
import io
from docopt import docopt
from pySmartDL import SmartDL

# Panadas is required
try:
    import pandas
except:
    print("pandas is required to use nzedb pre import: pip install pandas")

# BeautifulSoup is required
try:
    from bs4 import BeautifulSoup
except:
    print("BeautifulSoup is required to use nzedb pre import: pip install beautifulsoup4")

# Regex used to strip out the file name
FILENAME_REGEX = regex.compile(
    "https:\/\/raw.githubusercontent.com\/nZEDb\/nZEDbPre_Dumps\/master\/dumps\/\d{10,}\/(?P<lastfile>.+)_.+_.+")
COLNAMES = ["name", "filename", "nuked", "category", "pretime", "source", "requestid", "requestgroup"]
INSERTFAILS = []


def nzedbPre():
    downloadLinks = []
    try:
        rawlistJSON = urllib.request.urlopen("https://api.github.com/repositories/45781004/contents/dumps").read()
    except:
        print("pre-import: Error connecting to dropbox, try again later")

    try:
        data = open('lastfile.json')
        lastFileFromDisk = json.load(data)
    except:
        print("pre-import: No existing file found, will attempt to download and insert all pres")
        lastFileFromDisk = None

    listJSON = json.loads(rawlistJSON.decode('utf8'))

    for x in listJSON:
        if x["name"] != "0README.txt":
            try:
                rawpreJSON = urllib.request.urlopen(x["url"]).read()
            except:
                print("pre-import: failed fetching url: ", x["url"])

            preJSON = json.loads(rawpreJSON.decode('utf8'))
            for y in preJSON:
                downloadLinks.append(y["download_url"])

    # Try and process each of the csv's. If they are
    for preCSV in downloadLinks:
        processingFile = FILENAME_REGEX.search(preCSV).groupdict()

        if lastFileFromDisk is None or int(processingFile['lastfile']) > lastFileFromDisk['lastfile']:

            try:
                print("pre-import: Attempting to download file: {}".format(processingFile['lastfile']))
                urllib.request.urlretrieve(preCSV, "unformattedDL.gz")
            except:
                print("pre-import: Error downloading: {} - Please run the process again".format(preCSV))
                INSERTFAILS.append(processingFile['lastfile'])
                # The assumption here is, if one fails, you should probably just start again at that file.
                break

            # Get the data into datatable, much easier to work with.
            dirtyFile = pandas.read_csv('unformattedDL.gz', sep='\t', compression='gzip', header=None, na_values='\\N',
                                        usecols=[0, 8, 10, 14, 16, 18, 20, 22], names=COLNAMES)

            # Clean and process the file
            process(dirtyFile, processingFile)

        else:
            print("pre-import: More than likely {} has already been imported".format(processingFile['lastfile']))
            pass

    if len(INSERTFAILS) is not 0:
        print("pre-import: Failures: {}".format(INSERTFAILS))


def largeNzedbPre():
    if os.path.isfile('predb_dump-062714.csv.gz'):
        fileExists = True
    else:
        try:
            url = "https://www.dropbox.com/s/btr42dtzzyu3hh3/predb_dump-062714.csv.gz?dl=1"
            dest = "."

            print("pre-import: File predb_dump-062714.csv not found, attempt to download - may take a while, its 300mb")

            obj = SmartDL(url, dest)
            obj.start()

            fileExists = True
        except:
            print("pre-import: Error downloading/unzipping. Please try again.")
            exit(0)

    if fileExists:
        dirtyChunk = pandas.read_table('predb_dump-062714.csv.gz', compression='gzip', sep='\t', header=None,
                                       na_values='\\N', usecols=[0, 8, 10, 14, 16, 18, 20, 22], names=COLNAMES,
                                       chunksize=10000, engine='c', error_bad_lines=False, warn_bad_lines=False)
    else:
        print("pre-import: File predb_dump-062714.csv not found, please try again.")
        exit(0)

    i = 0
    for chunk in dirtyChunk:
        process(chunk)
        print("pre-import: Imported chunk {}".format(i))
        i += 1


def process(precsv, processingFile=None):
    ordering = ['name', 'filename', 'nuked', 'category', 'pretime', 'source', 'requestid', 'requestgroup', 'searchname']

    # Clean up the file a bit.
    precsv.replace("'", "", inplace=True, regex=True)
    precsv["nuked"].replace("2", "0", inplace=True)
    precsv["nuked"].replace("3", "1", inplace=True)
    precsv["nuked"].replace("4", "1", inplace=True)
    precsv["nuked"].replace("5", "1", inplace=True)
    precsv["nuked"].replace("69", "0", inplace=True)
    precsv.replace(".\\N$", '', inplace=True, regex=True)

    # Sometimes there are duplicates within the table itself, remove them
    precsv.drop_duplicates(subset='name', take_last=True, inplace=True)

    # Add clean searchname column
    precsv['searchname'] = precsv['name'].map(lambda name: releases.clean_release_name(name))

    # Drop the pres without requestid's
    precsv = precsv[precsv.requestid != '0']

    # Create a list of names to check if they exist
    names = list(precsv.name)

    # Query to find any existing pres, we need to delete them so COPY doesn't fail
    prenamelist = []
    with db_session() as db:

        if names:
            pres = db.query(Pre).filter(Pre.name.in_(names)).all()

            for pre in pres:
                prenamelist.append(pre.name)

        data = io.StringIO()
        precsv.to_csv(data, index=False, header=False)

        # Delete any pres found as we are essentially going to update them
        if prenamelist:
            for pre in pres:
                db.delete(pre)
            db.commit()
            print("pre-import: Deleted {} pres that will re-inserted".format(len(prenamelist)))
        else:
            print("pre-import: File clean, no pres need to be deleted before re-insert")

    try:
        if processingFile is not None:
            print("pre-import: Attempting to add {} to the database".format(processingFile['lastfile']))

            data.seek(0)
            copy_file(engine, data, ordering, Pre)

            # Write out the last pre csv name so it can be restarted later without downloading all the pres.
            with open('lastfile.json', 'w') as outfile:
                json.dump({'lastfile': int(processingFile['lastfile'])}, outfile)

        else:
            data.seek(0)
            copy_file(engine, data, ordering, Pre)
            data.close()
            print("pre-import: Chunk import successful")

    except Exception as e:
        print("pre-import: Error inserting into database - {}".format(e))

        if processingFile is not None:
            INSERTFAILS.append(processingFile['lastfile'])
        else:
            print("pre-import: Error processing chunk")


if __name__ == '__main__':

    arguments = docopt(__doc__)

    if arguments['small']:
        nzedbPre()
    elif arguments['large']:
        largeNzedbPre()
