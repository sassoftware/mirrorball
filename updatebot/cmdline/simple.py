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
