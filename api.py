import re

import bottle
from bottle import request, response
import xmltodict

from pynab import log
import pynab.api

app = application = bottle.Bottle()


@app.get('/api')
def api():
    log.debug('Handling request for {0}.'.format(request.fullpath))

    # these are really basic, don't check much
    function = request.query.t or pynab.api.api_error(200)

    for r, func in pynab.api.functions.items():
        # reform s|search into ^s$|^search$
        # if we don't, 's' matches 'caps' (s)
        r = '|'.join(['^{0}$'.format(r) for r in r.split('|')])
        if re.search(r, function):
            dataset = dict()
            dataset['get_link'] = get_link
            data = func(dataset)
            output_format = request.query.o or 'xml'
            if output_format == 'xml':
                # return as xml
                response.set_header('Content-type', 'application/rss+xml')
                return data
            elif output_format == 'json':
                # bottle auto-converts into json
                return xmltodict.parse(data)
            else:
                return pynab.api.api_error(201)


def get_link(route):
    url = request.environ['wsgi.url_scheme'] + '://'

    if request.environ.get('HTTP_HOST'):
        url += request.environ['HTTP_HOST']
    else:
        url += request.environ['SERVER_NAME']

        if request.environ['wsgi.url_scheme'] == 'https':
            if request.environ['SERVER_PORT'] != '443':
                url += ':' + request.environ['SERVER_PORT']
        else:
            if request.environ['SERVER_PORT'] != '80':
                url += ':' + request.environ['SERVER_PORT']

    return url + app.get_url(route)


if __name__ == '__main__':
    bottle.run(app=app, host='0.0.0.0', port=8080)