"""
Pynab nzedb pre import

Imports pre files from nzedb dropbox

Usage:
    nzedb_pre_import.py large|small

Options:
    -h --help       Show this screen.
    --version       Show version.

"""
#This is quite possibly the most hilariously complex import process...
#What I can gather as the column names from the csv, in case anyone else wants to do this.
#title 1, nfo, size, files, filename 9, nuked 11, nukereason, category 15 , predate 17, source 19, requestid 21, groupname 23

import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

from pynab.db import db_session, engine, Pre, copy_file
from pynab import releases
import urllib
import regex
import json
import io
from docopt import docopt

#Panadas is required
try:
	import pandas
except:
	print("pandas is required to use nzedb pre import: pip install pandas")

#BeautifulSoup is required
try:
	from bs4 import BeautifulSoup
except:
	print("BeautifulSoup is required to use nzedb pre import: pip install beautifulsoup4")



#Regex used to strip out the file name
FILENAME_REGEX = regex.compile('https:\/\/.+\/sh\/.+\/(?P<lastfile>.+)_.+_.+\?dl=1')
COLNAMES = ["name","filename","nuked","category","pretime","source","requestid","requestgroup"]
INSERTFAILS = []


def nzedbPre():

	downloadLinks = []

	#Nab the HTML used in beautifulSoup
	try:
		preHTML = urllib.request.urlopen("https://www.dropbox.com/sh/fb2pffwwriruyco/AACy9Egno_v2kcziVHuvWbbxa")
		soup = BeautifulSoup(preHTML.read())
	except:
		print("Pre-Import: Error connecting to dropbox, try again later")

	try:
		data = open('lastfile.json')
		lastFileFromDisk = json.load(data)
	except:
		print("Pre-Import: No existinfg file found, will attempt to download and insert all pres")
		lastFileFromDisk = None


	#Find all the download links, change the download from 0 to 1
	for x in soup.findAll("a", {"class" : "filename-link"}):
		cleanLink = x['href'][:-1] + '1'
		downloadLinks.append(cleanLink)


	#try remove the top two links (if they exist)
	try:
		downloadLinks.remove('https://www.dropbox.com/sh/fb2pffwwriruyco/AADGwFkXBXgW8vhQmo7S1L3Sa/0_batch_import.php?dl=1')
	except:
		pass
	
	try:
		downloadLinks.remove('https://www.dropbox.com/sh/fb2pffwwriruyco/AAD2-CozDOXFxFDMgLZ6Dwv_a/0README.txt?dl=1')
	except:
		pass


	#Try and process each of the csv's. If they are
	for preCSV in downloadLinks:
		processingFile = FILENAME_REGEX.search(preCSV).groupdict()

		if lastFileFromDisk is None or int(processingFile['lastfile']) > lastFileFromDisk['lastfile']:
			
			try:
				print("Pre-Import: Attempting to download file: {}".format(processingFile['lastfile']))
				urllib.request.urlretrieve(preCSV, "unformattedDL.gz")
			except:
				print("Pre-Import: Error downloading: {} - Please run the process again".format(preCSV))
				INSERTFAILS.append(processingFile['lastfile'])
				#The assumption here is, if one fails, you should probably just start again at that file.
				break
			
			#Get the data into datatable, much easier to work with.
			dirtyFile = pandas.read_csv('unformattedDL.gz', sep='\t', compression='gzip', header=None, na_values='\\N', usecols=[0,8,10,14,16,18,20,22], names=COLNAMES)

			#Clean and process the file
			process(dirtyFile, processingFile)


		else:
			print("Pre-Import: More than likely {} has already been imported".format(processingFile['lastfile']))
			pass


	if INSERTFAILS is not None:
		print("Pre-Import: Failures: {}".format(INSERTFAILS))


def largeNzedbPre():
	
	try:
		dirtyChunk = pandas.read_table('predb_dump-062714.csv', sep='\t', header=None, na_values='\\N', usecols=[0,8,10,14,16,18,20,22], names=COLNAMES, chunksize=10000, engine='python')
	except:
		print("Pre-Import: File predb_dump-062714.csv not found")
	

	i = 0

	for chunk in dirtyChunk: 
		process(chunk)
		print("Pre-Import: Imported chunk {}".format(i))
		i += 1


def process(precsv, processingFile=None):
		
	ordering = ['name','filename','nuked','category','pretime','source','requestid','requestgroup','searchname']
	
	#Clean up the file a bit.
	precsv.replace("'", '', inplace=True, regex=True)
	precsv["nuked"].replace("2", "0", inplace=True)
	precsv["nuked"].replace("3", "1", inplace=True)
	precsv["nuked"].replace("4", "1", inplace=True)
	precsv["nuked"].replace("5", "1", inplace=True)
	precsv["nuked"].replace("69", "0", inplace=True)
	precsv.replace(".\\N$", '', inplace=True, regex=True)

	#Sometimes there are duplicates within the table itself, remove them
	precsv.drop_duplicates(subset='name', take_last=True, inplace=True)

	#Add clean searchname column
	precsv['searchname'] = precsv['name'].map(lambda name: releases.clean_release_name(name))
		
	#Create a list of names to check if they exist
	names = list(precsv.name)

	#Query to find any existing pres, we need to delete them so COPY doesn't fail
	with db_session() as db:
		
		pres = db.query(Pre).filter(Pre.name.in_(names)).all()

		prenamelist = []
		for pre in pres:
			prenamelist.append(pre.name)
		
		#Create the inverse list, basically contains pres that already exist
		newdata = precsv[~precsv['name'].isin(prenamelist)]

		data = io.StringIO()
		newdata.to_csv(data, index=False, header=False)
		
		#Delete any pres found as we are essentially going to update them
		if len(newdata) is not 0:
			for pre in pres:
				db.delete(pre)
		else:
			print("Pre-Import: No pres to add from this file")
		
		db.commit()


	try:
		if processingFile is not None:
			print("Pre-Import: Attempting to add {} to the database".format(processingFile['lastfile']))
			
			data.seek(0)
			copy_file(engine, data, ordering, Pre)
			
			#Write out the last pre csv name so it can be restarted later without downloading all the pres.
			with open('lastfile.json', 'w') as outfile:
				json.dump({'lastfile' : int(processingFile['lastfile'])}, outfile)
		
		else:
			data.seek(0)
			copy_file(engine, data, ordering, Pre)
			data.close()
			print("Pre-Import: Chunk import successful")
	
	except Exception as e:
		print("Pre-Import: Error inserting into database - {}".format(e))
		
		if processingFile is not None:
			INSERTFAILS.append(processingFile['lastfile'])	
		else:
			print("Pre-Import: Error processing chunk")


if __name__ == '__main__':
	
	arguments = docopt(__doc__)

	if arguments['small']:
		nzedbPre()	
	elif arguments['large']:
		largeNzedbPre()