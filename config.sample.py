import logging

site = {
    # general site settings
    # ---------------------

    # title: shows on the rss feed, can be whatever
    'title': 'pynab',

    # description: same deal
    'description': 'a pynab api',

    # don't edit this
    'version': '0.1',

    # generally leave this alone too
    'api_version': '0.1',

    # your administrator email (shows on rss feed)
    'email': '@gmail.com',

    # api settings
    # ------------

    # result_limit: maximum search results for rss feeds
    # make sure there's no quotes around it
    'result_limit': 100,

    # result_default: default number if none is specified
    # make sure there's no quotes around it
    'result_default': 20,

    # scanning settings
    # -----------------

    # update_threads: number of processes to spawn for updating
    # realistically, should be the number of cpu cores you have
    # make sure there's no quotes around it
    'update_threads': 4,

    # update_wait: amount of time to wait between update cycles
    # in seconds
    'update_wait': 300,

    # new_group_scan_days: how many days to scan for a new group
    # make sure there's no quotes around it
    'new_group_scan_days': 5,

    # message_scan_limit: number of messages to take from nntp server at once
    # make sure there's no quotes around it
    'message_scan_limit': 20000,

    # backfill_days: number of days to backfill groups (using backfill)
    # make sure there's no quotes around it
    'backfill_days': 10,

    # logging settings
    # ----------------
    # logging_file: a filepath or None to go to stdout
    'logging_file': None,

    # logging.x where DEBUG, INFO, WARNING, ERROR, etc
    # generally, debug if something goes wrong, info for normal usage
    'logging_level': logging.DEBUG,

    # regex update settings
    # ---------------------

    # regex_url: url to retrieve regex updates from
    # this can be newznab's if you bought plus, include your id, ie.
    # expects data in newznab sql dump format
    # 'http://www.newznab.com/getregex.php?newznabID=<id>'
    'regex_url': '',

    # blacklist_url: url to retrieve blacklists from
    # generally leave alone
    'blacklist_url': 'https://raw.github.com/kevinlekiller/Newznab-Blacklist/master/New/blacklists.txt',


}

# mongodb config
db = {
    # hostname: usually 'localhost'
    'host': 'localhost',

    # port: default is 27017
    # make sure there's no quotes around it
    'port': 27017,

    # user: username, if auth is enabled
    'user': '',

    # pass: password, likewise
    'pass': '',

    # db: database name in mongo
    # pick whatever you want, it'll autocreate it
    'db': 'pynab',
}

# usenet server details
news = {
    # host: your usenet server host ('news.supernews.com' or the like)
    'host': '',

    # user: whatever your login name is
    'user': '',

    # password: your password
    'password': '',

    # port: port that your news server runs on
    # make sure there aren't any quotes around it
    'port': 443,

    # ssl: True if you want to use SSL, False if not
    'ssl': True,
}

# only used for convert_from_newznab.py
# you can probably leave this blank unless you know what you're doing
mysql = {
    'host': 'localhost',
    'port': 3306,
    'user': 'remote',
    'passwd': '',
    'db': 'newznab',
}