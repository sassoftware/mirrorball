#
# Copyright (c) 2008 rPath, Inc.
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

import testsetup

import mock
import slehelp

from updatebot import util
from updatebot import errors
from updatebot import update

class UpdateTest(slehelp.Helper):
    def testGetUpdates(self):
        mockRpmSource = mock.MockObject(stableReturnValues=True)
        updater = update.Updater(self.updateBotCfg, mockRpmSource)

        updateTrove = (('foo:source', None, None), mock.MockObject())
        adviseTrove = (('bar:source', None, None), mock.MockObject())

        mockFindUpdatableTroves = mock.MockObject(stableReturnValues=True)
        mockFindUpdatableTroves._mock.setReturn([updateTrove, adviseTrove],
                                                self.updateBotCfg.topGroup)
        self.mock(updater, '_findUpdatableTroves', mockFindUpdatableTroves)

        mockSanitizeTrove = mock.MockObject(stableReturnValues=True)
        mockSanitizeTrove._mock.setReturn(True, *updateTrove)
        mockSanitizeTrove._mock.setReturn(False, *adviseTrove)
        self.mock(updater, '_sanitizeTrove', mockSanitizeTrove)

        toAdvise, toUpdate = updater.getUpdates()
        self.failUnlessEqual(len(toAdvise), 2)
        self.failUnless(updateTrove in toAdvise)
        self.failUnless(adviseTrove in toAdvise)
        self.failUnlessEqual(len(toUpdate), 1)
        self.failUnless(updateTrove in toUpdate)
        mockFindUpdatableTroves._mock.assertCalled(self.updateBotCfg.topGroup)
        mockSanitizeTrove._mock.assertCalled(*updateTrove)
        mockSanitizeTrove._mock.assertCalled(*adviseTrove)

    def testFindUpdatableTroves(self):
        trvSpec = ('group-foo', 'foo.rpath.com@rpath:foo-devel', None)
        mockRpmSource = mock.MockObject(stableReturnValues=True)
        updater = update.Updater(self.updateBotCfg, mockRpmSource)

        mockFooVersion = mock.MockObject(stableReturnValues=True)
        mockBarVersion = mock.MockObject(stableReturnValues=True)
        mockBazVersion = mock.MockObject(stableReturnValues=True)

        mockFooRevision = mock.MockObject(stableReturnValues=True)
        mockBarRevision = mock.MockObject(stableReturnValues=True)
        mockBazRevision = mock.MockObject(stableReturnValues=True)

        mockFooVersion.trailingRevision._mock.setReturn(mockFooRevision)
        mockBarVersion.trailingRevision._mock.setReturn(mockBarRevision)
        mockBazVersion.trailingRevision._mock.setReturn(mockBazRevision)

        troves = [('info-foo:source', None, None),
                  ('group-foo:source', None, None),
                  ('foo:source', mockFooVersion, None),
                  ('bar:source', mockBarVersion, None),
                  ('baz:source', mockBazVersion, None)]

        mockConaryHelper = mock.MockObject(stableReturnValues=True)
        mockConaryHelper.getSourceTroves._mock.setReturn(troves, trvSpec)
        self.mock(updater, '_conaryhelper', mockConaryHelper)

        mockFooSrpm = mock.MockObject(stableReturnValues=True)
        mockBarSrpm = mock.MockObject(stableReturnValues=True)
        mockBazSrpm = mock.MockObject(stableReturnValues=True)

        mockGetLatestSource = mock.MockObject(stableReturnValues=True)
        mockGetLatestSource._mock.setReturn(mockFooSrpm, 'foo')
        mockGetLatestSource._mock.setReturn(mockBarSrpm, 'bar')
        mockGetLatestSource._mock.setReturn(mockBazSrpm, 'baz')
        self.mock(updater, '_getLatestSource', mockGetLatestSource)

        mockSrpmToConaryVersion = mock.MockObject(stableReturnValues=True)
        self.mock(util, 'srpmToConaryVersion', mockSrpmToConaryVersion)

        # srpm is newer than conary repo
        mockFooRevision._mock.set(version='0')
        mockSrpmToConaryVersion._mock.setReturn('1', mockFooSrpm)

        # srpm is same as conary repo
        mockBarRevision._mock.set(version='2')
        mockSrpmToConaryVersion._mock.setReturn('2', mockBarSrpm)

        # srpm is older than conary repo
        mockBazRevision._mock.set(version='4')
        mockSrpmToConaryVersion._mock.setReturn('3', mockBazSrpm)

        expectedResult = [(('foo', mockFooVersion, None), mockFooSrpm),
                          (('baz', mockBazVersion, None), mockBazSrpm)]

        result = updater._findUpdatableTroves(trvSpec)
        self.failUnlessEqual(result, expectedResult)
        mockConaryHelper.getSourceTroves._mock.assertCalled(trvSpec)
        mockGetLatestSource._mock.assertCalled('foo')
        mockGetLatestSource._mock.assertCalled('bar')
        mockGetLatestSource._mock.assertCalled('baz')
        mockSrpmToConaryVersion._mock.assertCalled(mockFooSrpm)
        mockSrpmToConaryVersion._mock.assertCalled(mockBarSrpm)
        mockSrpmToConaryVersion._mock.assertCalled(mockBazSrpm)
        mockFooVersion.trailingRevision._mock.assertCalled()
        mockBarVersion.trailingRevision._mock.assertCalled()
        mockBazVersion.trailingRevision._mock.assertCalled()

    def testGetLatestSource(self):
        mockRpmSource = mock.MockObject(stableReturnValues=True)
        updater = update.Updater(self.updateBotCfg, mockRpmSource)

        mockPackageVerCmp = mock.MockObject()
        self.mock(util, 'packagevercmp', mockPackageVerCmp)

        mockList = mock.MockObject(stableReturnValues=True)
        mockList.sort._mock.setReturn(None, mockPackageVerCmp)
        mockList[-1] = None
        mockElement = mockList[-1]

        mockRpmSource._mock.set(srcNameMap={'foo': mockList})

        result = updater._getLatestSource('foo')
        self.failUnless(result is mockElement)
        mockList.sort._mock.assertCalled(mockPackageVerCmp)

    def testSanitizeTrove(self):
        trvSpec = ('foo', None, None)
        mockRpmSource = mock.MockObject(stableReturnValues=True)
        updater = update.Updater(self.updateBotCfg, mockRpmSource)

        newBinPkg1 = mock.MockObject(stableReturnValues=True)
        newBinPkg2 = mock.MockObject(stableReturnValues=True)

        newBinPkg1._mock.set(name='foo')
        newBinPkg2._mock.set(name='foo-devel')

        oldBinPkg1 = mock.MockObject(stableReturnValues=True)
        oldBinPkg2 = mock.MockObject(stableReturnValues=True)

        oldBinPkg1._mock.set(name='foo')
        oldBinPkg2._mock.set(name='foo-devel')

        newSrcPkg = mock.MockObject()
        oldSrcPkg = mock.MockObject()

        srcPkgMap = {newSrcPkg: [newBinPkg1, newBinPkg2]}
        locationMap = {'a': oldBinPkg1, 'b': oldBinPkg2}
        binPkgMap = {oldBinPkg1: oldSrcPkg, oldBinPkg2: oldSrcPkg}

        mockRpmSource._mock.set(srcPkgMap=srcPkgMap)
        mockRpmSource._mock.set(locationMap=locationMap)
        mockRpmSource._mock.set(binPkgMap=binPkgMap)

        mockRecipeMaker = mock.MockObject(stableReturnValues=True)
        mockRecipeMaker.getManifest._mock.setReturn(['a', 'b'], 'foo')
        self.mock(updater, '_recipeMaker', mockRecipeMaker)

        mockPackageVerCmp = mock.MockObject(stableReturnValue=True)
        self.mock(util, 'packagevercmp', mockPackageVerCmp)

        # need to update repository
        mockPackageVerCmp._mock.setReturn(1, newSrcPkg, oldSrcPkg)
        result1 = updater._sanitizeTrove(trvSpec, newSrcPkg)
        self.failUnlessEqual(result1, True)
        mockRecipeMaker.getManifest._mock.assertCalled('foo')
        mockPackageVerCmp._mock.assertCalled(newSrcPkg, oldSrcPkg)
        mockPackageVerCmp._mock.assertCalled(newSrcPkg, oldSrcPkg)

        # only need to send advisory
        mockPackageVerCmp._mock.setReturn(0, newSrcPkg, oldSrcPkg)
        result1 = updater._sanitizeTrove(trvSpec, newSrcPkg)
        self.failUnlessEqual(result1, False)
        mockRecipeMaker.getManifest._mock.assertCalled('foo')
        mockPackageVerCmp._mock.assertCalled(newSrcPkg, oldSrcPkg)
        mockPackageVerCmp._mock.assertCalled(newSrcPkg, oldSrcPkg)

        # test update goes backwards exception
        mockPackageVerCmp._mock.setReturn(-1, newSrcPkg, oldSrcPkg)
        self.failUnlessRaises(errors.UpdateGoesBackwardsError,
            updater._sanitizeTrove, trvSpec, newSrcPkg)
        mockRecipeMaker.getManifest._mock.assertCalled('foo')
        mockPackageVerCmp._mock.assertCalled(newSrcPkg, oldSrcPkg)
        mockPackageVerCmp._mock.assertCalled(newSrcPkg, oldSrcPkg)

        # test remove package exception
        oldBinPkg2._mock.set(name='bar')
        mockPackageVerCmp._mock.setReturn(1, newSrcPkg, oldSrcPkg)
        self.failUnlessRaises(errors.UpdateRemovesPackageError,
            updater._sanitizeTrove, trvSpec, newSrcPkg)
        mockRecipeMaker.getManifest._mock.assertCalled('foo')
        mockPackageVerCmp._mock.assertCalled(newSrcPkg, oldSrcPkg)
        mockPackageVerCmp._mock.assertCalled(newSrcPkg, oldSrcPkg)


testsetup.main()