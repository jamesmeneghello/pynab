NOTE
====

Any time you pull master and it updates, re-copy the sample config and put your details in.

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
Something like 99.9% of the usage of my old Newznab server was API-only
for Sickbeard, Couchpotato, Headphones etc - so it's low-priority.

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

- Collates binaries at a part-level rather than segment
  - No more tables of 80,000,000 parts that take 40 years to process and several centuries to delete
  - Smaller DB size, since there's no overhead of storing 80,000,000 parts (more like 200-300k)
  - We can afford to keep binaries for much longer (clear them out once a week or so)
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
  - More to come, features before optimisation


Instructions
============

Installation and execution is reasonably easy.

Requirements
------------

- Python 3.3 or higher (might work on 3.2)
- PostgreSQL 9.3 or higher
- A u/WSGI-capable webserver (or use CherryPy)

I've tested the software on both Ubuntu Server 13.04 and Windows 8, so both should work.

Installation
------------

### Ubuntu 12.04 and earlier ###

Follow the instructions by broknbottle in [Issue #15](https://github.com/Murodese/pynab/issues/15) to install Python 3.3.x, then follow the 13.04 instructions.

### Ubuntu 13.04/13.10 ###

Install PostgreSQL 9.3, as per instructions [here](https://wiki.postgresql.org/wiki/Apt).

You also need to install Python 3.3, associated packages and pip3:

    sudo apt-get install python3 python3-setuptools python3-pip

### Universal ###

    > cd /var/www/
    > sudo git clone https://github.com/Murodese/pynab.git
    > cd pynab
    > sudo cp config.sample.py config.py
    > sudo vim config.py [fill in details as appropriate]
    > sudo pip3 install -r requirements.txt
    > sudo python3 install.py [follow instructions]
    > sudo chown -R www-data:www-data /var/www/pynab

If you receive an error message related to an old version of distribute while running pip3, you can
install the new version by typing:

    sudo easy_install -U distribute

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
any regexes, blacklists, categories and TVRage/IMDB/TVDB data, as well as user details
and current API keys. This means that your users should only experience downtime for a
short period, and don't have to regenerate their API keys. Hate your users? No problem,
they won't even notice the difference and you don't even have to tell them.

To convert from a Newznab installation, you should first enter the details of your MySQL
installation into config.py, and read the comment at the top of scripts/convert_from_newznab.py.
You may need to delete duplicate data in certain tables before running a conversion.

If you want to keep certain collections (maybe your Newznab TVRage table is much smaller than
the one supplied by this repo?), you can comment the function calls out at the bottom of the
script.

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

Allow this to finish before starting normal operation.

Operation
=========

### Start Indexing ###

At this point you should manually activate groups to index, and blacklists.
To kick you off, they look something like this:

    > mongo -u <user> -p <pass>
    # use pynab [or db name specified in config.py]
    # db.groups.update({name:'alt.binaries.teevee'},{$set:{'active': 1}}) [this will activate a.b.teevee]

You can also just use http://www.robomongo.org/, which makes managing it a lot easier.

Once desired groups have been activated and new_group_scan_days and backfill_days have been
set in config.py:

    > python3 start.py

start.py is your update script - it'll take care of indexing messages, collating binaries and
creating releases.

### Post-processing Releases ###

Some APIs (sometimes Sickbeard, usually Couchpotato) rely on some post-processed metadata
to be able to easily find releases. Sickbeard looks for TVRage IDs, CouchPotato for IMDB IDs,
for instance. These don't come from Usenet - we match them against online databases.

To run the post-process script, do this:

    > python3 postprocess.py

This will run a quick once-over of all releases to match to available local data, then a slow
process of pulling individual articles off Usenet for NFOs, RARs and other data. Finally, it'll
rename any shitty releases in Misc-Other and Ebooks, optionally deleting any releases it can't
fix after that (NB: won't do this until I'm satisfied it's safe).

Note that SB/CP will have trouble finding some stuff until it's been post-processed - Sickbeard
will usually search by name as well, but CP tends not to do so, so keep your releases post-processed.

### Backfilling Groups ###

Pynab has a backfill mechanism very similar to Newznab. This can be run sequentially to start.py,
so that you effectively fill releases in both directions. Because binary and release processing
is atomic, there are no issues running multiple scripts at the same time - you are effectively
only limited by the number of available NNTP connections, your bandwidth and your available 
processing power.

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

### Starting the API ###

To activate the API:

    > python3 api.py

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
        root /var/www/pynab;

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
    chdir = /var/www/pynab
    wsgi-file = api.py
    uid = www-data
    gid = www-data
    processes = 4 [or whatever number of cpu cores you have]
    threads = 2

### Using the miscellaneous scripts ###

To create a user (will return a generated API key):

	> python3 scripts/create_user.py <email>

To update indexes (generally only run if a commit message tells you to):

	> python3 scripts/ensure_indexes.py 

Update regex (run it every now and then, but it doesn't update that often):

    > python3 scripts/update_regex.py

Quickly match releases to local post-processing databases (run this pretty often, 
it'll probably be incorporated into start.py at some point):

	> python3 scripts/quick_postprocess.py

Categorise all uncategorised releases - this runs automatically after import.

	> python3 scripts/process_uncategorised.py


### Building the WebUI ###

Requires NPM and probably a few other things (post an issue if you're missing stuff):

    > sudo apt-get install npm

To build the webui from source, first modify the config to include your indexer host:

    > cd webui/app/scripts
    > vim config.js
    > [add host url and port]

Then initiate the build:

    > cd webui
    > npm install
    > bower install
    > grunt build

This will build a working and optimised version of the UI into the dist/ directory, which
will then be hosted by your webserver as part of api.py. Note that you can disable the web
interface in the main configuration.

F.A.Q.
======

- I keep getting errors related to "config.<something>" and start.py stops.

This means that your config.py is out of date. Re-copy config.sample.py and re-enter your details.
Generally speaking this should become less of a problem as time goes on - only new features require new
config options, and the project is mostly in bugfix mode at the moment.

- I get an error "cannot import regex" or something similar!

Re-run `pip3 install -r requirements.txt`. You're missing some libraries that we use.

- Start.py keeps failing with some kind of EOFError or just some random error.

Python's Multiprocessing Pool is such that any error will tend to flip it out and kill all the workers,
so combined with NNTP implementations' rather.. "free" usage of error messages and standards, this'll
happen for a while until I catch all the weird bugs. Found a new, weird crash? Post an issue!

Most of these got cleaned up in a recent revision, but there's still the potential for broken servers
to return bad data.

- I'm getting some random error while trying to fill groups

Go into config.py and set logging_level to logging.DEBUG and logging_file to something appropriate,
then upload the log somewhere and attach it to an issue.

- How do I enable header compression?

You don't - it's automatically enabled if your provider supports it. The benefits of using it are so 
large time-wise that there's no real reason to include a config option to turn it off. If you can think
of a reason to include it, post an issue and let me know.

- When attempting to start the API using Nginx or something similar, I just get internal server errors?

Check uWSGI's logs. Most likely your logfiles are going somewhere that you don't have permission to write to.

- After updating from Git, the webui won't build, citing bower-install errors.

Delete the webui/node_modules and webui/app/bower_components folder and re-run npm install / bower install.

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
