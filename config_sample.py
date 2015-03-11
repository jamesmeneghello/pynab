import logging

stats = {
    # stats settings
    # settings in this section will take effect on the fly. no need to restart
    # ------------------------------------------------------------------------

    # how long to sleep in seconds between stats reports
    'sleep_time': 300,

    # print header every nth report
    'header_every_nth': 20,

    # write a separate .csv file for use in excel.
    'write_csv': True,
}

monitor = {
    # type: monitor type
    # supervisor, windows
    #
    # supervisor requires daemons and logs - ensure pid_file and logging_file
    # options are set for scan, postprocess
    #
    # windows OSs can only use windows and should also set logging_file etc
    'type': 'supervisor',
}

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

    # postprocessed_only: whether to wait for some postproc to finish before showing results
    # effectively, only releases that've gone through inner rar checking will be shown by the api
    'postprocessed_only': False
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

    # full_vacuum: whether to run full_vacuums
    # you might not want to do this if your db is on an ssd
    # it rewrites the whole table to a new file
    'full_vacuum': True,

    # full_vacuum_iterations: number of iterations between full vacuums
    # the main tables are vacuumed each iteration of scanning/postproc
    # full vacuum can be really, really slow though!
    # and it requires a full-table lock
    # so if your update_wait is 300 (5 minutes), 288 is vacuum-full once per day
    'full_vacuum_iterations': 288,

    # new_group_scan_days: how many days to scan for a new group
    # make sure there's no quotes around it
    # 'new_group_scan_days': 5,
    # DEPRECATED: now uses backfill_days

    # message_scan_limit: number of messages to take from nntp server at once
    # make sure there's no quotes around it
    'message_scan_limit': 20000,

    # group_scan_limit: maximum number of messages to take from each group per scan
    # useful for very active groups on limited hardware
    # a scan iteration will only take this many messages per group before processing
    # hence, 10 groups x 2m messages = 20m segments total in the db
    # set None to scan forever, if you have a shitload of memory
    'group_scan_limit': 2000000,

    # early_process_threshold: start processing after a backlog
    # if each scan is getting too many segments, process them before
    # scanning. this will force an early process if there are more segments
    # saved than the number given here.
    #
    # this can probably be left at 50m unless you have memory issues
    # or are scanning very active groups. most people won't use this!
    'early_process_threshold': 50000000,

    # retry_missed: whether to re-scan for missed messages
    # slow, but useful for some providers
    'retry_missed': False,

    # miss_retry_limit: number of times to retry missed messages
    # integer, it'll retry this many times before giving up.
    'miss_retry_limit': 3,

    # backfill_days: number of days to backfill groups or scan new groups
    # make sure there's no quotes around it
    'backfill_days': 10,

    # binary_process_chunk_size: number of parts to process per batch
    # baseline process memory usage is about 20mb, this adds approximately:
    # 1000 - +4mb
    # 10000 - +32mb
    # ...i probably wouldn't go much higher than that
    'binary_process_chunk_size': 10000,

    # dead_binary_age: number of days to keep binaries for matching
    # realistically if they're not completed after a day or two, they're not going to be
    # set this to 3 days or so
    # !!WARNING!! if backfilling, set this to 0.
    'dead_binary_age': 1,

    # publish: publish release info in json to a host
    # useful for xmpp pubsub or any listening scripts
    # it just sends a POST to the server with the json
    'publish': False,

    # publish_hosts: hosts to send processed release data to
    # include the port and path if necessary
    # ie. ['http://127.0.0.1:5678/releases', 'http://someaddress.com/whatever']
    'publish_hosts': ['http://127.0.0.1:8090']
}

postprocess = {
    # release processing settings
    # ---------------------------

    # max_process_size: maximum size of releases to process
    # some releases can be really, really big (think 150+gb)
    # sometimes we don't even want to bother with those releases
    # since they'll take forever to index and possibly choke the server
    # this is the upper limit
    # 'max_process_size': 30*1024*1024*1024, # 30gb
    'max_process_size': 10 * 1024 * 1024 * 1024,

    # max_process_anyway: try to process huge releases anyway
    # you can attempt to index massive releases anyway
    # this will be slow and horrible and might kill everything
    # if you get memory_errors, disable this
    # if False, any oversized binaries will be deleted when processing
    'max_process_anyway': True,

    # min_size: minimum size of releases per-group
    # anything smaller than this in a group will be deleted
    # layout is minimum size and then a list of groups to check, ie.
    # 'min_size': {
    # 104857600: ['alt.binaries.hdtv', 'alt.binaries.hdtv.x264'],
    #     314572800: ['alt.binaries.mooveee']
    # },
    'min_size': {},

    # min_archives: the minimum number of archives in a binary to form a release
    # this is per-group or global
    # for per-group:
    # minimum 1 for every group except e-books, which is 0
    # 'min_archives': {
    #     'alt.binaries.e-books: 0,
    #     '*': 1
    # }
    # or
    # 'min_archives': 1 # 1 for all groups
    'min_archives': 1,

    # min_completion: the minimum completion % that a release should satisfy
    # if it's lower than this, it'll get removed eventually
    # it'll only create releases of this completion if 3 hours have passed to make sure
    # we're not accidentally cutting off the end of a new release
    'min_completion': 100,

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

    # process requests: query the pre table to
    # try and discover names from request ids
    'process_requests': True,

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
    # logging_dir: a filepath or None to go to stdout
    # this should be something like '/var/log/pynab'
    # it'll automatically split the logfiles for you
    'logging_dir': None,

    # logging.x where DEBUG, INFO, WARNING, ERROR, etc
    # generally, debug if something goes wrong, info for normal usage
    'logging_level': logging.DEBUG,

    # max_log_size: maximum size of logfiles before they get rotated
    # number, in bytes (this is 50mb)
    'max_log_size': 50 * 1024 * 1024,

    # enable/disable color logging to console
    'colors': True,
}

# main db server config
# mostly self-explanatory
db = {
    # engine: which db server type to use
    # 'postgresql' or 'mysql+pymysql'
    # maria, percona, etc use the latter
    'engine': 'postgresql',
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

# xmpp pubsub bot
# used to push nzbs, rather than waiting for rss updates
bot = {
    # enabled: whether to enable the xmpp pubsub bot
    'enabled': False,

    # host: jabber server hostname
    'host': '',

    # jid: jabber_id
    'jid': '',

    # password: jabber password
    'password': '',

    # listen: host/port to listen on for releases in json
    # should be a tuple, eg. for localhost:8090
    # ('', 8090)
    'listen': ('', 8090)
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
