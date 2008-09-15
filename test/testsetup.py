import os
import sys


curDir = os.path.dirname(__file__)
for dirlevel in range(10):
    testsuitePath = os.path.realpath(curDir + '/..' * dirlevel)
    if os.path.exists(testsuitePath + '/testsuite.py'):
        break
else:
    raise RuntimeError('Could not find testsuite.py!')
if not testsuitePath in sys.path:
    sys.path.insert(0, testsuitePath)


import testsuite
testsuite.setup()


def main():
    if sys._getframe(1).f_globals['__name__'] == '__main__':
        testsuite.main()
