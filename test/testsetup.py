import os
import sys
dirlevel = 0;
curDir = os.path.dirname(__file__)
testsuitePath = os.path.realpath(curDir + '/..' * dirlevel)
while (not os.path.exists(testsuitePath + '/testsuite.py') and dirlevel < 10):
    dirlevel+=1
    testsuitePath = os.path.realpath(curDir + '/..' * dirlevel)

if dirlevel == 10:
    raise RuntimeError('Could not find testsuite.py!')
if not testsuitePath in sys.path:
    sys.path.insert(0, testsuitePath)

import testsuite
testsuite.setup()

def main():
    if sys._getframe(1).f_globals['__name__'] == '__main__':
        testsuite.main()
