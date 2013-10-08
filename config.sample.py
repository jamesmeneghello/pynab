import pynab

site = {
    # general site settings
    'title': 'pynab',
    'description': 'a pynab api',
    'version': pynab.__version__,
    'api_version': '0.1',
    'email': '',
    'seed': '',

    # api settings
    'result_limit': 100,
    'result_default': 20,

    # scanning settings
    'new_group_scan_days': 5,
    'message_scan_limit': 20000,
    'backfill_days': 10
}

# mongodb details
db = {
    'host': 'localhost',
    'port': 27017,
    'user': '',
    'pass': '',
    'db': 'pynab',
}

# news server details
news = {
    'host': '',
    'user': '',
    'password': '',
    'port': 443,
    'ssl': True,
}

# for newznab import only
mysql = {
    'host': '10.1.1.15',
    'port': 3306,
    'user': '',
    'passwd': '',
    'db': 'newznab',
}