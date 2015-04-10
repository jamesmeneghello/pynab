additions = [
    # start above 200k for pynab regex
    {
        'id': 200000,
        'group_name': '.*',
        'regex': '/^trtk\d{4,8} - \[\d{1,5}\/\d{1,5}\] - "(?P<name>.+?)\.(?:nzb|vol\d+(?:\+\d+){1,}?\.par2|part\d+\.rar|par2|r\d{1,})" yEnc \(\d{1,5}\/\d{1,5}\)$/i',
        'ordinal': 2,
        'status': True,
        'description': 'music releases'
    }
]

replacements = {
}