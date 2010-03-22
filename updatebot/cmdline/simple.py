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

import os

from updatebot import log
from updatebot import config

def validatePlatform(platform, configDir):
    validPlatforms = os.listdir(configDir)
    if platform not in validPlatforms:
        print ('Invalid platform %s... Please select from the following '
            'available platforms %s' % (platform, ', '.join(validPlatforms)))
        return False
    return True

def usage(argv):
    print 'usage: %s <platform name> [logfile]' % argv[0]
    return 1

def main(argv, workerFunc, configDir='/etc/mirrorball', enableLogging=True):
    if len(argv) < 2 or len(argv) > 3:
        return usage(argv)

    logFile = None
    if len(argv) == 3:
        logFile = argv[2]

    if enableLogging:
        log.addRootLogger(logFile=logFile)

    platform = argv[1]
    if not validatePlatform(platform, configDir):
        return 1


    cfg = config.UpdateBotConfig()
    cfg.read(os.path.join(configDir, platform, 'updatebotrc'))

    rc = workerFunc(cfg)
    return rc
