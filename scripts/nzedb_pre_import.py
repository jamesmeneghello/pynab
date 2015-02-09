#This is quite possibly the most hilariously complex import process...
#What I can gather as the column names from the csv, in case anyone else wants to do this.
#title 1, nfo, size, files, filename 9, nuked 11, nukereason, category 15 , predate 17, source 19, requestid 21, groupname 23

import os
import sys
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
from pynab.db import db_session, engine, Pre
import urllib
import regex
import json
import subprocess

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

def processNzedbPre():

	downloadLinks = []
	insertFails = []

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


	#remove the top two links
	downloadLinks.remove('https://www.dropbox.com/sh/fb2pffwwriruyco/AADGwFkXBXgW8vhQmo7S1L3Sa/0_batch_import.php?dl=1')
	downloadLinks.remove('https://www.dropbox.com/sh/fb2pffwwriruyco/AAD2-CozDOXFxFDMgLZ6Dwv_a/0README.txt?dl=1')



	for preCSV in downloadLinks:
		processingFile = FILENAME_REGEX.search(preCSV).groupdict()

		if lastFileFromDisk is None or int(processingFile['lastfile']) > lastFileFromDisk['lastfile']:
			
			try:
				print("Pre-Import: Attempting to download file: {}".format(processingFile['lastfile']))
				urllib.request.urlretrieve(preCSV, "unformattedDL.gz")
			except:
				print("Pre-Import: Error downloading: {}".format(preCSV))
				insertFails.append(processingFile['lastfile'])
				#The assumption here is, if the first one fails, more than likely they will all fail
				break


			#Clean out some things we cant work with. Probably a better way to do this!
			cleanFile = pandas.read_csv('unformattedDL.gz', sep='\t', compression='gzip', header=None, na_values='\\N', usecols=[0,8,10,14,16,18,20,22])
			cleanFile.to_csv('formattedUL.csv', index=False, header=False)

			os.system('sed -i s/"\'"/""/g {}'.format("formattedUL.csv"))
			os.system('sed -i s/,2,/,0,/g {}'.format("formattedUL.csv"))
			os.system('sed -i s/,3,/,1,/g {}'.format("formattedUL.csv"))
			os.system('sed -i s/,4,/,1,/g {}'.format("formattedUL.csv"))
			os.system('sed -i s/,5,/,1,/g {}'.format("formattedUL.csv"))
			#For whatever reason this wouldnt work using os.system
			subprocess.call(['sed', '-i', 's/.\\N$/''/g', 'formattedUL.csv'], shell=False )

			#Get the data into datatable, much easier to work with.
			colnames = ["name","filename","nuked","category","pretime","source","requestid","requestgroup"]
			data = pandas.read_csv('formattedUL.csv', names=colnames)
			
			#Sometimes there are duplicates within the table itself, remove them
			data.drop_duplicates(subset='name', take_last=True, inplace=True)

			#Create a list of names to check if they exist
			names = list(data.name)

			#Query to find any existing pres, we need to delete them so COPY doesn't fail
			with db_session() as db:
				pres = db.query(Pre).filter(Pre.name.in_(names)).all()

				prenamelist = []
				for pre in pres:
					prenamelist.append(pre.name)
				
				#Create the inverse list, basically contains pres that already exist
				newdata = data[~data['name'].isin(prenamelist)]
				
				newdata.to_csv('formattedUL.csv', index=False, header=False)

				#Delete any pres found as we are essentially going to update them
				if len(pres) is not 0:
					for pre in pres:
						db.delete(pre)
				db.commit()

			#Process the now clean CSV
			conn = engine.raw_connection()
			cur = conn.cursor()		
			formattedUL = open('formattedUL.csv')	

			try:
				print("Pre-Import: Attempting to add {} to the database".format(processingFile['lastfile']))
				cur.copy_expert("COPY pres (name,filename,nuked,category,pretime,source,requestid,requestgroup) FROM STDIN WITH CSV", formattedUL)
				conn.commit()
			except Exception as e:
				print("Pre-Import: Error inserting into database - {}".format(e))
				insertFails.append(processingFile['lastfile'])	
			

			#Write out the last pre csv name so it can be restarted later without downloading all the pres.
			with open('lastfile.json', 'w') as outfile:
				json.dump({'lastfile' : int(processingFile['lastfile'])}, outfile)
	

		else:
			pass


	if insertFails is not None:
		print("Failures: {}".format(insertFails))

processNzedbPre()
