import json

import regex
import bottle
from bottle import request, response
import xmltodict

from pynab import log, log_init
import pynab.api
import config


app = application = bottle.Bottle()

# bottle.debug(True)

@app.get('/scripts/:path#.+#')
def serve_static(path):
    return bottle.static_file(path, root='./webui/dist/scripts/')


@app.get('/styles/:path#.+#')
def serve_static(path):
    return bottle.static_file(path, root='./webui/dist/styles/')


@app.get('/views/:path#.+#')
def serve_static(path):
    return bottle.static_file(path, root='./webui/dist/views/')


@app.get('/fonts/:path#.+#')
def serve_static(path):
    return bottle.static_file(path, root='./webui/dist/fonts/')


@app.get('/bower_components/:path#.+#')
def serve_static(path):
    return bottle.static_file(path, root='./webui/dist/bower_components/')


@app.get('/api')
def api():
    log.debug('Handling request for {0}.'.format(request.fullpath))

    # these are really basic, don't check much
    function = request.query.t or pynab.api.api_error(200)

    for r, func in pynab.api.functions.items():
        # reform s|search into ^s$|^search$
        # if we don't, 's' matches 'caps' (s)
        r = '|'.join(['^{0}$'.format(r) for r in r.split('|')])
        if regex.search(r, function):
            dataset = dict()
            dataset['get_link'] = get_link
            dataset['function'] = function
            data = func(dataset)
            return switch_output(data)

    # didn't match any functions
    return pynab.api.api_error(202)


@app.get('/')
@app.get('/index.html')
def index():
    if config.api.get('webui'):  # disabled by default ? not really useful for a single user install
        raise bottle.static_file('index.html', root='./webui/dist')


@app.get('/favicon.ico')
def index():
    if config.api.get('webui'):
        raise bottle.static_file('favicon.ico', root='./webui/dist')


def switch_output(data):
    output_format = request.query.o or 'xml'
    output_callback = request.query.callback or None

    if output_format == 'xml':
        # return as xml
        response.set_header('Content-type', 'application/rss+xml')
        return data
    elif output_format == 'json':
        if output_callback:
            response.content_type = 'application/javascript'
            return '{}({})'.format(output_callback, json.dumps(xmltodict.parse(data, attr_prefix='')))
        else:
            # bottle auto-converts a python dict into json
            return xmltodict.parse(data, attr_prefix='')
    else:
        return pynab.api.api_error(201)


def get_link(route=''):
    """Gets a link (including domain/subdirs) to a route."""
    if request.environ.get('HTTPS') == '1':
        request.environ['wsgi.url_scheme'] = 'https'

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

    url += request.environ.get('SCRIPT_NAME', '')
    if route:
        url += route

    return url


def main():
    bottle.run(app=app, host=config.api.get('api_host', '0.0.0.0'), port=config.api.get('api_port', 8080))


if __name__ == '__main__':
    log_init('api')
    main()
