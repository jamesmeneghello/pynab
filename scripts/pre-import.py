#title 1, nfo, size, files, filename 9, nuked 11, nukereason, category 15 , predate 17, source 19, requestid 21, groupname 23
#name,filename,nuked,category,pretime,source,requestid,groupname

import os
from os import listdir
import sys
from pynab.db import db_session, engine
import urllib
import regex
import json

#BeautifulSoup is required
try:
	from bs4 import BeautifulSoup
except:
	log.error("BeautifulSoup is required to use orlydb scraping: pip install beautifulsoup4")

downloadLinks = []


#Regex used to strip out the file name
FILENAME_REGEX = regex.compile('https:\/\/.+\/sh\/.+\/(?P<filename>.+)_.+_.+\?dl=1')

#Nab the HTML used in beautifulSoup
preHTML = urllib.request.urlopen("https://www.dropbox.com/sh/fb2pffwwriruyco/AACy9Egno_v2kcziVHuvWbbxa")
soup = BeautifulSoup(preHTML.read())

#Find all the download links, change the download from 0 to 1
for x in soup.findAll("a", {"class" : "filename-link"}):
	cleanLink = x['href'][:-1] + '1'
	downloadLinks.append(cleanLink)


#remove the top two links
downloadLinks.remove('https://www.dropbox.com/sh/fb2pffwwriruyco/AADGwFkXBXgW8vhQmo7S1L3Sa/0_batch_import.php?dl=1')
downloadLinks.remove('https://www.dropbox.com/sh/fb2pffwwriruyco/AAD2-CozDOXFxFDMgLZ6Dwv_a/0README.txt?dl=1')


for x in downloadLinks:
	preImportFile = FILENAME_REGEX.search(x).groupdict()
	
	try:
		urllib.request.urlretrieve(x, "unformattedDL.gz")
	except:
		print("Error downloading: {}".format(x))

	#Clean out some things we cant work with. Probably a better way to do this!
	os.system("csvcut -t -q 3 -c 1,9,11,15,17,19,21,23 unformattedDL.gz > formattedUL.csv")
	os.system('sed -i s/"\'"/""/g {}'.format("formattedUL.csv"))
	os.system('sed -i s/,2,/,0,/g {}'.format("formattedUL.csv"))
	os.system('sed -i s/,3,/,1,/g {}'.format("formattedUL.csv"))
	os.system('sed -i s/,4,/,1,/g {}'.format("formattedUL.csv"))
	os.system('sed -i s/,5,/,1,/g {}'.format("formattedUL.csv"))

	#open the file ready for import
	formattedUL = open('formattedUL.csv')
	
	conn = engine.raw_connection()
	cur = conn.cursor()
	
	try:
		cur.copy_expert("COPY pre2 (name,filename,nuked,category,pretime,source,requestid,requestgroup) FROM STDIN WITH CSV", formattedUL)
	except Exception as e:
		print("Pre-Import: Error inserting into database - {}".format(e))	

	try:
		conn.commit()
	except:
		print("More than likely a pre is already in the db")
	
	with open('lastfile.json', 'w') as outfile:
		json.dump({'lastfile' : int(preImportFile['filename'])}, outfile)
	
	break



#print(downloadLinks)

#print(links)
'''
os.system("csvcut -t -q 3 -c 1,9,11,15,17,19,21,23 1404152742_predb_dump.csv.gz > bla.csv")

#with db_session as db:
#conn = engine.raw_connection()
#os.system('csvsql --db {} --table fy09 --insert bla.csv'.format(conn))
#COPY ratings FROM '/path/blah.csv' DELIMITER ',' CSV;



#States are Nuked 1, Unnuked 2, Modnuked 3, Renuked 4, Oldnuked 5
#This is a pain..
os.system('sed -i s/"\'"/""/g {}'.format("bla.csv"))
os.system('sed -i s/,2,/,0,/g {}'.format("bla.csv"))
os.system('sed -i s/,3,/,1,/g {}'.format("bla.csv"))
os.system('sed -i s/,4,/,1,/g {}'.format("bla.csv"))
os.system('sed -i s/,5,/,1,/g {}'.format("bla.csv"))

my_file = open('bla.csv')

conn = engine.raw_connection()
cur = conn.cursor()
try:
	cur.copy_expert("COPY pre2 (name,filename,nuked,category,pretime,source,requestid,requestgroup) FROM STDIN WITH CSV", my_file )
except Exception as e:
	print("Pre-Import: Error inserting into database - {}".format(e))
#cur.copy_expert("COPY pre2 (name,filename,nuked,category,pretime,source,requestid,requestgroup) FROM 'bla.csv' WITH CSV",sys.stdin )
try:
	conn.commit()
except:
	print("no")
#cur.copy_from(my_file, 'pre2', ",", columns=('name','filename','nuked','category','pretime','source','requestid','requestgroup'))
#print(os.listdir("."))
'''

'''
#for x in os.listdir("."):
#	if x.endswith("csv"):
#		print(x)

#os.system('csvcut -c 1,9,15,17,19,21,23 bla.csv > test.csv')

'''