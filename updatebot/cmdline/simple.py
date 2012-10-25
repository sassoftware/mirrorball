#
# Copyright (c) rPath, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
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
