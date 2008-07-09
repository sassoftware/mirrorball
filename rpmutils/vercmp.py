#!/usr/bin/python

def _rpmversplit(s):
    l = []
    isNumericHunk = s[0].isdigit()

    i = 1
    start = 0


    while i < len(s):
        if not s[i].isalnum():
            l.append(s[start:i])
            start = i + 1
        elif isNumericHunk != s[i].isdigit():
            l.append(s[start:i])
            start = i

        i += 1

    l.append(s[start:i])

    # filter out empty strings
    return [ x for x in l if x ]

def rpmvercmp(ver1string, ver2string):

    ver1list = _rpmversplit(ver1string)
    ver2list = _rpmversplit(ver2string)

    while ver1list or ver2list:
        if not ver1list:
            return -1
        elif not ver2list:
            return 1

        v1 = ver1list.pop(0)
        v2 = ver2list.pop(0)

        if v1.isdigit() and v2.isdigit():
            v1 = int(v1)
            v2 = int(v2)
        elif v1.isdigit() and not v2.isdigit():
            # numbers are newer than letters
            return 1
        elif not v1.isdigit() and v2.isdigit():
            return -1

        if v1 < v2:
            return -1
        elif v1 > v2:
            return 1

    return 0

if __name__ == '__main__':
    def _test(a, b, expected):
        result = rpmvercmp(a, b)
        if result == -1:
            print a, '<', b
        elif result == 1:
            print a, '>', b
        else:
            print a, '==', b
        assert(result == expected)

    _test('1', '1', 0)
    _test('1', '2', -1)
    _test('2', '1', 1)
    _test('a', 'a', 0)
    _test('a', 'b', -1)
    _test('b', 'a', 1)
    _test('1.2', '1.3', -1)
    _test('1.3', '1.1', 1)
    _test('1.a', '1.a', 0)
    _test('1.a', '1.b', -1)
    _test('1.b', '1.a', 1)
    _test('1.2+', '1.2', 0)
    _test('1.0010', '1.0', 1)
    _test('1.05', '1.5', 0)
    _test('1.0', '1', 1)
    _test('2.50', '2.5', 1)
    _test('fc4', 'fc.4', 0)
    _test('FC5', 'fc5', -1)
    _test('2a', '2.0', -1)
    _test('1.0', '1.fc4', 1)
    _test('3.0.0_fc', '3.0.0.fc', 0)
    _test('1++', '1_', 0)
    _test('+', '_', -1)
    _test('_', '+', -1)
