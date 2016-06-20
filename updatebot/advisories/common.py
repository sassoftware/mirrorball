#
# Copyright (c) 2008-2009 rPath, Inc.
#
# This program is distributed under the terms of the Common Public License,
# version 1.0. A copy of this license should have been distributed with this
# source file in a file called LICENSE. If it is not present, the license
# is always available at http://www.rpath.com/permanent/licenses/CPL-1.0.
#
# This program is distributed in the hope that it will be useful, but
# without any warranty; without even the implied warranty of merchantability
# or fitness for a particular purpose. See the Common Public License for
# full details.
#

"""
Base modules for dealing
"""

import time
import smtplib
import logging
from email.MIMEText import MIMEText
from smtplib import SMTPRecipientsRefused, SMTPHeloError
from smtplib import SMTPSenderRefused, SMTPDataError

log = logging.getLogger('updatebot.advisories')

from updatebot.errors import AdvisoryRecipientRefusedError
from updatebot.errors import FailedToSendAdvisoryError
from updatebot.errors import MultipleAdvisoriesFoundError
from updatebot.errors import NoAdvisoryFoundError
from updatebot.errors import NoPackagesFoundForAdvisory
from updatebot.errors import NoRecipientsFoundError
from updatebot.errors import NoSenderFoundError
from updatebot.errors import ProductNameNotDefinedError
from updatebot.errors import ExtraPackagesFoundInUpdateError

class BaseAdvisory(object):
    """
    Module for representing an advisory message.
    """

    template = """\
Published: %(date)s
Products:
    %(product)s

Updated Versions:
%(updateTroves)s

Description:
%(description)s
"""

    def __init__(self, cfg):
        self._cfg = cfg

        self._fromName = self._cfg.emailFromName
        self._from = self._cfg.emailFrom
        self._to = self._cfg.emailTo
        self._bcc = self._cfg.emailBcc

        self._subject = None

        if not self._cfg.productName:
            raise ProductNameNotDefinedError

        if not self._from or not self._fromName:
            raise NoSenderFoundError(why='Configuration error, emailFrom or '
                'emailFromName not defined')

        if not self._to:
            raise NoRecipientsFoundError(why='Configuration error, emailTo not '
                'defined')

        self._data = {'product': self._cfg.productName,
                      'date': time.strftime('%Y-%m-%d', time.localtime()),
                      'updateTroves': ''}

    def __str__(self):
        return self._subject

    def send(self):
        """
        Send an advisory email.
        """

        message = self._getMessage()
        smtp = self._smtpConnect()

        try:
            results = smtp.sendmail(self._from, self._to + self._bcc,
                                    message.as_string())
        except (SMTPRecipientsRefused, SMTPHeloError, SMTPSenderRefused,
                SMTPDataError), e:
            raise FailedToSendAdvisoryError(error=e)

        smtp.quit()

        if results is not None and results != {}:
            raise AdvisoryRecipientRefusedError(data=results)

        return results

    def _getMessage(self):
        """
        Get the message to send.
        """

        msgText = self.template % self._data
        email = MIMEText(msgText)
        email['Subject'] = self._subject
        email['From'] = '%s <%s>' % (self._fromName, self._from)
        email['To'] = self._formatList(self._to)
        return email

    @staticmethod
    def _formatList(lst):
        """
        Format a list to be comma separated.
        """

        return ', '.join(lst)

    def _smtpConnect(self):
        """
        Get a smtp connection object.
        """

        server = smtplib.SMTP(self._cfg.smtpServer)

        rootLogger = logging.getLogger('')
        if rootLogger.level == logging.DEBUG:
            server.set_debuglevel(1)

        return server

    def setUpdateTroves(self, troves):
        """
        Set the list of updated troves to add to the advisory.
        @param troves: list of troves
        @type troves: [(name, version, flavor), ... ]
        """

        trvs = set()
        for n, v, f in troves:
            trvs.add(self._formatTrove(n, v, f))

        self._data['updateTroves'] += self._indentFormatList(trvs)

    @staticmethod
    def _indentFormatList(lst, indent=1):
        """
        Format a list into a string with tab indention.
        """

        tab = '    ' * indent
        joinString = '\n' + tab
        result = tab + joinString.join(lst)
        return result

    @staticmethod
    def _formatTrove(n, v, f):
        """
        Format a trove spec into a string.
        """

        # W0613 - Unused argument 'f'
        # pylint: disable-msg=W0613

        label = v.trailingLabel().asString()
        revision = v.trailingRevision().asString()

        return '%s=%s/%s' % (n, label, revision)

    def setSubject(self, subject):
        """
        Set the subject of the advisory email.
        """

        self._subject = subject

    def setDescription(self, desc):
        """
        Set the description of the advisory.
        """

        self._data['description'] = desc


class BaseAdvisor(object):
    """
    Class for managing, manipulating, and distributing advisories.
    """

    _advisoryClass = BaseAdvisory
    allowExtraPackages = False

    def __init__(self, cfg, pkgSource):
        self._cfg = cfg
        self._pkgSource = pkgSource

        # { binPkg: set([patchObj, ...]) }
        self._pkgMap = dict()

        # { patchObj: set([srcPkg, ...] }
        self._cache = dict()

        # { ((name, version, flavor), srcPkg): [ advisoryObj, ...] }
        self._advisories = dict()

    def check(self, trvLst):
        """
        Check to see if there are advisories for troves in trvLst.
        @param trvLst: list of troves and srpms.
        @type trvLst: [((name, version, flavor), srcPkg), ... ]
        """

        # FIXME: Maybe we should check to see if all binary rpms listed in
        #        the advisory are in the set of packages to be updated.

        for nvf, srcPkg in trvLst:
            patches = set()
            for binPkg in self._pkgSource.srcPkgMap[srcPkg]:
                if binPkg in self._pkgMap:
                    patches.update(self._pkgMap[binPkg])

            if self._checkForDuplicates(patches):
                patches = set([patches.pop()])

            # Make sure we have advisories for all packages we expect to have
            # advisories for.
            for binPkg in self._pkgSource.srcPkgMap[srcPkg]:
                # Don't check srpms.
                if binPkg is srcPkg or binPkg in self._pkgMap:
                    continue
                elif self._hasException(binPkg):
                    log.info('found advisory exception for %s' % binPkg)
                    log.debug(binPkg.location)
                elif not self._isUpdatesRepo(binPkg):
                    log.info('package not in updates repository %s' % binPkg)
                    log.debug(binPkg.location)
                elif len(patches) > 0:
                    log.info('found package not mentioned in advisory %s'
                             % binPkg)
                    log.debug(binPkg.location)
                    if not self.allowExtraPackages:
                        raise ExtraPackagesFoundInUpdateError(pkg=binPkg,
                                src=srcPkg, advisory=list(patches)[0])
                else:
                    log.error('could not find advisory for %s' % binPkg)
                    raise NoAdvisoryFoundError(why=binPkg)

            if len(patches) > 1:
                raise MultipleAdvisoriesFoundError(what=srcPkg,
                                                   advisories=patches)

            # len(patches) will only be 0 if there is an exception or the new
            # pkg is not in an updates repository.
            elif len(patches) == 0:
                continue

            patch = patches.pop()
            if patch not in self._cache:
                self._cache[patch] = set()

            self._cache[patch].add(srcPkg)
            self._advisories[patch] = self._mkAdvisory(patch)

    def load(self):
        """
        Parse the required data to generate a mapping of binary package
        object to patch object for a given platform into self._pkgMap.

        Note: This method is meant to be implemented by the backend module
              that inherits from this class.
        """

        log.error('The %s backend does not implement %s'
            % (self.__class__.__name__, 'load'))
        raise NotImplementedError

    def _hasException(self, binPkg):
        """
        Check the config for repositories with exceptions for sending
        advisories. (io. repositories that we generated metadata for.)
        @param binPkg: binary package object
        @type binPkg: repomd.packagexml._Package

        Note: This method is meant to be implemented by the backend module
              that inherits from this class.
        """

        log.error('The %s backend does not implement %s'
            % (self.__class__.__name__, '_hasException'))
        raise NotImplementedError

    def _isUpdatesRepo(self, binPkg):
        """
        Check the repository name. If this package didn't come from a updates
        repository it is probably not security related.
        @param binPkg: binary package object
        @type binPkg: repomd.packagexml._Package

        Note: This method is meant to be implemented by the backend module
              that inherits from this class.
        """

        log.error('The %s backend does not implement %s'
            % (self.__class__.__name__, '_isUpdatesRepo'))
        raise NotImplementedError

    def _checkForDuplicates(self, patchSet):
        """
        Check a set of "patch" objects for duplicates. If there are duplicates
        combine any required information into the first object in the set and
        return True, otherwise return False.

        Note: This method is meant to be implemented by the backend module
              that inherits from this class.
        """

        log.error('The %s backend does not implement %s'
            % (self.__class__.__name__, '_checkForDuplicates'))
        raise NotImplementedError

    def _filterPatch(self, patch):
        """
        Filter out patches that match filters in config.
        @param patch: repomd patch object
        @type patch: repomd.patchxml._Patch
        """

        for _, regex in self._cfg.patchFilter:
            if regex.match(patch.summary):
                return True
            if regex.match(patch.description):
                return True

        return False

    def _mkAdvisory(self, patch):
        """
        Create and populate advisory object for a given package.
        """

        advisory = self._advisoryClass(self._cfg)
        advisory.setSubject(patch.summary)
        advisory.setDescription(patch.description)
        return advisory

    def send(self, trvLst, newTroves):
        """
        Send advisories for all troves in the trvLst.
        @param trvLst: list of packages that have been updated.
        @type trvLst: [((name, version, flavor), srcPkg), ...]
        @param newTroves: list of new troves after the promote
        @type newTroves: [(name, version, flavor), ...]
        """

        newTroveMap = self._mkNewTroveMap(trvLst, newTroves)

        toSend = set()
        for patch, advisory in self._advisories.iteritems():
            binNames = [ x.name for x in patch.packages ]
            for srpm in self._cache[patch]:
                if srpm not in newTroveMap:
                    log.warn('%s not in newTroveMap' % srpm)
                    continue

                # Make sure advisory applies to a package that was promoted.
                toAdvise = [ x for x in newTroveMap[srpm] if x[0] in binNames ]
                if not toAdvise:
                    log.warn('%s does not apply to any published packages of %s'
                             % (advisory, srpm))
                    continue

                advisory.setUpdateTroves(newTroveMap[srpm])
                toSend.add(advisory)

        for advisory in toSend:
            log.info('sending advisory: %s' % advisory)
            advisory.send()

    def _mkNewTroveMap(self, trvLst, newTroves):
        """
        Create a mapping of the elements in trvLst to newTroves.
        @param trvLst: list of packages that have been updated.
        @type trvLst: [((name, version, flavor), srcPkg), ...]
        @param newTroves: list of new troves after the promote
        @type newTroves: [(name, version, flavor), ...]
        @return {trvLstElement: [(n, v, f), ...]}
        """

        res = dict()
        for nvf, srcPkg in trvLst:
            res[srcPkg] = []
            binNames = [ x.name for x in self._pkgSource.srcPkgMap[srcPkg] ]
            for n, v, f in newTroves:
                if n in binNames:
                    res[srcPkg].append((n, v, f))
            if not res[srcPkg]:
                raise NoPackagesFoundForAdvisory(what=(nvf, srcPkg))

        return res

    def _getArchiveUrls(self):
        """
        Compute archive urls to load.
        """

        base = self._cfg.listArchiveBaseUrl
        startDate = self._cfg.listArchiveStartDate
        timeTup = list(time.strptime(startDate, '%Y%m'))

        startYear = timeTup[0]
        endYear = time.localtime()[0]
        endMonth = time.localtime()[1]

        while timeTup[0] <= endYear:
            if timeTup[0] != startYear:
                timeTup[1] = 1

            if timeTup[0] == endYear:
                end = endMonth
            else:
                end = 12

            while timeTup[1] <= end:
                fname = time.strftime('%Y-%B.txt.gz', timeTup)
                yield '/'.join([base, fname])

                timeTup[1] += 1

            timeTup[0] += 1
