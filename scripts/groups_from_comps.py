#!/usr/bin/python

import sys
import time
import os
mirrorballDir = os.path.abspath('../')
sys.path.insert(0, mirrorballDir)

from collections import namedtuple

from lxml import etree

from conary.lib import util

from conary import versions

from updatebot import bot, config, log

from updatebot import groupmgr

from updatebot import cmdline

logfile = '%s_%s.log' % (sys.argv[0], time.strftime('%Y-%m-%d_%H%M%S'))
log.addRootLogger(logfile)

class GROUP(namedtuple('group', 'name filename bydefault checkpath depcheck')):
    __slots__ = ()

    def toxml(self):
        node = etree.Element('items')
        etree.SubElement(node, 'byDefault').text = self.bydefault
        etree.SubElement(node, 'depCheck').text = self.depcheck
        etree.SubElement(node, 'checkPathConflicts').text = self.checkpath
        etree.SubElement(node, 'filename').text = self.filename
        etree.SubElement(node, 'name').text = self.name
        return node

class PACKAGE(namedtuple('package', 'name flavor use version')):
    __slots__ = ()

    def toxml(self):  
        node = etree.Element('items')
        etree.SubElement(node, 'name').text = self.name
        etree.SubElement(node, 'flavor').text = self.flavor
        etree.SubElement(node, 'use').text = self.use
        etree.SubElement(node, 'version').text = self.version
        return node



class CompsReader(object):

    '''
    Creates a data structure from comps.xml that can 
    be used by factory-managed-group to create conary groups
    '''

    byDefault = {
        # True => "installed"
        'mandatory': True,
        'default': True,
        # False => "optional"
        'optional': False,
        'conditional': False,
    }

    flavorMap = { 
        # x86 Map
        '1#x86:i486:i586:i686' : 'x86',
        '1#x86:~!i486:~!i586:~!i686' : 'x86',
        # x86_64 Map 
        '1#x86_64': 'x86_64'
    }

    depCheckMap = {
        'group-core' : '1',
        'group-critical-path-base' : '1',
        }

    byDefaultMap = {        
        'group-core' : '1',
        'group-critical-path-base' : '1',
        }

    checkPathConflictMap = {        
        'group-core' : '1',
        'group-critical-path-base' : '1',
        }

    def __init__(self, cfg, compsfile=None):
        self.compsfile = compsfile
        self.cfg = config.UpdateBotConfig()
        self.cfg.read(mirrorballDir + '/config/%s/updatebotrc' % cfg)
        self.bot = bot.Bot(self.cfg)
        #self.pkgSource = self.upbot._pkgSource
        #self.pkgSource.load()

        ui = cmdline.UserInterface()

        self.mgr = groupmgr.GroupManager(self.cfg, ui)

        self.label = self.mgr._helper._ccfg.buildLabel
        self.troves = self.mgr._helper._getLatestTroves()
        self.allTroves = self.mgr._helper._repos.getTroveLeavesByLabel({None: {self.label: None}})
        self.group_everything = self.groupEverything(self.troves, self.allTroves)


    def groupEverything(self, troves, allTroves):
        everything = {}
        import itertools
        for k1, k2 in itertools.izip(sorted(troves), sorted(allTroves)):
            assert k1 == k2
            a = troves[k1]
            b = allTroves[k2]
            if not k1.startswith('group-') and len(a.values()[0]) != len(b.values()[0]):
                log.error('unhandled flavor found %s' % k1)
                raise RuntimeError

        for name, vf in troves.iteritems():
            if ':' in name or self.bot._updater._fltrPkg(name):
                continue

            vers = vf.keys()
            assert len(vers) == 1
            vers.sort()
            version = vers[-1]
            flavors = vf[version]
            if version and flavors:
                for flavor in flavors:
                    everything.setdefault(name, set()).add((name, version, flavor))
            else:
                print "Could not find NVFS for %s" % name
        return everything


    def write_xml(self, data, subdir=None):
        if subdir:
            util.mkdirChain(subdir)
            os.chdir(subdir)
        for filename, xml in data.iteritems():
            with open(filename, 'w') as f:
                f.write(xml)        

    def findPkgFromEverything(self, pkg):
        if not self.group_everything:
            self.group_everything = self.groupEverything(self.troves, self.allTroves)
        nvfs = self.group_everything.get(pkg)
        if not nvfs:
            nvfs = set()
            nvfs.add((pkg, None, None))
        return nvfs

    def getEverythingPackageMap(self):
        pkgMap = {}
        pkgList = []
        if not self.group_everything:
            self.group_everything = self.groupEverything(self.troves, self.allTroves)
        for name, nvfs in self.group_everything.iteritems():
            if nvfs:
                pkgList.append((name, self.byDefault.get('optional')))
        if pkgList:
            pkgMap['group-everything'] = pkgList
        return pkgMap

    def getPackageMap(self, groups):
        pkgMap = {} # groupname: [(packagename, byDefault), ...]
        for group in groups:
            grpName = 'group-' + group.find('id').text
            pkgList = []
            for packagelist in group.findall('packagelist'):
                for pkg in packagelist.findall('packagereq'):
                    pkgList.append((pkg.text, self.byDefault.get(pkg.get('type'))))
            if pkgList:
                pkgMap[grpName] = pkgList
        return pkgMap

    def getGroupMap(self, environments, categories):
        grpMap = {} # groupname: [(trovename, byDefault), ...]
        for env in environments + categories:
            envName = 'group-' + env.find('id').text
            grpList = []
            for grouplist in env.findall('grouplist'):
                for grp in grouplist.findall('groupid'):
                    grpList.append(('group-' + grp.text, True))
            for optionlist in env.findall('optionlist'):
                for grp in optionlist.findall('groupid'):
                    grpList.append(('group-' + grp.text, False))
            grpMap[envName] = grpList
        return grpMap

    def createGroupsXml(self, data):
        root = etree.Element('data')
        for grp in data.keys():
            name = grp.replace('.xml', '')
            bydefault = self.byDefaultMap.get(name, '0')
            checkpath = self.checkPathConflictMap.get(name, '0')
            depcheck = self.depCheckMap.get(name, '0')
            group = GROUP(name, grp, bydefault, checkpath, depcheck) 
            root.append(group.toxml())
        return etree.tostring(root, pretty_print=True, 
                        xml_declaration=True, encoding='UTF-8')


    def createPackageXml(self, pkgList):
        root = etree.Element('data')
        for pkg, bydefault in pkgList:
            for name, version, flavor in self.findPkgFromEverything(pkg):
                if not version:
                    print "[WARNING] %s missing from label. probably have to repackage" % name
                    continue
                if hasattr(flavor, 'freeze'):
                    flavor = flavor.freeze()
                if hasattr(version, 'freeze'):
                    version = version.freeze()
                package = PACKAGE(pkg, flavor, self.flavorMap.get(flavor), version)  
                root.append(package.toxml())
        return etree.tostring(root, pretty_print=True, 
                        xml_declaration=True, encoding='UTF-8')

    def createAllXml(self, pkgMap, grpMap):
        data = {}
        for group, packages in pkgMap.iteritems():
            pkgXml = self.createPackageXml(packages)
            if pkgXml.find('items'):
                data.setdefault(group + '.xml', pkgXml)
        
        # FIXME
        # Not sure the factory can handle this format yet
        # should look up groups in data to make sure they exist already
        #for group, groups in grpMap.iteritems():
        #    grpXml = self.createPackageXml(groups)
        #    if grpXml.find('items'):   
        #       data.setdefault(group + '.xml', grpXml)
                
        data.setdefault('groups.xml', self.createGroupsXml(data))
        return data

            
    def read(self, fn):
        r = etree.parse(fn).getroot()
        groups = r.xpath('group')
        environments = r.xpath('environment')
        categories = r.xpath('category')
        # TODO Find a use for langpacks
        langpacks = r.find('langpacks')
        pkgMap = self.getPackageMap(groups)
        pkgMap.update(self.getEverythingPackageMap())
        grpMap = self.getGroupMap(environments, categories)
        data = self.createAllXml(pkgMap, grpMap)
        return data
 
    def write(self, data, subdir=None):
        self.write_xml(data, subdir)

    def main(self, compsfile):
        data = self.read(compsfile)
        self.write(data)

if __name__ == '__main__':
    sys.excepthook = util.genExcepthook()

    cfg = sys.argv[1]
    fn = sys.argv[2]

    comps_reader = CompsReader(cfg)

    #import epdb;epdb.st()

    data = comps_reader.read(fn)

    #import epdb;epdb.st()

    comps_reader.write(data, 'group-os')
