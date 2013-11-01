"""With big thanks to SABNZBD, since they're maybe the only ones with yenc code that
works in Python 3"""

import regex

from pynab import log

YDEC_TRANS = ''.join([chr((i + 256 - 42) % 256) for i in range(256)])


def yenc_decode(lines):
    """Decodes a yEnc-encoded fileobj.
    Should use python-yenc 0.4 for this, but it's not py3.3 compatible.
    """

    data = yenc_strip([l.decode('ISO-8859-1') for l in lines])

    if data:
        yenc, data = yenc_check(data)
        ybegin, ypart, yend = yenc

        if ybegin and yend:
            data = ''.join(data)
            for i in (0, 9, 10, 13, 27, 32, 46, 61):
                j = '=%c' % (i + 64)
                data = data.replace(j, chr(i))
            return data.translate(YDEC_TRANS)
        else:
            log.debug('File wasn\'t yenc.')
            log.debug(data)
    else:
        log.debug('Problem parsing lines.')

    return None


def yenc_check(data):
    ybegin = None
    ypart = None
    yend = None

    ## Check head
    for i in range(min(40, len(data))):
        try:
            if data[i].startswith('=ybegin '):
                splits = 3
                if data[i].find(' part=') > 0:
                    splits += 1
                if data[i].find(' total=') > 0:
                    splits += 1

                ybegin = yenc_split(data[i], splits)

                if data[i + 1].startswith('=ypart '):
                    ypart = yenc_split(data[i + 1])
                    data = data[i + 2:]
                    break
                else:
                    data = data[i + 1:]
                    break
        except IndexError:
            break

    ## Check tail
    for i in range(-1, -11, -1):
        try:
            if data[i].startswith('=yend '):
                yend = yenc_split(data[i])
                data = data[:i]
                break
        except IndexError:
            break

    return (ybegin, ypart, yend), data


YSPLIT_RE = regex.compile(r'([a-zA-Z0-9]+)=')


def yenc_split(line, splits=None):
    fields = {}

    if splits:
        parts = YSPLIT_RE.split(line, splits)[1:]
    else:
        parts = YSPLIT_RE.split(line)[1:]

    if len(parts) % 2:
        return fields

    for i in range(0, len(parts), 2):
        key, value = parts[i], parts[i + 1]
        fields[key] = value.strip()

    return fields


def yenc_strip(data):
    while data and not data[0]:
        data.pop(0)

    while data and not data[-1]:
        data.pop()

    for i in range(len(data)):
        if data[i][:2] == '..':
            data[i] = data[i][1:]
    return data