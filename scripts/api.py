import re

from bottle import get, run, request
import xmltodict

from pynab import log
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


run(host='localhost', port=9090, debug=True)