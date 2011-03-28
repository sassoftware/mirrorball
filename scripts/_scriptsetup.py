import os
import sys

mirrorballDir = os.path.realpath(os.path.dirname(__file__) + '/..')
sys.path.insert(0, mirrorballDir)
sys.path.insert(0, mirrorballDir + '/include')

if 'CONARY_PATH' in os.environ:
    sys.path.insert(0, os.environ['CONARY_PATH'])

import conary
import updatebot

print >>sys.stderr, 'using conary from', os.path.dirname(conary.__file__)
print >>sys.stderr, 'using updatebot from', os.path.dirname(updatebot.__file__)

from conary.lib import util
sys.excepthook = util.genExcepthook()
