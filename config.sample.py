# general site configuration
site = {
    # should be a 128-bit randomised hex string
    # you can generate one with:
    # print("%032x" % random.getrandbits(128))
    'seed': ''
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