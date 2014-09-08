import logging

api = {
    # api settings
    # ---------------------

    # title: shows on the rss feed, can be whatever
    'title': 'pynab',

    # description: same deal
    'description': 'a pynab api',

    # don't edit this
    'version': '1.0.0',

    # generally leave this alone too
    'api_version': '0.2.3',

    # your administrator email (shows on rss feed)
    'email': '',

    # enable web interface
    'webui': True,

    # result_limit: maximum search results for rss feeds
    # make sure there's no quotes around it
    'result_limit': 100,

    # result_default: default number if none is specified
    # make sure there's no quotes around it
    'result_default': 20,
    
    # api_host: ip or hostname to bind the api
    # usually '0.0.0.0'
    'api_host': '0.0.0.0',

    # api_port: port number to bind the api
    # usually 8080
    'api_port': 8080,

    # pid_file: process file for the api, if daemonized
    # make sure it's writable, leave blank for nginx
    'pid_file': ''
}

scan = {
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

    # dead_binary_age: number of days to keep binaries for matching
    # realistically if they're not completed after a day or two, they're not going to be
    # set this to 3 days or so
    # !!WARNING!! if backfilling, set this to 0.
    'dead_binary_age': 3,

    # pid_file: process file for the scanner, if daemonized
    # make sure it's writable, leave blank for nginx
    'pid_file': ''

}

postprocess = {
    # release processing settings
    # ---------------------------

    # min_archives: the minimum number of archives in a binary to form a release
    # setting this to 1 will cut out releases that only contain an nzb, etc.
    'min_archives': 1,

    # min_completion: the minimum completion % that a release should satisfy
    # if it's lower than this, it'll get removed eventually
    # it'll only create releases of this completion if 3 hours have passed to make sure
    # we're not accidentally cutting off the end of a new release
    'min_completion': 99,

    # 100% completion resulted in about 11,000 unmatched releases after 4 weeks over 6 groups
    # lowering that to 99% built an extra 3,500 releases

    # postprocess_wait: time to sleep between postprocess.py loops
    # setting this to 0 may be horrible to online APIs, but if you've got a good
    # local db it should be fine
    # once you've scanned virtually everything and are just maintaining it,
    # set it to the same as update_wait or more.
    'postprocess_wait': 300,

    # process_rars: whether to check for passworded releases, get file size and count
    # this uses extra bandwidth, since it needs to download at least one archive
    # for something like a bluray release, this is quite large
    'process_rars': True,

    # unrar_path: path to unrar binary
    # for windows, this'll be wherever you installed it to
    # for linux, probably just /usr/bin/unrar
    # if windows, make sure to escape slashes, ie.
    # 'C:\\Program Files (x86)\\Unrar\\Unrar.exe'
    'unrar_path': '',

    # delete_spam: delete releases that contain executables
    # uses delete_spam_groups config for the groups to scan
    'delete_spam': True,

    # delete_spam_groups: which groups to remove exe'd releases from
    # comma-separated group names
    'delete_spam_groups': 'alt.binaries.hdtv,alt.binaries.hdtv.x264,alt.binaries.moovee,alt.binaries.movies.divx,alt.binaries.movies,alt.binaries.multimedia,alt.binaries.teevee',

    # delete_passworded: delete releases that are passworded
    'delete_passworded': True,

    # delete_potentially_passworded: delete releases that are probably passworded
    'delete_potentially_passworded': True,

    # delete_bad_releases: delete releases that we can't rename out of misc-other
    'delete_bad_releases': True,

    # delete_blacklisted_releases: delete releases matching blacklist rules during postproc
    # blacklisting is only done during part collation, so if releases are being renamed
    # during postproc, they'll hang around. this will do a second pass during postproc.
    'delete_blacklisted_releases': False,

    # delete_blacklisted_days: only go back x days looking for blacklisted releases
    # if you want to run this over your whole DB, set it to 0
    # you don't want to repeatedly do that, though
    # set it to 3 or so for normal operation
    'delete_blacklisted_days': 3,

    # process_imdb: match movie releases against IMDB
    # couchpotato sometimes depends on this data for API usage, definitely recommended
    'process_imdb': True,

    # process_tvrage: match TV releases against TVRage
    # sickbeard sometimes depends on this data for API usage, definitely recommended
    'process_tvrage': True,

    # process_nfos: grab NFOs for releases for other use
    # this can be used to clean release names, etc
    'process_nfos': True,

    # process_sfvs: grab SFVs for releases for other use
    # this can be used to clean release names, etc
    'process_sfvs': False,

    # fetch_blacklist_duration: the number of days between tvrage/imdb API attempts
    # so if we can't find a match for some movie, wait 7 days before trying that movie again
    # there's really no benefit to setting this low - anywhere from a week to several months is fine
    'fetch_blacklist_duration': 7,
    
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

log = {
    # logging settings
    # ----------------
    # logging_file: a filepath or None to go to stdout
    'logging_file': None,

    # logging.x where DEBUG, INFO, WARNING, ERROR, etc
    # generally, debug if something goes wrong, info for normal usage
    'logging_level': logging.DEBUG,

    # max_log_size: maximum size of logfiles before they get rotated
    # number, in bytes (this is 50mb)
    'max_log_size': 50*1024*1024,
    
}

# postgre server config
# hopefully self-explanatory
postgre = {
    'host': '',
    'port': 5432,
    'user': '',
    'pass': '',
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

# used in convert_mongo_to_postgre.py
# mongodb config
mongo = {
    # hostname: usually 'localhost'
    'host': '',

    # port: default is 27017
    # make sure there's no quotes around it
    'port': 27017,

    # user: username, if auth is enabled
    'user': '',

    # pass: password, likewise
    'pass': '',

    # db: database name in mongo
    'db': 'pynab',
}

# only used for convert_from_newznab.py
# you can probably leave this blank unless you know what you're doing
mysql = {
    'host': '',
    'port': 3306,
    'user': '',
    'passwd': '',
    'db': 'newznab',
}
