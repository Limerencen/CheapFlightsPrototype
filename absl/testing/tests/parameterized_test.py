
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

"""Tests for absl.testing.parameterized."""

from collections import abc
import sys
import unittest

from absl.testing import absltest
from absl.testing import parameterized


class MyOwnClass(object):
  pass


def dummy_decorator(method):

  def decorated(*args, **kwargs):
    return method(*args, **kwargs)

  return decorated


def dict_decorator(key, value):
  """Sample implementation of a chained decorator.

  Sets a single field in a dict on a test with a dict parameter.
  Uses the exposed '_ParameterizedTestIter.testcases' field to
  modify arguments from previous decorators to allow decorator chains.

  Args:
    key: key to map to
    value: value to set

  Returns:
    The test decorator
  """
  def decorator(test_method):
    # If decorating result of another dict_decorator
    if isinstance(test_method, abc.Iterable):
      actual_tests = []
      for old_test in test_method.testcases:
        # each test is a ('test_suffix', dict) tuple
        new_dict = old_test[1].copy()
        new_dict[key] = value
        test_suffix = '%s_%s_%s' % (old_test[0], key, value)
        actual_tests.append((test_suffix, new_dict))

      test_method.testcases = actual_tests
      return test_method
    else:
      test_suffix = ('_%s_%s') % (key, value)
      tests_to_make = ((test_suffix, {key: value}),)
      # 'test_method' here is the original test method
      return parameterized.named_parameters(*tests_to_make)(test_method)
  return decorator


class ParameterizedTestsTest(absltest.TestCase):
  # The test testcases are nested so they're not
  # picked up by the normal test case loader code.

  class GoodAdditionParams(parameterized.TestCase):

    @parameterized.parameters(
        (1, 2, 3),
        (4, 5, 9))
    def test_addition(self, op1, op2, result):
      self.arguments = (op1, op2, result)
      self.assertEqual(result, op1 + op2)

  # This class does not inherit from TestCase.
  class BadAdditionParams(absltest.TestCase):

    @parameterized.parameters(
        (1, 2, 3),
        (4, 5, 9))
    def test_addition(self, op1, op2, result):
      pass  # Always passes, but not called w/out TestCase.

  class MixedAdditionParams(parameterized.TestCase):

    @parameterized.parameters(
        (1, 2, 1),
        (4, 5, 9))
    def test_addition(self, op1, op2, result):
      self.arguments = (op1, op2, result)
      self.assertEqual(result, op1 + op2)

  class DictionaryArguments(parameterized.TestCase):

    @parameterized.parameters(
        {'op1': 1, 'op2': 2, 'result': 3},
        {'op1': 4, 'op2': 5, 'result': 9})
    def test_addition(self, op1, op2, result):
      self.assertEqual(result, op1 + op2)

  class NoParameterizedTests(parameterized.TestCase):
    # iterable member with non-matching name
    a = 'BCD'
    # member with matching name, but not a generator
    testInstanceMember = None  # pylint: disable=invalid-name
    test_instance_member = None

    # member with a matching name and iterator, but not a generator
    testString = 'foo'  # pylint: disable=invalid-name
    test_string = 'foo'

    # generator, but no matching name
    def someGenerator(self):  # pylint: disable=invalid-name
      yield
      yield
      yield

    def some_generator(self):
      yield
      yield
      yield

    # Generator function, but not a generator instance.
    def testGenerator(self):
      yield
      yield
      yield

    def test_generator(self):
      yield
      yield
      yield

    def testNormal(self):
      self.assertEqual(3, 1 + 2)

    def test_normal(self):
      self.assertEqual(3, 1 + 2)

  class ArgumentsWithAddresses(parameterized.TestCase):

    @parameterized.parameters(
        (object(),),
        (MyOwnClass(),),
    )
    def test_something(self, case):
      pass

  class CamelCaseNamedTests(parameterized.TestCase):

    @parameterized.named_parameters(
        ('Interesting', 0),
    )
    def testSingle(self, case):
      pass

    @parameterized.named_parameters(
        {'testcase_name': 'Interesting', 'case': 0},
    )
    def testDictSingle(self, case):
      pass

    @parameterized.named_parameters(
        ('Interesting', 0),
        ('Boring', 1),
    )
    def testSomething(self, case):
      pass

    @parameterized.named_parameters(
        {'testcase_name': 'Interesting', 'case': 0},
        {'testcase_name': 'Boring', 'case': 1},
    )
    def testDictSomething(self, case):
      pass

    @parameterized.named_parameters(
        {'testcase_name': 'Interesting', 'case': 0},
        ('Boring', 1),
    )
    def testMixedSomething(self, case):
      pass

    def testWithoutParameters(self):
      pass

  class NamedTests(parameterized.TestCase):
    """Example tests using PEP-8 style names instead of camel-case."""

    @parameterized.named_parameters(
        ('interesting', 0),
    )
    def test_single(self, case):
      pass

    @parameterized.named_parameters(
        {'testcase_name': 'interesting', 'case': 0},
    )
    def test_dict_single(self, case):
      pass

    @parameterized.named_parameters(
        ('interesting', 0),
        ('boring', 1),
    )
    def test_something(self, case):
      pass

    @parameterized.named_parameters(
        {'testcase_name': 'interesting', 'case': 0},
        {'testcase_name': 'boring', 'case': 1},
    )
    def test_dict_something(self, case):
      pass

    @parameterized.named_parameters(
        {'testcase_name': 'interesting', 'case': 0},
        ('boring', 1),
    )
    def test_mixed_something(self, case):
      pass

    def test_without_parameters(self):
      pass

  class ChainedTests(parameterized.TestCase):

    @dict_decorator('cone', 'waffle')
    @dict_decorator('flavor', 'strawberry')
    def test_chained(self, dictionary):
      self.assertDictEqual(dictionary, {'cone': 'waffle',
                                        'flavor': 'strawberry'})

  class SingletonListExtraction(parameterized.TestCase):

    @parameterized.parameters(
        (i, i * 2) for i in range(10))
    def test_something(self, unused_1, unused_2):
      pass

  class SingletonArgumentExtraction(parameterized.TestCase):

    @parameterized.parameters(1, 2, 3, 4, 5, 6)
    def test_numbers(self, unused_1):
      pass

    @parameterized.parameters('foo', 'bar', 'baz')
    def test_strings(self, unused_1):
      pass

  class SingletonDictArgument(parameterized.TestCase):

    @parameterized.parameters({'op1': 1, 'op2': 2})
    def test_something(self, op1, op2):
      del op1, op2

  @parameterized.parameters(
      (1, 2, 3),
      (4, 5, 9))
  class DecoratedClass(parameterized.TestCase):

    def test_add(self, arg1, arg2, arg3):
      self.assertEqual(arg1 + arg2, arg3)

    def test_subtract_fail(self, arg1, arg2, arg3):
      self.assertEqual(arg3 + arg2, arg1)

  @parameterized.parameters(
      (a, b, a+b) for a in range(1, 5) for b in range(1, 5))
  class GeneratorDecoratedClass(parameterized.TestCase):

    def test_add(self, arg1, arg2, arg3):
      self.assertEqual(arg1 + arg2, arg3)

    def test_subtract_fail(self, arg1, arg2, arg3):
      self.assertEqual(arg3 + arg2, arg1)

  @parameterized.parameters(
      (1, 2, 3),
      (4, 5, 9),
  )
  class DecoratedBareClass(absltest.TestCase):

    def test_add(self, arg1, arg2, arg3):
      self.assertEqual(arg1 + arg2, arg3)

  class OtherDecoratorUnnamed(parameterized.TestCase):

    @dummy_decorator
    @parameterized.parameters((1), (2))
    def test_other_then_parameterized(self, arg1):
      pass

    @parameterized.parameters((1), (2))
    @dummy_decorator
    def test_parameterized_then_other(self, arg1):
      pass

  class OtherDecoratorNamed(parameterized.TestCase):

    @dummy_decorator
    @parameterized.named_parameters(('a', 1), ('b', 2))
    def test_other_then_parameterized(self, arg1):
      pass

    @parameterized.named_parameters(('a', 1), ('b', 2))
    @dummy_decorator
    def test_parameterized_then_other(self, arg1):
      pass

  class OtherDecoratorNamedWithDict(parameterized.TestCase):

    @dummy_decorator
    @parameterized.named_parameters(
        {'testcase_name': 'a', 'arg1': 1},
        {'testcase_name': 'b', 'arg1': 2})
    def test_other_then_parameterized(self, arg1):
      pass

    @parameterized.named_parameters(
        {'testcase_name': 'a', 'arg1': 1},
        {'testcase_name': 'b', 'arg1': 2})
    @dummy_decorator
    def test_parameterized_then_other(self, arg1):
      pass

  class UniqueDescriptiveNamesTest(parameterized.TestCase):
