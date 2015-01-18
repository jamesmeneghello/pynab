#title 1, nfo, size, files, filename 9, nuked 11, nukereason, category 15 , predate 17, source 19, requestid 21, groupname 23
#name,filename,nuked,category,pretime,source,requestid,groupname

import os
from os import listdir
import sys
from pynab.db import db_session, engine

#for x in os.listdir("."):
#	if x.endswith("csv"):
#		print(x)

#os.system('csvcut -c 1,9,15,17,19,21,23 bla.csv > test.csv')

os.system("csvcut -t -q 3 -c 1,9,11,15,17,19,21,23 1404152742_predb_dump.csv.gz > bla.csv")

#with db_session as db:
#conn = engine.raw_connection()
#os.system('csvsql --db {} --table fy09 --insert bla.csv'.format(conn))
#COPY ratings FROM '/path/blah.csv' DELIMITER ',' CSV;



#States are Nuked 1, Unnuked 2, Modnuked 3, Renuked 4, Oldnuked 5
#This is a pain..
os.system('sed -i s/"\'"/""/g {}'.format("bla.csv"))
os.system('sed -i s/,2,/,0,/g {}'.format("bla.csv"))
os.system('sed -i s/,3,/,0,/g {}'.format("bla.csv"))
os.system('sed -i s/,4,/,0,/g {}'.format("bla.csv"))
os.system('sed -i s/,5,/,0,/g {}'.format("bla.csv"))

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
if __name__ == '__main__':
    argparser = argparse.ArgumentParser(description="Pynab prebot")
    argparser.add_argument('-d', '--daemonize', action='store_true', help='run as a daemon')
    argparser.add_argument('-p', '--pid-file', help='pid file (when -d)')

    args = argparser.parse_args()
    if args.daemonize:
        pidfile = args.pid_file or config.scan.get('pid_file')
        if not pidfile:
            log.error("A pid file is required to run as a daemon, please supply one either in the config file '{}' or as argument".format(config.__file__))
        else:
            daemonize(pidfile)
    else:
        main()
'''