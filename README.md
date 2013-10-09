pynab
=====

Pynab is a rewrite of Newznab, using Python and MongoDB. Complexity is way down,
consisting of (currently) ~2,400 SLoC, compared to Newznab's ~104,000 lines of
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

It's also unfinished as yet, since I haven't even written the update scripts yet.
They're mostly just tests.

Features
--------

- Group indexing
- Mostly-accurate release generation (thanks to Newznab's regex collection)
- High performance
- Developed around pure API usage
- Newznab-API compatible (mostly, see below)

In development:
---------------

- Update scripts (heh)
- Postprocessing (and thereby tv/m-search)
- Console management (for users, etc - use mongo currently)
- Some minor extra features
- User authentication

Instructions
============

Installation and execution is reasonably easy.

Requirements
------------

- Python 3.3 or higher
- A WSGI-capable webserver (or use CherryPy)

Installation
------------

git clone https://github.com/Murodese/pynab.git
cd pynab
sudo pip3 install -r requirements.txt

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