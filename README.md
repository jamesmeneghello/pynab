pynab
=====

Pynab is a rewrite of Newznab, using Python and MongoDB. Complexity is way down,
consisting of (currently) ~4,600 SLoC, compared to Newznab's ~104,000 lines of
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

Note that because this is purely for API access, THERE IS NO WEB FRONTEND. You
cannot add users through a web interface, manage releases, etc. There isn't a
frontend. Again, if you'd like to add one, feel free - something like 99.9%
of the usage of my old Newznab server was API-only for Sickbeard, Couchpotato,
Headphones etc - so it's low-priority.


Features
--------

- Group indexing
- Mostly-accurate release generation (thanks to Newznab's regex collection)
- Also mostly-accurate release categorisation (which is easily extensible)
- Binary blacklisting (regex thanks to kevinlekiller)
- High performance
- Developed around pure API usage
- Newznab-API compatible (mostly, see below)

In development:
---------------

- Postprocessing (and thereby tv/m-search)
- Console management (for users, etc - robomongo?)


Technical Differences to Newznab
================================

- Uses a document-based storage engine rather than a relational storage engine like MySQL
  - Adherence to schema isn't strict, so migrations are easy
  - Once releases are built, only one query is required to retrieve all related information (no gigantic joins)
  - Significantly faster than MySQL
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
- General optimisations
  - Several operations have been much-streamlined to prevent wasteful, un-necessary regex processing
  - No language wars, but Python is generally quicker than PHP (and will be moreso when PyPy supports 3.3)
  - More to come, features before optimisation


Instructions
============

Installation and execution is reasonably easy.

Requirements
------------

- Python 3.3 or higher
- MongoDB 2.4.x or higher
- A u/WSGI-capable webserver (or use CherryPy)

I've tested the software on both Ubuntu Server 13.04 and Windows 8, so both should work.

Installation
------------

### Ubuntu ###

Install mongodb-10gen by following the instructions here:
http://docs.mongodb.org/manual/tutorial/install-mongodb-on-ubuntu/
For all other server operating systems, follow the instructions provided by MongoDB.

Text-Search must be enabled. Follow:
http://docs.mongodb.org/manual/tutorial/enable-text-search/
Note that you can also edit mongodb.conf to include:

    setParameter = textSearchEnabled=true

You also need to install Python 3.3, associated packages and pip3:

    sudo apt-get install python3 python3-setuptools

### Universal ###

    > cd /var/www/
    > sudo git clone https://github.com/Murodese/pynab.git
    > cd pynab
    > sudo cp config.sample.py config.py
    > sudo vim config.py [fill in details as appropriate]
    > sudo pip3 install -r requirements.txt
    > sudo python3 install.py [follow instructions]
    > sudo chown -R www-data:www-data /var/www/pynab

The installation script will automatically import necessary data and download the latest regex and blacklists.

Please note that in order to download updated regexes from the Newznab crew, you'll need a NN+ ID.
You can get one by following the instructions on their website (generally a donation).
You can also import a regex dump or create your own.

### Converting from Newznab ###

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

### Starting the API ###

To activate the API:

    > python3 api.py

Starting the api.py script will put up a very basic web server, without threading/pooling
capability.

If you plan on using the API for extended periods of time or have more than one user access it,
please use a proper webserver.

The API is built on bottle.py, who provide helpful details on deployment: http://bottlepy.org/docs/dev/deployment.html

As an example, to run pynab on nginx/uwsgi, you need these packages:

    > sudo apt-get install uwsgi uwsgi-plugin-python3

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
    plugins = python3
    chdir = /var/www/pynab
    wsgi-file = api.py
    uid = www-data
    gid = www-data
    enable-threads = true


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
