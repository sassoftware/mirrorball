#!/usr/bin/python2.4
# -*- mode: python -*-
#
# Copyright (c) 2006-2007 rPath, Inc.  All Rights Reserved.
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
"""
Mock object implementation.

This mock object implementation is meant to be very forgiving - it returns a
new child Mock Object for every attribute accessed, and a mock object is
returned from every method call.

It is the tester's job to enabled the calls that they are interested in
testing, all calls where the return value of the call and side effects are not
recorded (logging, for example) are likely to succeed w/o effort.

If you wish to call the actual implementation of a function on a MockObject,
you have to enable it using enableMethod.  If you wish to use an actual variable setting, you need to set it.

All enabling/checking methods for a MockObject are done through the _mock attribute.  Example:

class Foo(object):
    def __init__(self):
        # NOTE: this initialization is not called by default with the mock
        # object.
        self.one = 'a'
        self.two = 'b'

    def method(self, param):
        # this method is enabled by calling _mock.enableMethod
        param.bar('print some data')
        self.printMe('some other data', self.one)
        return self.two

    def printMe(self, otherParam):
        # this method is not enabled and so is stubbed out in the MockInstance.
        print otherParam

def test():
    m = MockInstance(Foo)
    m._mock.set(two=123)
    m._mock.enableMethod('method')
    param = MockObject()
    rv = m.method(param)
    assert(rv == 123) #m.two is returned
    # note that param.bar is created on the fly as it is accessed, and 
    # stores how it was called.
    assert(param.bar._mock.assertCalled('print some data')
    # m.one and m.printMe were created on the fly as well
    # m.printMe remembers how it was called.
    m.printMe._mock.assertCalled('some other data', m.one)
    # attribute values are generated on the fly but are retained between
    # accesses.
    assert(m.foo is m.foo)

TODO: set the return values for particular function calls w/ particular
parameters.
"""
import new

_mocked = []

class MockObject(object):
    """
        Base mock object.

        Creates attributes on the fly, affect attribute values by using
        the _mock attribute, which is a MockManager.

        Initial attributes can be assigned by key/value pairs passed in.
    """

    def __init__(self, **kw):
        stableReturnValues = kw.pop('stableReturnValues', False)
        self._mock = MockManager(self, stableReturnValues=stableReturnValues)
        self.__dict__.update(kw)
        self._mock._dict = {}

    def __getattribute__(self, key):
        if key == '_mock' or self._mock.enabled(key):
            return object.__getattribute__(self, key)
        if key in self.__dict__:
            return self.__dict__[key]
        m = self._mock.getCalled(key)
        self.__dict__[key] = m
        return m

    def __setattr__(self, key, value):
        if key == '_mock' or self._mock.enabled(key):
            object.__setattr__(self, key, value)
        else:
            m = self._mock.setCalled(key, value)
            if not hasattr(self, key):
                object.__setattr__(self, key, m)

    def __setitem__(self, key, value):
        m = self._mock.setItemCalled(key, value)
        self._mock._dict[key] = m

    def __len__(self):
        return self._mock.length

    def __deepcopy__(self, memo):
        return self

    def __iter__(self):
        for i in range(len(self)):
            yield self[i]

    def __getitem__(self, key):
        if key in self._mock._dict:
            return self._mock._dict[key]
        else:
            m = self._mock.getItemCalled(key)
            self._mock._dict[key] = m
            return m

    def __hasattr__(self, key):
        if key == '_mock' or self._mock.enabled(key):
            return object.__hasattr__(self, key)
        return True

    def __call__(self, *args, **kw):
        return self._mock.called(args, kw)

class MockManager(object):
    noReturnValue = object()

    def __init__(self, obj, stableReturnValues=False):
        self._enabledByDefault = False
        self._enabled = set(['__dict__', '__methods__', '__class__',
                             '__members__', '__deepcopy__'])
        self._disabled = set([])
        self._errorToRaise = None
        self.calls = []
        self.callReturns = []
        self.getCalls = []
        self.setCalls = []
        self.getItemCalls = []
        self.setItemCalls = []
        self.hasCalls = []
        self.eqCalls = []
        self.obj = obj
        self.superClass = object
        self.length = 1
        self.stableReturnValues = stableReturnValues
        self.returnValue = self.noReturnValue

    def enableByDefault(self):
        self._enabledByDefault = True

    def disableByDefault(self):
        self._enabledByDefault = False

    def setDefaultReturn(self, returnValue):
        self.returnValue = returnValue

    def setReturn(self, returnValue, *args, **kw):
        self.callReturns.append((args, tuple(sorted(kw.items())), returnValue))

    def enableMethod(self, name):
        """
            Enables a method to be called from the given superclass.

            The function underlying the method is slurped up and assigned to 
            this class.
        """
        self.enable(name)
        func = getattr(self.superClass, name).im_func
        method = new.instancemethod(func, self.obj, self.obj.__class__)
        object.__setattr__(self.obj, name, method)

    def enable(self, *names):
        self._enabled.update(names)
        self._disabled.difference_update(names)

    def disable(self, *names):
        self._enabled.difference_update(names)
        self._disabled.update(names)
        for name in names:
            object.__setattr__(self.obj, name, MockObject())

    def enabled(self, name):
        if self._enabledByDefault:
            return name not in self._disabled
        else:
            return name in self._enabled

    def set(self, **kw):
        for key, value in kw.iteritems():
            self._enabled.add(key)
            setattr(self.obj, key, value)

    def raiseErrorOnAccess(self, error):
        self._errorToRaise = error

    def assertCalled(self, *args, **kw):
        kw = tuple(sorted(kw.items()))
        assert((args, kw) in self.calls)
        self.calls.remove((args, kw))

    def assertNotCalled(self, *args, **kw):
        assert(not self.calls)

    def setCalled(self, key, value):
        if self._errorToRaise:
            self._raiseError()
        m = MockObject()
        self.setCalls.append((key, value, m))
        return m

    def setItemCalled(self, key, value):
        if self._errorToRaise:
            self._raiseError()
        m = MockObject()
        self.setItemCalls.append((key, value, m))
        return m


    def _raiseError(self):
        err = self._errorToRaise
        self._errorToRaise = None
        raise err

    def getCalled(self, key):
        if self._errorToRaise:
            self._raiseError()
        m = MockObject(stableReturnValues=self.stableReturnValues)
        self.getCalls.append((key, m))
        return m

    def getItemCalled(self, key):
        if self._errorToRaise:
            self._raiseError()
        m = MockObject(stableReturnValues=self.stableReturnValues)
        self.getItemCalls.append((key, m))
        return m


    def called(self, args, kw):
        kw = tuple(sorted(kw.items()))
        self.calls.append((args, kw))
        if self._errorToRaise:
            self._raiseError()
        else:
            rv = [x[2] for x in self.callReturns if (x[0], x[1]) == (args, kw)]
            if rv:
                return rv[-1]
            rv = [x[2] for x in self.callReturns 
                  if not x[0] and x[1] == (('_mockAll', True),)]
            if rv:
                return rv[-1]
            else:
                if self.returnValue is not self.noReturnValue:
                    return self.returnValue
                if self.stableReturnValues:
                    self.returnValue = MockObject(stableReturnValues=True)
                    return self.returnValue
                return MockObject()

    def getCalls(self):
        return self.calls

    def popCall(self):
        call =  self.calls[0]
        self.calls = self.calls[1:]
        return call

class MockInstance(MockObject):

    def __init__(self, superClass, **kw):
        MockObject.__init__(self, **kw)
        self._mock.superClass = superClass

def attach(obj):
    if hasattr(obj, '__setattr__'):
        oldsetattr = obj.__setattr__
    if hasattr(obj, '__getattribute__'):
        oldgetattr = obj.__getattribute__

    def __setattr__(self, key, value):
        if not isinstance(getattr(self, key), mock.MockObject()):
            oldsetattr(key, value)

    def __getattribute__(self, key):
        if not hasattr(self, key):
            oldsetattr(key, mock.MockObject())
        return oldgetattr(key)
    oldsetattr('__setattr__', new.instancemethod(__setattr__, obj,
                                                 obj.__class__))
    oldsetattr('__getattribute__', new.instancemethod(__getattribute__, obj, obj.__class__))

def mockMethod(method):
    self = method.im_self
    name = method.__name__
    origMethod = getattr(self, name)
    setattr(self, name, MockObject())
    getattr(self, name)._mock.method = origMethod
    getattr(self, name)._mock.origValue = origMethod
    _mocked.append((self, name))
    return getattr(self, name)

def mock(obj, attr):
    m = MockObject()
    if hasattr(obj, attr):
        m._mock.origValue = getattr(obj, attr)
    setattr(obj, attr, m)
    _mocked.append((obj, attr))

def unmockAll():
    for obj, attr in _mocked:
        if not hasattr(getattr(obj, attr), '_mock'):
            continue
        setattr(obj, attr, getattr(obj, attr)._mock.origValue)
    _mocked[:] = []

def mockClass(class_, *args, **kw):
    commands = []
    runInit = kw.pop('mock_runInit', False)
    for k, v in kw.items():
        if k.startswith('mock_'):
            if not isinstance(v, (list, tuple)):
                v = [v]
            commands.append((k[5:], v))
            kw.pop(k)
    class _MockClass(MockInstance, class_):
        def __init__(self, *a, **k):
            MockInstance.__init__(self, class_, *args, **kw)
            if runInit:
                self._mock.enableByDefault()
                class_.__init__(self, *a, **k)
            self._mock.called(a, k)
            for command, params in commands:
                getattr(self._mock, command)(*params)

    return _MockClass

def mockFunctionOnce(obj, attr, returnValue):
    newFn = lambda *args, **kw: returnValue
    return replaceFunctionOnce(obj, attr, newFn)

def replaceFunctionOnce(obj, attr, newFn):
    curValue = getattr(obj, attr)
    def restore():
        setattr(obj, attr, curValue)

    def fun(*args, **kw):
        restore()
        return newFn(*args, **kw)
    setattr(obj, attr, fun)
    fun.func_name = attr
    fun.restore = restore
