#
# Copyright (c) SAS Institute Inc
#

from urlparse import urljoin
import logging
import os

from lxml import objectify
import requests

from .pompackage import Package


__all__ = ()


log = logging.getLogger(__name__)

XMLParser = objectify.makeparser(recover=True, remove_comments=True)


def detail(func):
    def wrapper(*args, **kwargs):
        info = kwargs.pop('info', False)
        properties = kwargs.pop('properties', False)

        detail = []
        if info:
            detail.append('info')
        elif properties:
            detail.append('properties')
        if detail:
            kwargs.setdefault(
                'headers', {})['x-result-detail'] = ','.join(detail)
        return func(*args, **kwargs)
    return wrapper


def repos(func):
    def wrapper(*args, **kwargs):
        repos = kwargs.pop('repos', None)
        if repos:
            if isinstance(repos, str):
                repos = [repos]
            kwargs.setdefault('params', {})['repos'] = ','.join(repos)
        return func(*args, **kwargs)
    return wrapper


class Client(object):
    """
    Client for talking to artfactory api
    """

    def __init__(self, url, auth=None, headers=None):
        """
        Create a client from a url.

        If you need authenticatio, pass in a tuple of username and password:
            Client("http://example.com", ("user", "secret"))
        or
            Client("http://example.com", auth=("user", "secret"))

        If there are default headers you want used for every request, pass in
        a dictionary:
            Client("http://example.com,
                headers={'my-default-header': 'foo'})

        :param str hostname: hostname of artifactory
        :param int port: port if other than 80/443
        :param bool https: use https if true
        :param tuple auth: 2-tuple of username and password
        :param dict headers: dictionary of headers to use for all requests
        """
        # append a / to url if it doesn't end with one
        self.url = url + ('' if url.endswith('/') else '/')
        self._api_url = urljoin(self.url, "api/")

        self._session = requests.Session()
        if auth:
            self._session.auth = auth
        if headers:
            self._session.headers.update(headers)

    def _get(self, uris, **kwargs):
        res = self._request('GET', uris, **kwargs)
        return res

    def _post(self, uris,  **kwargs):
        res = self._request_many('POST', uris, **kwargs)
        return res

    def _request(self, method, uris, return_json=True, **kwargs):
        return_one = False
        if isinstance(uris, str):
            return_one = True
            uris = [uris]
        urls = [urljoin(self.url, uri) for uri in uris]
        res = [self._session.request(method, u, **kwargs) for u in urls]
        if return_json:
            res = [r.json() for r in res]
        if return_one:
            return res[0]
        return res

    def _search(self, path, **kwargs):
        log.debug("search(%s, kwargs=%s)", path, kwargs)
        res = self._get(urljoin("api/search/", path), **kwargs)
        results = res.get('results')
        urls = [r['uri'] for r in results]
        res = self._get(urls)
        return res

    @repos
    @detail
    def quick_search(self, name, **kwargs):
        kwargs.setdefault('params', {})['name'] = name
        results = self._search("artifact/", **kwargs)
        return results

    @repos
    def class_search(self, name, **kwargs):
        kwargs.setdefault('params', {})['name'] = name
        return self._get("archive/", **kwargs)

    @detail
    @repos
    def gavc_search(self, group=None, artifact=None, version=None,
                    classifier=None, **kwargs):
        """
        Search by Maven coordinates: GroupId, ArtifactId, Version &
        Classifier. Search must contain at least one argument. Can
        limit search to specific repositories (local or caches).

        You can retrieve extra information or properites by setting
        the `info` or `properties` flags to True

        :param str group: a group id to search for
        :param str artifact: an artifact id to search fo
        :param str version: a version string
        :param str classifier: a classifier string
        :param repos: limit search to these repositories, local or cache
        :type repos: str or list
        :param bool info: add all extra information
        :param bool properties: get the properties of found artifacts
        """
        params = {}
        if group:
            params["g"] = group
        if artifact:
            params["a"] = artifact
        if version:
            params['v'] = version
        if classifier:
            params['c'] = classifier
        if not params:
            raise ValueError("Must provide one of: group, artifact, version,"
                             " or classifier")
        kwargs.setdefault('params', {}).update(params)
        results = self._search("gavc/", **kwargs)
        return results

    @detail
    @repos
    def property_search(self, properties, **kwargs):
        if not isinstance(properties, dict):
            properties = dict(properties)
        kwargs.setdefault('params', {}).update(properties)
        return self._search("prop/", **kwargs)

    @detail
    @repos
    def checksum_search(self, checksum, checksum_type, **kwargs):
        if checksum_type not in ('md5', 'sha1'):
            raise ValueError("Invalid checksum type: '%s'" % checksum_type)
        kwargs.setdefault('params', {})[checksum_type] = checksum
        return self._search('checksum/', **kwargs)

    def pattern_search(self, pattern, **kwargs):
        kwargs.setdefault('params', {})['pattern'] = pattern
        return self._search('pattern/', **kwargs)

    @repos
    def version_search(self, group=None, artifact=None, **kwargs):
        params = {}
        if group:
            params['g'] = group
        if artifact:
            params['a'] = artifact

        if not params:
            raise ValueError("Must specify at least one of: group, artifact")

        if 'version' in kwargs:
            params['version'] = kwargs.pop('version')

        if 'remote' in kwargs:
            params['remote'] = str(1 if kwargs.pop('remote') else 0)

        kwargs.setdefault('params', {}).update(params)
        return self._search('versions/', **kwargs)

    def retrieve_artifact(self, paths, stream=False):
        if isinstance(paths, str):
            paths = [paths]
            return_one = True
        urls = [p.replace(':', '', 1) for p in paths]
        res = self._request('GET', urls, stream=stream, return_json=False)
        if return_one:
            return res[0]
        return res

    @property
    def repositories(self):
        return self._get('repositories/')

    def walk(self, repo, top=None, topdown=True, ignorehidden=True):
        base_uri = 'storage/' + repo

        # normalize path argument
        if top is None:
            top = '/'
        elif not top.startswith('/'):
            top = '/' + top

        parent = self._get(base_uri + top)
        folders, artifacts = [], []
        for child in parent['children']:
            if child['uri'].startswith('/.') and ignorehidden:
                continue

            if top == '/':
                uri = child['uri']
            else:
                uri = parent['path'] + child['uri']

            child_obj = self._get(base_uri + uri)
            if child['folder']:
                folders.append(child_obj)
            else:
                artifacts.append(child_obj)

        if topdown:
            yield parent, folders, artifacts

        for folder in folders:
            for x in self.walk(repo, folder['path'], topdown):
                yield x

        if not topdown:
            yield parent, folders, artifacts

    def getPackageDetails(self, repo, archStr):
        poms = [pom for pom in self.quick_search('pom', repos=repo)
                if pom.get('mimeType') == 'application/x-maven-pom+xml']

        for pom in poms:
            location ='{repo}:{path}'.format(**pom)
            pomFile = self.retrieve_artifact(location)
            pomObject = objectify.fromstring(pomFile.text.encode('utf-8'),
                                             XMLParser)
            if hasattr(pomObject, 'getroot'):
                pomObject = pomObject.getroot()

            artifacts = self.gavc_search(
                str(pomObject.groupId if hasattr(pomObject, 'groupId')
                    else pomObject.parent.groupId),
                str(pomObject.artifactId),
                str(pomObject.version if hasattr(pomObject, 'version')
                    else pomObject.parent.version),
                )

            if not artifacts:
                log.debug('No extra artifacts assocated with %s', location)

            yield Package(pomObject, location)
            yield Package(pomObject, location, archStr, artifacts)
