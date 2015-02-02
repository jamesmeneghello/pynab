#title 1, nfo, size, files, filename 9, nuked 11, nukereason, category 15 , predate 17, source 19, requestid 21, groupname 23
#name,filename,nuked,category,pretime,source,requestid,groupname

import os
from os import listdir
import sys
from pynab.db import db_session, engine, Pre
import urllib
import regex
import json
import csv

#BeautifulSoup is required
try:
	from bs4 import BeautifulSoup
except:
	log.error("BeautifulSoup is required to use orlydb scraping: pip install beautifulsoup4")



#Regex used to strip out the file name
FILENAME_REGEX = regex.compile('https:\/\/.+\/sh\/.+\/(?P<lastfile>.+)_.+_.+\?dl=1')

def processNzedbPre():

	downloadLinks = []
	insertFails = []

	#Nab the HTML used in beautifulSoup
	try:
		preHTML = urllib.request.urlopen("https://www.dropbox.com/sh/fb2pffwwriruyco/AACy9Egno_v2kcziVHuvWbbxa")
		soup = BeautifulSoup(preHTML.read())
	except:
		print("Error connecting to dropbox, try again later")

	try:
		data = open('lastfile.json')
		lastFileFromDisk = json.load(data)
	except:
		print("No existinfg file found, will attempt to download and insert all pres")
		lastFileFromDisk = None

	#Find all the download links, change the download from 0 to 1
	for x in soup.findAll("a", {"class" : "filename-link"}):
		cleanLink = x['href'][:-1] + '1'
		downloadLinks.append(cleanLink)


	#remove the top two links
	downloadLinks.remove('https://www.dropbox.com/sh/fb2pffwwriruyco/AADGwFkXBXgW8vhQmo7S1L3Sa/0_batch_import.php?dl=1')
	downloadLinks.remove('https://www.dropbox.com/sh/fb2pffwwriruyco/AAD2-CozDOXFxFDMgLZ6Dwv_a/0README.txt?dl=1')



	for preCSV in downloadLinks:
		processingFile = FILENAME_REGEX.search(preCSV).groupdict()

		if lastFileFromDisk is None or int(processingFile['lastfile']) > lastFileFromDisk['lastfile']:
			
			try:
				urllib.request.urlretrieve(preCSV, "unformattedDL.gz")
			except:
				print("Error downloading: {}".format(preCSV))
				insertFails.append(processingFile['lastfile'])
				break

			#Clean out some things we cant work with. Probably a better way to do this!
			os.system("csvcut -t -q 3 -c 1,9,11,15,17,19,21,23 unformattedDL.gz > formattedUL.csv")
			os.system('sed -i s/"\'"/""/g {}'.format("formattedUL.csv"))
			os.system('sed -i s/,2,/,0,/g {}'.format("formattedUL.csv"))
			os.system('sed -i s/,3,/,1,/g {}'.format("formattedUL.csv"))
			os.system('sed -i s/,4,/,1,/g {}'.format("formattedUL.csv"))
			os.system('sed -i s/,5,/,1,/g {}'.format("formattedUL.csv"))
			#os.system('sed -i s/",\\N"/''/g {}'.format("formattedUL.csv"))

			#open the file ready for import
			formattedUL = open('formattedUL.csv')
			dictCSV = csv.DictReader(formattedUL, fieldnames = ("name","filename","nuked","category","pretime","source","requestid","requestgroup"), dialect=csv)
			#dictCSV.fieldnames = "name","filename","nuked","category","pretime","source","requestid","requestgroup"
			#conn = engine.raw_connection()
			#cur = conn.cursor()
			#print("need to process")
			with db_session() as db:
				for i, data in enumerate(dictCSV):
					p = Pre(**data)
					db.add(p)
					if i % 1000 == 0:
						db.flush()
				try:
					db.commit()		
				except:
					print("probably a dupe error")	
					insertFails.append(processingFile['lastfile'])
			
			'''try:
				cur.copy_expert("COPY pres2 (name,filename,nuked,category,pretime,source,requestid,requestgroup) FROM STDIN WITH CSV", formattedUL)
				conn.commit()
			except Exception as e:
				print("Pre-Import: Error inserting into database - {}".format(e))
				insertFails.append(processingFile['lastfile'])	
			'''
			with open('lastfile.json', 'w') as outfile:
				json.dump({'lastfile' : int(processingFile['lastfile'])}, outfile)
			
		else:
			pass

	print(insertFails)
processNzedbPre()
