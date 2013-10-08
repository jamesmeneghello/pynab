import re
import gzip

from bottle import get, run, request, response
import xmltodict

from pynab import log
from pynab.db import db, fs
import pynab.api


@get('/api')
def api():
    log.debug('Handling request for {0}.'.format(request.fullpath))

    # these are really basic, don't check much
    function = request.query.t or pynab.api.api_error(200)

    for r, func in pynab.api.functions.items():
        # reform s|search into ^s$|^search$
        # if we don't, 's' matches 'caps' (s)
        r = '|'.join(['^{0}$'.format(r) for r in r.split('|')])
        print('{0}: {1}'.format(r, func))
        if re.search(r, function):
            data = func()
            output_format = request.query.o or 'xml'
            if output_format == 'xml':
                # return as xml
                return data
            elif output_format == 'json':
                # bottle auto-converts into json
                return xmltodict.parse(data)
            else:
                return pynab.api.api_error(201)


@get('/getnzb/<id>')
def get_nzb(id):
    r = request.query.r or ''
    i = request.query.i or ''

    if r:
        release = db.releases.find_one({'id': id})
        if release:
            data = fs.get(release['nzb']).read()
            response.set_header('Content-type', 'application/x-nzb')
            response.set_header('X-DNZB-Name', release['search_name'])
            response.set_header('X-DNZB-Category', release['category']['name'])
            response.set_header('Content-Disposition', 'attachment; filename="{0}"'
            .format(release['search_name'].replace(' ', '_') + '.nzb')
            )
            return gzip.decompress(data)
        else:
            pynab.api.api_error(300)
    else:
        pynab.api.api_error(100)


run(host='localhost', port=9090, debug=True)