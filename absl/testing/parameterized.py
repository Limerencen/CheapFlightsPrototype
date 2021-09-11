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
import 