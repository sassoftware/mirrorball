#!/usr/bin/python
#
# Copyright (c) SAS Institute, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


import os
import sys
import cmd
import logging

sys.path.insert(0, os.environ['HOME'] + '/hg/rpath-xmllib')
sys.path.insert(0, os.environ['HOME'] + '/hg/conary')
sys.path.insert(0, os.environ['HOME'] + '/hg/mirrorball')

from conary.build import use
from conary.conaryclient.cmdline import askYn

from rpath_common.xmllib import api1 as xmllib

from repomd import xmlcommon
from repomd import repository

from updatebot import config
from updatebot import conaryhelper
from updatebot import log as logger

logger.addRootLogger()
log = logging.getLogger('logparse')

class _LogXml(xmlcommon.SlotNode):
    pass

class _RecordXml(xmlcommon.SlotNode):

    __slots__ = ('descriptor', 'level', 'message', 'messageId', 'pid', 'time')

    def addChild(self, child):
        n = child.getName()
        if n in ('descriptor', 'level', 'message', 'messageId', 'pid', 'time'):
            setattr(self, n, child.finalize())

    def __repr__(self):
        return '%s\t%s: %s' % (self.level, self.descriptor, self.message)

    def __cmp__(self, other):
        return cmp(self.messageId, other.messageId)

    def __hash__(self):
        return hash((self.descriptor, self.messageId))


class _BuildLogXml(xmlcommon.XmlFileParser):
    def _registerTypes(self):
        self._databinder.registerType(_LogXml, name='log')
        self._databinder.registerType(_RecordXml, name='record')
        self._databinder.registerType(xmllib.StringNode, name='descriptor')
        self._databinder.registerType(xmllib.StringNode, name='level')
        self._databinder.registerType(xmllib.StringNode, name='message')
        self._databinder.registerType(xmllib.IntegerNode, name='messageId')
        self._databinder.registerType(xmllib.IntegerNode, name='pid')
        self._databinder.registerType(xmllib.StringNode, name='time')

    def parse(self):
        data = xmlcommon.XmlFileParser.parse(self)
        return [ x for x in data.iterChildren() ]


class _BaseRecord(object):
    def __init__(self, log, record):
        self.log = log
        self.log._control.append(self)
        for var in _RecordXml.__slots__:
            setattr(self, var, getattr(record, var))

    def __repr__(self):
        return '%s\t%s: %s' % (self.level, self.descriptor, self.message)

    def isParsable(self):
        if '$' in self.message:
            return False
        return True

    def isSupported(self):
        return False

    def getCommand(self):
        return None

    def parseCommand(self):
        return None


class _ScriptActionRecord(_BaseRecord):
    def __str__(self):
        return self.cmd

    def parseCommand(self):
        if not self.getCommand():
            return None

        cmd = []
        for e in self.cmd.split():
            if e == '2>' or e == '>' or '/dev/null' in e:
                break
            cmd.append(e)

        return ' '.join(cmd)


class OwnershipRecord(_ScriptActionRecord):
    def isSupported(self):
        if 'root:root' in self.cmd:
            return False
        elif '--reference' in self.cmd:
            return False
        elif not self.cmd.startswith('chown'):
            return False
        else:
            return True

    def getCommand(self):
        if not self.isSupported():
            return None

        args = []
        kwargs = {}

        recursive = False
        for e in self.cmd.split():
            if e == 'chown':
                continue
            elif e == '-R':
                recursive = True
            elif ':' in e and len(e.split(':')) == 2:
                owner, group = e.split(':')
                args.insert(0, group)
                args.insert(0, owner)
            elif e == '2>' or '/dev/null' in e:
                break
            else:
                if recursive:
                    e = e + '.*'

                args.append(e)

        return args, kwargs



class PermissionRecord(_ScriptActionRecord):
    def isSupported(self):
        if not self.cmd.startswith('chmod'):
            return False
        elif not self.cmd.split()[1].isdigit():
            return False
        elif '--refrence' in self.cmd:
            return False
        elif 'dpkg' in self.cmd:
            return False
        else:
            return True

    def getCommand(self):
        if not self.isSupported():
            return None

        args = []
        kwargs = {}

        mode = None
        for e in self.cmd.split():
            if e == 'chmod':
                continue
            elif e.isdigit():
                mode = int(e)
            elif e == '2>' or '/dev/null' in e:
                break
            else:
                args.append(e)

        if not mode:
            return None

        args.append(mode)
        return args, kwargs


class InitscriptRecord(_ScriptActionRecord):
    def isSupported(self):
        if not self.cmd.startswith('update-rc.d'):
            return False
        elif 'remove' in self.cmd:
            return False
        else:
            return True

    def getCommand(self):
        if not self.isSupported():
            return None

        args = []
        kwargs = {}

        for e in self.cmd.split():
            if e == 'update-rc.d':
                continue
            elif e == '>' or '/dev/null' in e:
                break
            else:
                args.append(e)

        return args, kwargs


class CreateDirectoryRecord(_ScriptActionRecord):
    def getDirectory(self):
        cmd = self.cmd.strip(',')
        index = cmd.find('/')
        return cmd[index:]

    def isSupported(self):
        index = self.cmd.find('mkdir')
        self.cmd = self.cmd[index:]

        if not self.cmd.startswith('mkdir'):
            return False
        else:
            return True

    def getCommand(self):
        if not self.isSupported():
            return None

        args = []
        kwargs = {}

        mode = False
        for e in self.cmd.split():
            if e == 'mkdir':
                continue
            elif e == '-p':
                continue
            elif e == '-m':
                mode = True
            elif mode and e.isdigit():
                kwargs['mode'] = int(mode)
            elif e == '2>' or e == '>' or '/dev/null' in e:
                break
            else:
                args.append(e)

        return args, kwargs


class AlternativesRecord(_ScriptActionRecord):
    def isSupported(self):
        if not self.cmd.startswith('update-alternatives'):
            return False
        elif '--remove' in self.cmd:
            return False
        else:
            return True

    def getCommand(self):
        if not self.isSupported():
            return None

        args = []
        kwargs = {}

        for e in self.cmd.split():
            if e == '>' or e == '2>' or '/dev/null' in e:
                break
            else:
                args.append(e)

        return args, kwargs


class UserInfoRecord(_ScriptActionRecord):
    def isSupported(self):
        cmds = ('adduser', 'useradd', 'groupadd', 'addgroup')
        if not self.cmd.split()[0] in cmds:
            return False
        else:
            return True


class DeviceNodeRecord(_ScriptActionRecord):
    pass


class UnhandledRecord(_ScriptActionRecord):
    pass


def ScriptActionRecord(log, record):
    assert record.message.startswith('warning: ReportScriptActions: ')
    m = record.message[len('warning: ReportScriptActions: '):]
    if '$' in m:
        klass = UnhandledRecord
    elif 'chown' in m:
        klass = OwnershipRecord
    elif 'chmod' in m:
        klass = PermissionRecord
    elif 'update-rc.d' in m:
        klass = InitscriptRecord
    elif 'mkdir' in m:
        klass = CreateDirectoryRecord
    elif 'update-alternatives' in m:
        klass = AlternativesRecord
    elif ('useradd' in m or
          'adduser' in m or
          'groupadd' in m or
          'addgroup' in m):
        klass = UserInfoRecord
    elif 'mknod' in m:
        klass = DeviceNodeRecord
    else:
        klass = UnhandledRecord

    obj = klass(log, record)
    obj.cmd = m
    return obj


class ExcludeDirectoriesRecord(_BaseRecord):
    def getDirectory(self):
        index = self.message.find('/')
        return self.message[index:]

    def isSupported(self):
        if not self.message.startswith('+ ExcludeDirectories: excluding '):
            return False

        message = self.message[len('+ ExcludeDirectories: excluding '):]
        if not message.startswith('empty') and not message.startswith('directory'):
            return False

        self.short = message
        return True

    def getCommand(self):
        if not self.isSupported():
            return None

        blackList = (
            '/dev',
            '/etc/apparmor.d',
            '/lib',
            '/usr/lib',
            '/sbin',
            '/usr/sbin',
            '/bin',
            '/usr/bin',
            '/usr/share/man',
            '/usr/share/consolefonts',
            '/var/lib/pycentral',
            '/usr/lib/locale',
            '/usr/share/perl5',
        )

        args = []
        kwargs = {}

        mode = False
        for e in self.short.split():
            if e == 'empty':
                continue
            elif e == 'directory':
                continue
            elif e == 'with':
                continue
            elif e == 'mode':
                mode = True
            elif mode and e.isdigit():
                kwargs['mode'] = int(e)
            elif e.startswith('/'):
                matches = [ x for x in blackList if e.startswith(x) ]
                if not matches:
                    args.append(e)

        if len(args) == 0:
            return None

        return args, kwargs

    def __str__(self):
        return self.short

    def parseCommand(self):
        cmd = self.getCommand()
        if not cmd:
            return None

        args, kwargs = cmd

        new = 'mkdir '
        if 'mode' in kwargs:
            new += '-m %s' % kwargs['mode']

        for arg in args:
            new += ' %s' % arg

        return new


class BuildLog(object):
    def __init__(self, path, helper):
        assert path.endswith('-xml')

        self._path = path
        self._helper = helper
        self._name = os.path.basename(path)
        self._repository = repository.Repository('file:/')
        self._parser = _BuildLogXml(self._repository, self._path)

        self._data = self._parser.parse()

        self._control = []

    def auditPolicy(self):
        recordFilter = (
            'cook.build.policy.ENFORCEMENT.ReportScriptActions',
            'cook.build.policy.PACKAGE_CREATION.ExcludeDirectories'
        )

        negativeFilter = (
            'Running policy: ReportScriptActions',
            'Running policy: ExcludeDirectories',
            '+ ExcludeDirectories: excluding empty directory /lib',
            '+ ExcludeDirectories: excluding empty directory /usr/lib',
        )

        records = []
        for record in self._data:
            if (record.descriptor in recordFilter and
                record.message not in negativeFilter):
                obj = None
                if record.descriptor == \
                        'cook.build.policy.ENFORCEMENT.ReportScriptActions':
                    obj = ScriptActionRecord(self, record)
                elif record.descriptor == \
                        'cook.build.policy.PACKAGE_CREATION.ExcludeDirectories':
                    if record.message.startswith('+ ExcludeDirectories: excluding'):
                        obj = ExcludeDirectoriesRecord(self, record)
                if obj:
                    records.append(obj)
        return records

    def getControl(self):
        valid = [ x.parseCommand() for x in self._control if x.getCommand() ]

        if not valid:
            return ''

        ret = '\n'.join(valid)
        ret += '\n'
        return ret

    def _getPkgName(self):
        slice = self._name.split('-')
        return '-'.join(slice[:-2])

    def writeControl(self):
        pkgName = self._getPkgName()
        log.info('writing control file for %s' % pkgName)

        recipeDir = self._helper._checkout(pkgName)
        control = self.getControl()
        if not control and os.path.exists(os.path.join(recipeDir, 'control')):
            self._helper._removeFile(recipeDir, 'control')
        if control:
            fd = open(os.path.join(recipeDir, 'control'), 'w')
            fd.write(control)
            fd.close()
            self._helper._addFile(recipeDir, 'control')

        use.setBuildFlagsFromFlavor(pkgName, self._helper._ccfg.buildFlavor,
                                    error=False)

        self._helper._commit(recipeDir, 'add/update control file')

    def __repr__(self):
        return self._name

    def __cmp__(self, other):
        return cmp(self._name, other._name)


class BuildLogAnalyzer(object):
    def __init__(self, directory, helper):
        self._logDir = os.path.abspath(directory)
        self._helper = helper

        self._logFiles = []
        for logfile in os.listdir(self._logDir):
            if logfile.endswith('-xml'):
                path = os.path.join(self._logDir, logfile)
                self._logFiles.append(BuildLog(path, helper))
        self._logFiles.sort()

        self._buckets = {}

    def auditPolicy(self):
        new = True

        numPkgs = [ x for x in self._logFiles if x.auditPolicy() ]
        print ("Found %s of %s packages with policy errors"
               % (len(numPkgs), len(self._logFiles)))

        prompt = 80 * '=' + '\n' + 'Repeat Log Data? (y/N): '

        for logObj in self._logFiles:
            while new or askYn(prompt):
                new = False

                records = logObj.auditPolicy()
                if not records:
                    break

                print 'Package: ', logObj
                for rec in records:
                    print rec

            new = True

    def makeBuckets(self):
        for logObj in self._logFiles:
            for record in logObj.auditPolicy():
                key = record.__class__.__name__
                if key not in self._buckets:
                    self._buckets[key] = []
                self._buckets[key].append(record)

    def findPathConflicts(self):
        d = {}
        for record in (self._buckets['ExcludeDirectoriesRecord'] +
                       self._buckets['CreateDirectoryRecord']):
            if not record.isParsable():
                continue
            key = record.getDirectory()
            if key not in d:
                d[key] = set()
            d[key].add(record.log)

        for key, value in d.iteritems():
            if len(value) > 1:
                print ('Found path conflict (%s) between the following '
                       'packages: %s' % (key, ', '.join(map(str, value))))

    def writeControl(self):
        for logObj in self._logFiles:
            lobObj.writeControl()


if __name__ == '__main__':
    import sys
    from conary.lib import util
    sys.excepthook = util.genExcepthook()

    cfg = config.UpdateBotConfig()
    cfg.read(os.environ['HOME'] + '/hg/mirrorball/config/ubuntu/updatebotrc')

    helper = conaryhelper.ConaryHelper(cfg)

    obj = BuildLogAnalyzer(sys.argv[1], helper)
#    obj.auditPolicy()
    obj.makeBuckets()
#    obj.findPathConflicts()

    #for logObj in obj._logFiles:
    #    print 80 * '='
    #    print 'Package:', logObj
    #    print logObj.getControl()
    #    logObj.writeControl()

    import epdb; epdb.st()
