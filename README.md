pynab
=====

Pynab is a rewrite of Newznab, using Python and PostgreSQL. Complexity is way down,
consisting of (currently) ~4,000 SLoC, compared to Newznab's ~104,000 lines of
php/template. Performance and reliability are significantly improved, as is
maintainability and a noted reduction in the sheer terror I experienced upon
looking at some of the NN code in an attempt to fix a few annoying bugs.

This project was written almost entirely for my own amusement and use, so it's
specifically tailored towards what I was looking for in an indexer - fast,
compatible API with few user restrictions and low complexity. I literally just
use my indexer to index groups and pass access to my friends, so there's no API
limits or the like. If you'd like to use this software and want to add such
functionality, please feel free to fork it! I won't have time to work on it
beyond my own needs, but this is what open source is for.

Note that because this is purely for API access, the WebUI is very simple. You
cannot add users through a web interface, manage releases, etc. 
Something like 99.9% of the usage of my old Newznab server was API-only,
so it's low-priority.

API Compatibility
-----------------

- [Sickbeard](http://sickbeard.com) and branches
- [NZBDrone](http://nzbdrone.com)
- [CouchPotato](http://couchpota.to)
- [Headphones](https://github.com/rembo10/headphones) (only slightly tested)
- [NZB360](http://nzb360.com/)
- [NZBSearcher](https://play.google.com/store/apps/details?id=nl.giejay.nzbsearcher.trial&hl=en)

Features
--------

- Group indexing
- Mostly-accurate release generation (thanks to Newznab's regex collection)
- Also mostly-accurate release categorisation (which is easily extensible)
- Binary blacklisting (regex thanks to kevinlekiller)
- High performance
- Developed around pure API usage
- Newznab-API compatible (mostly, see below)
- TVRage/IMDB/Password post-processing

In development:
---------------

- Release renaming for obfuscated releases (works for misc/books, breaks other stuff)
- Pre-DB comparisons maybe?


Technical Differences to Newznab
================================

- NZBs are imported whole
  - Bulk imports of 50gb of nzb.gzs now take hours to process, not weeks
  - No more importing in batches of 100 - just point it at a directory of 600,000 NZBs and let it process
  - Relies on provided NZBs being complete and mostly good, though
- NZBs are stored in the DB
  - Commonly-grabbed NZBs are generally cached in RAM
  - Big IO savings
  - Generally quicker than off the HDD
  - You don't run into filesystem problems from having 2.5 million files in a few directories
- Very simple query interface
  - The vast majority of access to my indexer was API-based (1-5 web hits per month vs 50,000+ api hits)
  - It's not a replacement for Newznab if you have a lot of direct user interaction
- Simplified authentication
  - No more usernames, passwords, or anything, really.
  - API key access required for everything - sure, it can be sniffed very easily, but it always could be. Worst that can happen: someone uses the API.
- General optimisations
  - Several operations have been much-streamlined to prevent wasteful, un-necessary regex processing
  - No language wars, but Python is generally quicker than PHP (and will be moreso when PyPy supports 3.3)
  - General (significant) database speed improvements


Instructions
============

Installation and execution is reasonably easy.

Requirements
------------

- Python 3.2 or higher
- PostgreSQL 9.3 or higher
- A u/WSGI-capable webserver (or use CherryPy)

I've tested the software on both Ubuntu Server 13.04 and Windows 8, so both should work.

Installation
------------

### Ubuntu 12.04 and earlier ###

Follow the instructions by broknbottle in [Issue #15](https://github.com/Murodese/pynab/issues/15) to install Python 3.3.x, then follow the 13.04 instructions.

### Ubuntu 13.04/13.10 ###

Install PostgreSQL 9.3, as per instructions [here](https://wiki.postgresql.org/wiki/Apt).

You also need to install Python 3.3/3.4, associated packages and pip3:

    > sudo apt-get install python3 python3-setuptools python3-pip libxml2-dev libxslt-dev libyaml-dev

And a few packages required by psycopg2:

    > sudo apt-get install postgresql-server-dev-9.3

### General *nix ###

    > cd /opt/
    > sudo git clone https://github.com/Murodese/pynab.git
    > sudo chown -R www-data:www-data pynab
    > cd pynab
    > sudo cp config.sample.py config.py
    > sudo vim config.py [fill in details as appropriate]
    > sudo pip3 install -r requirements.txt

If you receive an error message related to an old version of distribute while running pip3, you can
install the new version by typing:

    sudo easy_install -U distribute

### Windows ###

Running pynab on Windows is possible, but not recommended or well-supported. Lack of screen support
 means that console output is tricky, so using logfiles is very much recommended.

Clone and configure:

    > [browse to desired directory]
    > git clone https://github.com/Murodese/pynab.git
    > [browse to pynab]
    > [copy config.sample.py to config.py]
    > [fill in config as appropriate, ensuring to set logfile]

Install pre-reqs. The following packages are available as Windows binaries from [here](http://www.lfd.uci.edu/~gohlke/pythonlibs/#lxml).
Select the appropriate package for your version of python (ie. py34 for 3.4, etc):

    - lxml
    - sqlalchemy
    - psycopg2

Two packages used in pynab require a compiler, such as [MinGW](http://www.mingw.org/). This may also require
 you to modify some config vars to make pip see the compiler, see [here](http://stackoverflow.com/questions/2817869/error-unable-to-find-vcvarsall-bat/2838827#2838827).

Once the compiler has been installed:

    > pip install -r requirements.txt

### Install/Migrate ###

New installation? As below:

    > sudo python3 install.py [follow instructions]

Migrating from Newznab? Go here: [Converting from Newznab](#converting-from-newznab)

Migrating from pynab-mongo? Go here: [Converting from pynab-mongo](#converting-from-pynab-mongo)

Once done:

    > sudo chown -R www-data:www-data /opt/pynab

The installation script will automatically import necessary data and download the latest regex and blacklists.

Please note that in order to download updated regexes from the Newznab crew, you'll need a NN+ ID.
You can get one by following the instructions on their website (generally a donation).
You can also import a regex dump or create your own.

### Converting from Newznab ###

	WARNING:

    This software is unstable as yet, so keep backups of everything - if you're importing NZBs,
    make sure you make a copy of them first. The import script will actively delete
    things, newznab conversion will just copy - but better to be safe.

Pynab can transfer some data across from Newznab - notably your groups (and settings),
any regexes, blacklists, categories and TVRage/IMDB data, as well as user details
and current API keys. This means that your users should only experience downtime for a
short period, and don't have to regenerate their API keys. Hate your users? No problem,
they won't even notice the difference and you don't even have to tell them.

To convert from a Newznab installation, you should first enter the details of your MySQL
installation into config.py, and read the comment at the top of scripts/convert_from_newznab.py.
You may need to delete duplicate data in certain tables before running a conversion.

To run the conversion, first follow the normal installation instructions. Then:

    > python3 scripts/convert_from_newznab.py

This will copy over relevant data from your Newznab installation. Because Pynab's method of
storing NZBs and metadata is very different to Newznab, we can't do a direct releases table
conversion - you need to import the NZBs en-masse. Luckily, this is no longer an incredibly
lengthy process - it should only take a few hours to process several hundred thousand NZBs
on a reasonable server. Importing 2.5 million releases from my old installation took 11 hours.

To import said NZBs:

    > python3 scripts/import.py /path/to/nzbs

For most Newznab installations, it'll look like this:

    > python3 scripts/import.py /var/www/newznab/nzbfiles

:warning: Run this script against a copy of the nzb folder, since it automatically deletes NZBS
that were successfully imported.

Allow this to finish before starting normal operation.

### Converting from pynab-mongo ###

If you were using pynab-mongo and want to convert your database to the Postgre version,
there's a script supplied. It's recommended that you side-load the Postgre branch, rather
than cut over directly:

    # don't bother running install.py first, as we're copying everything from mongo
    # you will, of course, need postgres installed
    > cd /opt
    > git clone https://github.com/Murodese/pynab.git pynab-postgres
    > cd /opt/pynab-postgres
    > git checkout development-postgres
    > cp config.sample.py config.py
    > [edit config.py to add mongo and postgres config]
    > python3 scripts/convert_mongo_to_postgre.py

The script handles virtually everything, copying all necessary data. For large installations,
this could take some time - there's no quick way to copy that data across. That said, it's not
too excessive - for 500k releases, somewhere between 15 minutes to an hour depending on server
specs. The migration script is unable to handle existing release file data and will need to
re-retrieve it.

Once this is complete, rename the old folder and replace it with the new, then shut down mongo:

    > sudo service nginx stop # or whatever you're using
    > mv /opt/pynab /opt/pynab.old
    > mv /opt/pynab-postgres /opt/pynab
    > sudo service nginx start
    > sudo service mongo stop

You can also optimise your postgres config to use available memory with something like pgTune:
https://github.com/gregs1104/pgtune

Execution of the indexer works identically to the mongo version - just run start.py and
postprocess.py.

### Installing Upstart Scripts ###

Pynab comes with an upstart script that can be used to handle automatic startups. To install it:

    > vim init/pynab.conf
    > [edit home, logdir as necessary]
    > sudo cp init/pynab.conf /etc/init

This will, by default, run the pynab scan and postprocess daemons automatically on system boot. You
can also manually control parts of pynab, as seen below.

Operation
=========

Pynab comes with a CLI program that can make administration somewhat easier. Common usage is listed below.

### Enabling Groups ###

After installation, you should enable groups to be scanned. Pynab comes pre-installed with several
groups, but none enabled by default. To enable a group:

    > python3 pynab.py group enable <group name>

For example, to enable alt.binaries.linux:

    > python3 pynab.py group enable alt.binaries.linux

### Adding Users ###

For users to access your API, they need an API key. To add a user:

    > python3 pynab.py user create <email>

This will supply you with an API key for the user. You can also delete a user:

    > python3 pynab.py user delete <email>

### Running Pynab ###

The pynab CLI handles execution of daemons and respawning of processes. There are two primary 
parts of pynab: scanning and post-processing. Scanning indexes usenet posts and builds releases,
while post-processing enriches releases with metadata useful for the API. This metadata includes
TVRage IDs, IMDB IDs, whether a release is passworded, release size, etc.

Before running pynab, you should ensure that you've read and edited config.py (copied from 
config.sample.py). If log directories are set to unwritable locations, pynab will not run.

The simplest way of starting pynab is:

    > python3 pynab.py start

Or, if you've installed the Upstart script:

    > sudo start pynab

This will execute both the scanning and post-processing components of pynab. If you're using Windows,
this will also execute the API - if you're using a nix OS, you should read down to the section on 
using uWSGI to operate the API.

These components can also be started individually:

    > python3 pynab.py scan
    > python3 pynab.py postprocess
    > python3 pynab.py api

To stop pynab, you can use:

    > python3 pynab.py stop

Or, again, if using Upstart:

    > sudo stop pynab

### Monitoring Pynab ###

You can optionally use a teamocil layout to set up a window for monitoring (that will show scan/postproc
progress). 

If you want to use the monitor, you'll need some other packages:

    > sudo apt-get install tmux

Including Ruby 2.0 so that we can install teamocil...

    > \curl -L https://get.rvm.io | bash -s stable --ruby
    > rvm install ruby --latest
    > rvm list [find the 2.0.x version]
    > rvm use ruby-<version>
    > gem install teamocil

To run the monitor:

    > ./monitor.sh

This will spawn a new tmux session, load the Teamocil layout and then attach to tmux.

Teamocil layouts are in `teamocil/` and can be modified or added as desired (just change monitor.sh).
If you create a good layout, submit a pull request! :)

### Backfilling Groups ###

Pynab has a backfill mechanism very similar to Newznab. This can be run sequentially to start.py,
so that you effectively fill releases in both directions. Because binary and release processing
is atomic, there are no issues running multiple scripts at the same time - you are effectively
only limited by the number of available NNTP connections, your bandwidth and your available 
processing power.

Before starting a backfill, you need to change the dead_binary_age config option in config.py.
If backfilling, set it to 0 - otherwise, leave it on 1-3. This will delete binaries that haven't
been turned into releases after they're x days old (from time of posting, not time of collection).
As such, you don't want to delete backfilled binaries.

    > nano config.py [change dead_binary_age to 0]

You can use the backfill scripts as so:

	> python3 scripts/backfill.py -g <group> -d <date>

You can optionally specify a group - omitting the group argument will operate a backfill over all
groups. You can also optionally specify a particular date to backfill to - omitting a date will fall
back onto your config.py's backfill_days parameter.

Note that you can combine the backfill script with Screen to backfill multiple groups at once, like so:

	> screen /bin/bash
	> python3 scripts/backfill.py -g alt.binaries.somegroup
	> (press ctrl-a then d)
	> screen /bin/bash
	> python3 scripts/backfill.py -g alt.binaries.someothergroup
	> (press ctrl-a then d)
	> screen /bin/bash
	> python3 start.py
	> (press ctrl-a then d)
	> screen /bin/bash
	> python3 post_process.py
	> (press ctrl-a then d)
	> tail -f pynab.log

The last line will enable you to see output from all the windows, if logging_file is enabled.
This is pretty spammy and unreadable, though. Watchdog to come with summarised stats for the DB.

By running start.py at the same time as the backfill scripts, start.py will automatically take care of 
processing parts created by the backfill scripts at regular intervals, preventing the parts table from
becoming extremely large.

### Updating Pynab ###

Run the following to update to the latest version:

    > python3 pynab.py update

Requires that alembic is installed and in your path (as well as git).

### Starting the API ###

To activate the API:

    > python3 pynab.py api

Starting the api.py script will put up a very basic web server, without threading/pooling
capability.

If you plan on using the API for extended periods of time or have more than one user access it,
please use a proper webserver.

The API is built on bottle.py, who provide helpful details on deployment: http://bottlepy.org/docs/dev/deployment.html

As an example, to run pynab on nginx/uwsgi, you need this package:

    > sudo apt-get install uwsgi

However, Ubuntu/Debian repos have an incredibly old version of uWSGI available, so install the new one.
Note that this must be pip3 and not pip, otherwise you'll install the uWSGI Python 2.7 module:

    > sudo pip3 install uwsgi
    > sudo ln -fs /usr/local/bin/uwsgi /usr/bin/uwsgi

Your /etc/nginx/sites-enabled/pynab file should look like this:

    upstream _pynab {
        server unix:/var/run/uwsgi/app/pynab/socket;
    }

    server {
        listen 80;
        server_name some.domain.name.or.ip;

        location / {
            try_files $uri @uwsgi;
        }

        location @uwsgi {
            include uwsgi_params;
            uwsgi_pass _pynab;
        }
    }

While your /etc/uwsgi/apps-enabled/pynab.ini should look like this:

    [uwsgi]
    socket = /var/run/uwsgi/app/pynab/socket
    master = true
    chdir = /opt/pynab
    wsgi-file = api.py
    uid = www-data
    gid = www-data
    processes = 4 [or whatever number of cpu cores you have]
    threads = 2

### Using the miscellaneous scripts ###

Update regex (run it every now and then, but it doesn't update that often):

    > python3 scripts/update_regex.py

Categorise all uncategorised releases - this runs automatically after import.

    > python3 scripts/process_uncategorised.py
    
Fill sizes from NZBs - this should only be used if you were running an old version of pynab 
(pre-aug-2014).

    > python3 scripts/fill_sizes_from_nzb.py

Quick post-process - this quickly runs an offline post-process of files for imdb/tvrage data.
This automatically gets called at the start of postprocess.py execution and should only be used
if you've imported a large dump of imdb/tvrage data or something similar.

    > python3 scripts/quick_postprocess.py

Recategorise everything - as it says. Wipes clean the category slate for all releases and checks them anew.
Run if there have been major changes to category regex or lots of stuff broke.

    > python3 scripts/recategorise_everything.py

Rename bad releases - automatically run as part of the post-process process (process [process]).
CLI script that can take badly-named releases and attempt to rename them from nfo, sfv, par or rar.
Don't run on normal groups, just ebooks and misc.

    > python3 scripts/rename_bad_releases.py


### Building the WebUI ###

Requires NPM and probably a few other things. You can install nodejs, NPM, grunt and bower
however you like. Ubuntu's repositories sometimes have an issue with node, however. Order
of installation is important.

Note that using NPM 2.0.0 can break everything, 1.3.10~ should be used (which is the default
in Ubuntu's repos). Installing things in the wrong order can break everything. Installing
grunt/bower from aptitude can break everything, and using sudo in the wrong place can break
everything. If you're having trouble with permissions and package errors, try running
`rm -rf node_modules`, `npm cache clear`, `rm -rf ~/.npm` before removing/reinstalling
NPM 1.3.10 and any node.js packages that came from aptitude.

A semi-reliable way to install the required packages is below (be careful of sudo use):

    > sudo apt-get install npm nodejs-legacy ruby ruby-compass

Run the npm install:

    > cd webui
    > npm install [not using sudo]

Install necessary build tools (using sudo):

    > sudo npm install -g grunt-cli
    > sudo npm install -g bower

To build the webui from source, first modify the config to include your indexer host:

    > cd webui/app/scripts
    > vim config.js
    > [add host url and port]

Then initiate the build:

    > bower install
    > grunt build

This will build a working and optimised version of the UI into the dist/ directory, which
will then be hosted by your webserver as part of api.py. Note that you can disable the web
interface in the main configuration.

F.A.Q.
======

- I keep getting errors related to "config.<something>" and start.py stops.
- e.g. AttributeError: 'module' object has no attribute 'monitor'

This means that your config.py is out of date. Re-copy config.sample.py and re-enter your details.
Generally speaking this should become less of a problem as time goes on - only new features require new
config options, and the project is mostly in bugfix mode at the moment.

- I get an error "cannot import regex" or something similar!

Re-run `pip3 install -r requirements.txt`. You're missing some libraries that we use.

- How do I enable header compression?

You don't - it's automatically enabled if your provider supports it. The benefits of using it are so 
large time-wise that there's no real reason to include a config option to turn it off. If you can think
of a reason to include it, post an issue and let me know.

- When attempting to start the API using Nginx or something similar, I just get internal server errors?

Check uWSGI's logs. Most likely your logfiles are going somewhere that you don't have permission to write to.

- After updating from Git, the webui won't build, citing bower-install errors.

Delete the webui/node_modules and webui/app/bower_components folder and re-run npm install / bower install.

- A whole lot of releases are getting miscategorised!

There was a bug in a particular version of the python regex module that could cause release and binary
regex to give incredibly shitty results. This is forced to a correct version in requirements.txt, so just
run `pip3 install --upgrade regex` if it's happening.

- While building the WebUI, I get errors about compass.

Run the following:

    > gem uninstall sass
    > gem install sass --no-ri --no-rdoc
    > gem install compass --no-ri --no-rdoc 

- Upstart has broken horribly, and `sudo start pynab` or `sudo stop pynab` just hang and do nothing until I reboot.

Particularly annoying, this bug, which is an upstart bug. You should see some output like this:

    > sudo initctl status pynab
    > pynab stop/killed, process 994 (or some other pid)

Do this:

    > cd ~
    > wget https://raw.githubusercontent.com/ion1/workaround-upstart-snafu/master/workaround-upstart-snafu
    > chmod +x workaround-upstart-snafu
    > ./workaround-upstart-snafu 994 (whatever pid was listed above)
    
Let it run. Rebooting also solves this.


Newznab API
===========

Generally speaking, most of the relevant API functionality is implemented,
with noted exceptions:

- REGISTER (since it's controlled by server console)
- CART-ADD (there is no cart)
- CART-DEL (likewise)
- COMMENTS (no comments)
- COMMENTS-ADD (...)
- USER (not yet implemented, since API access is currently unlimited)


Acknowledgements
================

- The Newznab team, for creating a great piece of software
- Everyone who contributed to the NN+ regex collection
- Kevinlekiller, for his blacklist regex
- Everyone who's sent in issues and tested the software
