#
# Copyright (c) SAS Institute Inc
#

from urlparse import urljoin
import logging
import os

import requests

from .pompackage import PomPackage


__all__ = ('Client', 'PomPackage')

log = logging.getLogger(__name__)

# Turn down the logging level on requeests
requests_logger = logging.getLogger('requests.packages.urllib3.connectionpool')
requests_logger.setLevel(logging.WARN)


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
            if isinstance(repos, (str, unicode)):
                repos = [repos]
            kwargs.setdefault('params', {})['repos'] = ','.join(repos)
        return func(*args, **kwargs)
    return wrapper


class Client(object):
    """
    Client for talking to artfactory api
    """

    def __init__(self, cfg, headers=None):
        """
        Create a client from a updatebot config object.

        If there are default headers you want used for every request, pass in
        a dictionary:
            Client("http://example.com,
                headers={'my-default-header': 'foo'})

        :param UpdateBotConfig cfg: cfg object to use for configuring the client
        :param dict headers: dictionary of headers to use for all requests
        """
        # append a / to url if it doesn't end with one
        self._cfg = cfg
        self._url = cfg.repositoryUrl + '/'
        self._api_url = urljoin(self._url, "api/")

    def _get(self, uri, **kwargs):
        res = self._request('GET', uri, **kwargs)
        return res

    def _post(self, uri,  **kwargs):
        res = self._request('POST', uri, **kwargs)
        return res

    def _head(self, uri, **kwargs):
        res = self._request('HEAD', uri, return_json=False, **kwargs)
        return res

    def _request(self, method, uri, return_json=True, **kwargs):
        url = urljoin(self._url, uri)
        res = requests.request(method, url, **kwargs)
        if return_json:
            return res.json()
        return res

    def _search(self, path, **kwargs):
        log.debug("search(%s, kwargs=%s)", path, kwargs)
        if 'auth' not in kwargs:
            kwargs['auth'] = self._cfg.artifactoryUser.find(self._cfg.repositoryUrl)

        res = self._get(urljoin("api/search/", path), **kwargs)
        urls = [r['uri'] for r in res.get('results', [])]

        for url in urls:
            res = self._get(url)
            yield res

    @staticmethod
    def constructPath(groupId, artifactId, version=None, artifactName=None,
                      extension='pom', relative=False):
        """Construct a maven 2 path

        :param groupId: group name
        :type groupId: string
        :param artifactId: artifact name
        :type artifactId: string
        :param version: (None) version of artifact
        :type version: string
        :param artifactName: (None) artifact name if not the artifactId
        :type artifactName: string
        :param extension: (pom) file extention of artifact
        :type extension: string
        :param relative: (False) generate a relative path
        :type relative: bool
        """
        path = '/{0}/{1}'
        if relative:
            path = path[1:]

        if version:
            path += '/{2}'

        if artifactName:
            path += '/{3}.{4}'
        else:
            path += '/{1}-{2}.{4}'

        return path.format(
            groupId.replace('.', '/'),
            artifactId,
            version,
            artifactName,
            extension,
            )

    def artifactUrl(self, group, artifact, version, extension='pom'):
        path = self.constructPath(group, artifact, version, extension=extension,
                                  relative=True)
        uri = urljoin('repo/', path)
        return urljoin(self._url, uri)

    def checkJar(self, group, artifact, version):
        path = self.constructPath(group, artifact, version, extension='jar',
                                  relative=True)
        uri = urljoin('repo/', path)
        res = self._head(uri)
        return res.status_code == requests.codes.ok

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

    def retrieve_artifact(self, path, stream=False):
        url = path.replace(':', '', 1)
        res = self._request('GET', url, stream=stream, return_json=False)
        if res.status_code == requests.codes.ok:
            if stream:
                return res.raw
            return res.text.encode('utf-8')

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
