# Copyright 2017 The Abseil Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Adds support for parameterized tests to Python's unittest TestCase class.

A parameterized test is a method in a test case that is invoked with different
argument tuples.

A simple example::

    class AdditionExample(parameterized.TestCase):
      @parameterized.parameters(
        (1, 2, 3),
        (4, 5, 9),
        (1, 1, 3))
      def testAddition(self, op1, op2, result):
        self.assertEqual(result, op1 + op2)

Each invocation is a separate test case and properly isolated just
like a normal test method, with its own setUp/tearDown cycle. In the
example above, there are three separate testcases, one of which will
fail due to an assertion error (1 + 1 != 3).

Parameters for individual test cases can be tuples (with positional parameters)
or dictionaries (with named parameters)::

    class AdditionExample(parameterized.TestCase):
      @parameterized.parameters(
        {'op1': 1, 'op2': 2, 'result': 3},
        {'op1': 4, 'op2': 5, 'result': 9},
      )
      def testAddition(self, op1, op2, result):
        self.assertEqual(result, op1 + op2)

If a parameterized test fails, the error message will show the
original test name and the parameters for that test.

The id method of the test, used internally by the unittest framework, is also
modified to show the arguments (but note that the name reported by `id()`
doesn't match the actual test name, see below). To make sure that test names
stay the same across several invocations, object representations like::

    >>> class Foo(object):
    ...  pass
    >>> repr(Foo())
    '<__main__.Foo object at 0x23d8610>'

are turned into ``__main__.Foo``. When selecting a subset of test cases to run
on the command-line, the test cases contain an index suffix for each argument
in the order they were passed to :func:`parameters` (eg. testAddition0,
testAddition1, etc.) This naming scheme is subject to change; for more reliable
and stable names, especially in test logs, use :func:`named_parameters` instead.

Tests using :func:`named_parameters` are similar to :func:`parameters`, except
only tuples or dicts of args are supported. For tuples, the first parameter arg
has to be a string (or an object that returns an apt name when converted via
``str()``). For dicts, a value for the key ``testcase_name`` must be present and
must be a string (or an object that returns an apt name when converted via
``str()``)::

    class NamedExample(parameterized.TestCase):
      @parameterized.named_parameters(
        ('Normal', 'aa', 'aaa', True),
        ('EmptyPrefix', '', 'abc', True),
        ('BothEmpty', '', '', True))
      def testStartsWith(self, prefix, string, result):
        self.assertEqual(result, string.startswith(prefix))

    class NamedExample(parameterized.TestCase):
      @parameterized.named_parameters(
        {'testcase_name': 'Normal',
          'result': True, 'string': 'aaa', 'prefix': 'aa'},
        {'testcase_name': 'EmptyPrefix',
          'result': True, 'string': 'abc', 'prefix': ''},
        {'testcase_name': 'BothEmpty',
          'result': True, 'string': '', 'prefix': ''})
      def testStartsWith(self, prefix, string, result):
        self.assertEqual(result, string.startswith(prefix))

Named tests also have the benefit that they can be run individually
from the command line::

    $ testmodule.py NamedExample.testStartsWithNormal
    .
    --------------------------------------------------------------------
    Ran 1 test in 0.000s

    OK

Parameterized Classes
=====================

If invocation arguments are shared across test methods in a single
TestCase class, instead of decorating all test methods
individually, the class itself can be decorated::

    @parameterized.parameters(
      (1, 2, 3),
      (4, 5, 9))
    class ArithmeticTest(parameterized.TestCase):
      def testAdd(self, arg1, arg2, result):
        self.assertEqual(arg1 + arg2, result)

      def testSubtract(self, arg1, arg2, result):
        self.assertEqual(result - arg1, arg2)

Inputs from Iterables
=====================

If parameters should be shared across several test cases, or are dynamically
created from other sources, a single non-tuple iterable can be passed into
the decorator. This iterable will be used to obtain the test cases::

    class AdditionExample(parameterized.TestCase):
      @parameterized.parameters(
        c.op1, c.op2, c.result for c in testcases
      )
      def testAddition(self, op1, op2, result):
        self.assertEqual(result, op1 + op2)


Single-Argument Test Methods
============================

If a test method takes only one argument, the single arguments must not be
wrapped into a tuple::

    class NegativeNumberExample(parameterized.TestCase):
      @parameterized.parameters(
        -1, -3, -4, -5
      )
      def testIsNegative(self, arg):
        self.assertTrue(IsNegative(arg))


List/tuple as a Single Argument
===============================

If a test method takes a single argument of a list/tuple, it must be wrapped
inside a tuple::

    class ZeroSumExample(parameterized.TestCase):
      @parameterized.parameters(
        ([-1, 0, 1], ),
        ([-2, 0, 2], ),
      )
      def testSumIsZero(self, arg):
        self.assertEqual(0, sum(arg))


Cartesian product of Parameter Values as Parametrized Test Cases
================================================================

If required to test method over a cartesian product of parameters,
`parameterized.product` may be used to facilitate generation of parameters
test combinations::

    class TestModuloExample(parameterized.TestCase):
      @parameterized.product(
          num=[0, 20, 80],
          modulo=[2, 4],
          expected=[0]
      )
      def testModuloResult(self, num, modulo, expected):
        self.assertEqual(expected, num % modulo)

This results in 6 test cases being created - one for each combination of the
parameters. It is also possible to supply sequences of keyword argument dicts
as elements of the cartesian product::

    @parameterized.product(
        (dict(num=5, modulo=3, expected=2),
         dict(num=7, modulo=4, expected=3)),
        dtype=(int, float)
    )
    def testModuloResult(self, num, modulo, expected, dtype):
      self.assertEqual(expected, dtype(num) % modulo)

This results in 4 test cases being created - for each of the two sets of test
data (supplied as kwarg dicts) and for each of the two data types (supplied as
a named parameter). Multiple keyword argument dicts may be supplied if required.

Async Support
=============

If a test needs to call async functions, it can inherit from both
parameterized.TestCase and another TestCase that supports async calls, such
as [asynctest](https://github.com/Martiusweb/asynctest)::

  import asynctest

  class AsyncExample(parameterized.TestCase, asynctest.TestCase):
    @parameterized.parameters(
      ('a', 1),
      ('b', 2),
    )
    async def testSomeAsyncFunction(self, arg, expected):
      actual = await someAsyncFunction(arg)
      self.assertEqual(actual, expected)
"""

from collections import abc
import functools
import inspect
import itertools
import re
import types
import unittest

from absl.testing import absltest


_ADDR_RE = re.compile(r'\<([a-zA-Z0-9_\-\.]+) object at 0x[a-fA-F0-9]+\>')
_NAMED = object()
_ARGUMENT_REPR = object()
_NAMED_DICT_KEY = 'testcase_name'


class NoTestsError(Exception):
  """Raised when parameterized decorators do not generate any tests."""


class DuplicateTestNameError(Exception):
  """Raised when a parameterized test has the same test name multiple times."""

  def __init__(self, test_class_name, new_test_name, original_test_name):
    super(DuplicateTestNameError, self).__init__(
        'Duplicate parameterized test name in {}: generated test name {!r} '
        '(generated from {!r}) already exists. Consider using '
        'named_parameters() to give your tests unique names and/or renaming '
        'the conflicting test method.'.format(
            test_class_name, new_test_name, original_test_name))


def _clean_repr(obj):
  return _ADDR_RE.sub(r'<\1>', repr(obj))


def _non_string_or_bytes_iterable(obj):
  return (isinstance(obj, abc.Iterable) and not isinstance(obj, str) and
          not isinstance(obj, bytes))


def _format_parameter_list(testcase_params):
  if isinstance(testcase_params, abc.Mapping):
    return ', '.join('%s=%s' % (argname, _clean_repr(value))
                     for argname, value in testcase_params.items())
  elif _non_string_or_bytes_iterable(testcase_params):
    return ', '.join(map(_clean_repr, testcase_params))
  else:
    return _format_parameter_list((testcase_params,))


def _async_wrapped(func):
  @functools.wraps(func)
  async def wrapper(*args, **kwargs):
    return await func(*args, **kwargs)
  return wrapper


class _ParameterizedTestIter(object):
  """Callable and iterable class for producing new test cases."""

  def __init__(self, test_method, testcases, naming_type, original_name=None):
    """Returns concrete test functions for a test and a list of parameters.

    The naming_type is used to determine the name of the concrete
    functions as reported by the unittest framework. If naming_type is
    _FIRST_ARG, the testcases must be tuples, and the first element must
    have a string representation that is a valid Python identifier.

    Args:
      test_method: The decorated test method.
      testcases: (list of tuple/dict) A list of parameter tuples/dicts for
          individual test invocations.
      naming_type: The test naming type, either _NAMED or _ARGUMENT_REPR.
      original_name: The original test method name. When decorated on a test
          method, None is passed to __init__ and test_method.__name__ is used.
          Note test_method.__name__ might be different than the original defined
          test method because of the use of other decorators. A more accurate
          value is set by TestGeneratorMetaclass.__new__ later.
    """
    self._test_method = test_method
    self.testcases = testcases
    self._naming_type = naming_type
    if original_name is None:
      original_name = test_method.__name__
    self._original_name = original_name
    self.__name__ = _ParameterizedTestIter.__name__

  def __call__(self, *args, **kwargs):
    raise RuntimeError('You appear to be running a parameterized test case '
                       'without having inherited from parameterized.'
                       'TestCase. This is bad because none of '
                       'your test cases are actually being run. You may also '
                       'be using another decorator before the parameterized '
                       'one, in which case you should reverse the order.')

  def __iter__(self):
    test_method = self._test_method
    naming_type = self._naming_type

    def make_bound_param_test(testcase_params):
      @functools.wraps(test_method)
      def bound_param_test(self):
        if isinstance(testcase_params, abc.Mapping):
          return test_method(self, **testcase_params)
        elif _non_string_or_bytes_iterable(testcase_params):
          return test_method(self, *testcase_params)
        else:
          return test_method(self, testcase_params)

      if naming_type is _NAMED:
        # Signal the metaclass that the name of the test function is unique
        # and descriptive.
        bound_param_test.__x_use_name__ = True

        testcase_name = None
        if isinstance(testcase_params, abc.Mapping):
          if _NAMED_DICT_KEY not in testcase_params:
            raise RuntimeError(
                'Dict for named tests must contain key "%s"' % _NAMED_DICT_KEY)
          # Create a new dict to avoid modifying the supplied testcase_params.
          testcase_name = testcase_params[_NAMED_DICT_KEY]
          testcase_params = {
              k: v for k, v in testcase_params.items() if k != _NAMED_DICT_KEY
          }
        elif _non_string_or_bytes_iterable(testcase_params):
          if not isinstance(testcase_params[0], str):
            raise RuntimeError(
                'The first element of named test parameters is the test name '
                'suffix and must be a string')
          testcase_name = testcase_params[0]
          testcase_params = testcase_params[1:]
        else:
          raise RuntimeError(
              'Named tests must be passed a dict or non-string iterable.')

        test_method_name = self._original_name
        # Support PEP-8 underscore style for test naming if used.
        if (test_method_name.startswith('test_')
            and testcase_name
            and not testcase_name.startswith('_')):
          test_method_name += '_'

        bound_param_test.__name__ = test_method_name + str(testcase_name)
      elif naming_type is _ARGUMENT_