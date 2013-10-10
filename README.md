pynab
=====

Pynab is a rewrite of Newznab, using Python and MongoDB. Complexity is way down,
consisting of (currently) ~3,200 SLoC, compared to Newznab's ~104,000 lines of
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

It's also unfinished as yet. Update scripts are written and working, but control
of the indexer is tricky as yet until a command console is written (unless you
use robomongo or similar). Post-processing is also not completed.

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

    > git clone https://github.com/Murodese/pynab.git
    > cd pynab
    > cp config.sample.py config.py
    > vim config.py [fill in details as appropriate]
    > sudo pip3 install -r requirements.txt
    > python3 install.py [follow instructions]

The installation script will automatically import necessary data and download the latest regex and blacklists.
At this point you should manually activate groups to index, and blacklists.
To kick you off, they look something like this:

    > mongo -u <user> -p <pass>
    # use pynab [or db name specified in config.py]
    # db.groups.update({name:'alt.binaries.teevee'},{$set:{'active': 1}}) [this will activate a.b.teevee]

Once desired groups have been activated and new_group_scan_days and backfill_days have been
set in config.py:

    > python3 start.py

start.py is your update script - it'll take care of indexing messages, collating binaries and
creating releases.

To activate the API:

    > python3 api.py

Starting the api.py script will put up a very basic web server, without threading/pooling
capability.

If you plan on using the API for extended periods of time or have more than one user access it,
please use a proper webserver.

The API is built on bottle.py, who provide helpful details on deployment: http://bottlepy.org/docs/dev/deployment.html

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
