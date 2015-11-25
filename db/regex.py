additions = [
    # start above 200k for pynab regex
    {
        'id': 200000,
        'group_name': '.*',
        'regex': '/^trtk\d{4,8} - \[\d{1,5}\/\d{1,5}\] - "(?P<name>.+?)\.(?:nzb|vol\d+(?:\+\d+){1,}?\.par2|part\d+\.rar|par2|r\d{1,})" yEnc/i',
        'ordinal': 1,
        'status': True,
        'description': 'music releases'
    }
]

nn_replacements = {
    '677': {
        'id': 677,
        'regex': '/^.*?\"(?P<name>.*?)\.(pdb|htm|prc|lit|epub|lrf|txt|pdf|rtf|doc|chf|chn|mobi|chm|doc|par|rar|sfv|nfo|nzb|srt|ass|txt|zip|ssa|r\d{1,3}|7z|tar|idx|t\d{1,2}|u\d{1,3})/i',
        'status': True,
        'ordinal': 9,
        'group_name': 'alt.binaries.e-book.flood'
    },
    '678': {
        'id': 678,
        'regex': '/^.*?\"(?P<name>.*?)\.(pdb|htm|prc|lit|epub|lrf|txt|pdf|rtf|doc|chf|chn|mobi|chm|doc|par|rar|sfv|nfo|nzb|srt|ass|txt|zip|ssa|r\d{1,3}|7z|tar|idx|t\d{1,2}|u\d{1,3})/i',
        'status': True,
        'ordinal': 9,
        'group_name': 'alt.binaries.e-book'
    },
    '679': {
        'id': 679,
        'regex': '/^.*?\"(?P<name>.*?)\.(pdb|htm|prc|lit|epub|lrf|txt|pdf|rtf|doc|chf|chn|mobi|chm|doc|par|rar|sfv|nfo|nzb|srt|ass|txt|zip|ssa|r\d{1,3}|7z|tar|idx|t\d{1,2}|u\d{1,3})/i',
        'status': True,
        'ordinal': 9,
        'group_name': 'alt.binaries.ebook'
    },
    '680': {
        'id': 680,
        'regex': '/^.*?\"(?P<name>.*?)\.(pdb|htm|prc|lit|epub|lrf|txt|pdf|rtf|doc|chf|chn|mobi|chm|doc|par|rar|sfv|nfo|nzb|srt|ass|txt|zip|ssa|r\d{1,3}|7z|tar|idx|t\d{1,2}|u\d{1,3})/i',
        'status': True,
        'ordinal': 9,
        'group_name': 'alt.binaries.e-book.technical'
    },
    '682': {
        'id': 682,
        'regex': '/^.*?\"(?P<name>.*?)\.(pdb|htm|prc|lit|epub|lrf|txt|pdf|rtf|doc|chf|chn|mobi|chm|doc|par|rar|sfv|nfo|nzb|srt|ass|txt|zip|ssa|r\d{1,3}|7z|tar|idx|t\d{1,2}|u\d{1,3})/i',
        'status': False,
        'ordinal': 9,
        'group_name': 'alt.binaries.ebook.flood'
    },
}

nzedb_replacements = {
    '1030': {
        'id': 1030,
        'regex': '/^\(\?+\)[-_\s]{0,3}[\(\[]\d+\/\d+[\]\)][-_\s]{0,3}"(?P<match0>.+?([-_](proof|sample|thumbs?))*(\.part\d*(\.rar)?|\.rar)?(\d{1,3}\.rev|\.vol.+?|\.[A-Za-z0-9]{2,4}).)"[-_\s]{0,3}yEnc$/i',
        'status': True,
        'ordinal': 65,
        'group_name': 'alt.binaries.tv'
    }
}