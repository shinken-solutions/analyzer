import json
import urllib2
import urllib

_HTTP_EXCEPTIONS = None


def get_http_exceptions():
    global _HTTP_EXCEPTIONS
    if _HTTP_EXCEPTIONS is not None:
        return _HTTP_EXCEPTIONS
    HTTP_EXCEPTIONS = (urllib2.HTTPError, urllib2.URLError, )
    _HTTP_EXCEPTIONS = HTTP_EXCEPTIONS
    return _HTTP_EXCEPTIONS


class Httper(object):
    def __init__(self):
        pass
    
    
    @staticmethod
    def get(uri, params={}, headers={}, with_status_code=False):
        data = None  # always none in GET
        
        if params:
            uri = "%s?%s" % (uri, urllib.urlencode(params))
        
        url_opener = urllib2.build_opener(urllib2.HTTPHandler)
        
        req = urllib2.Request(uri, data)
        req.get_method = lambda: 'GET'
        for (k, v) in headers.iteritems():
            req.add_header(k, v)
        request = url_opener.open(req)
        response = request.read()
        #
        # if code != 200:
        #    raise urllib2.HTTPError('')
        if not with_status_code:
            return response
        else:
            status_code = request.code
            return (status_code, response)
    
    
    @staticmethod
    def delete(uri, params={}, headers={}):
        data = None  # always none in GET
        
        if params:
            uri = "%s?%s" % (uri, urllib.urlencode(params))
        
        url_opener = urllib2.build_opener(urllib2.HTTPHandler)
        
        req = urllib2.Request(uri, data)
        req.get_method = lambda: 'DELETE'
        for (k, v) in headers.iteritems():
            req.add_header(k, v)
        request = url_opener.open(req)
        response = request.read()
        # code = request.code
        return response
    
    
    @staticmethod
    def post(uri, params={}, headers={}):
        data = None  # always none in GET
        
        if params:
            # TODO: sure it's json and not urlencode?
            # data = urllib.urlencode(params)
            data = json.dumps(params)
        
        url_opener = urllib2.build_opener(urllib2.HTTPHandler)
        
        req = urllib2.Request(uri, data)
        req.get_method = lambda: 'POST'
        for (k, v) in headers.iteritems():
            req.add_header(k, v)
        request = url_opener.open(req)
        response = request.read()
        # code = request.code
        return response
    
    
    @staticmethod
    def put(uri, data=None, params={}, headers=None):
        #data = None  # always none in GET
        if headers is None:
            headers = {}
        
        if params:
            # TODO: sure it's json and not urlencode?
            # data = urllib.urlencode(params)
            uri = "%s?%s" % (uri, urllib.urlencode(params))
            headers['Content-Type'] = 'your/contenttype'
        
        url_opener = urllib2.build_opener(urllib2.HTTPHandler)
        
        req = urllib2.Request(uri, data)
        req.get_method = lambda: 'PUT'
        for (k, v) in headers.iteritems():
            req.add_header(k, v)
        request = url_opener.open(req)
        response = request.read()
        # code = request.code
        return response


httper = Httper()
