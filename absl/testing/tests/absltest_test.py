
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

"""Tests for absltest."""

import collections
import contextlib
import io
import os
import pathlib
import re
import stat
import string
import subprocess
import tempfile
import unittest

from absl.testing import _bazelize_command
from absl.testing import absltest
from absl.testing import parameterized
from absl.testing.tests import absltest_env


class HelperMixin(object):

  def _get_helper_exec_path(self):
    helper = 'absl/testing/tests/absltest_test_helper'
    return _bazelize_command.get_executable_path(helper)

  def run_helper(self, test_id, args, env_overrides, expect_success):
    env = absltest_env.inherited_env()
    for key, value in env_overrides.items():
      if value is None:
        if key in env:
          del env[key]
      else:
        env[key] = value

    command = [self._get_helper_exec_path(),
               '--test_id={}'.format(test_id)] + args
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
        universal_newlines=True)
    stdout, stderr = process.communicate()
    if expect_success:
      self.assertEqual(
          0, process.returncode,
          'Expected success, but failed with '
          'stdout:\n{}\nstderr:\n{}\n'.format(stdout, stderr))
    else:
      self.assertEqual(
          1, process.returncode,
          'Expected failure, but succeeded with '
          'stdout:\n{}\nstderr:\n{}\n'.format(stdout, stderr))
    return stdout, stderr


class TestCaseTest(absltest.TestCase, HelperMixin):
  longMessage = True

  def run_helper(self, test_id, args, env_overrides, expect_success):
    return super(TestCaseTest, self).run_helper(test_id, args + ['HelperTest'],
                                                env_overrides, expect_success)

  def test_flags_no_env_var_no_flags(self):
    self.run_helper(
        1,
        [],
        {'TEST_RANDOM_SEED': None,
         'TEST_SRCDIR': None,
         'TEST_TMPDIR': None,
        },
        expect_success=True)

  def test_flags_env_var_no_flags(self):
    tmpdir = tempfile.mkdtemp(dir=absltest.TEST_TMPDIR.value)
    srcdir = tempfile.mkdtemp(dir=absltest.TEST_TMPDIR.value)
    self.run_helper(
        2,
        [],
        {'TEST_RANDOM_SEED': '321',
         'TEST_SRCDIR': srcdir,
         'TEST_TMPDIR': tmpdir,
         'ABSLTEST_TEST_HELPER_EXPECTED_TEST_SRCDIR': srcdir,
         'ABSLTEST_TEST_HELPER_EXPECTED_TEST_TMPDIR': tmpdir,
        },
        expect_success=True)

  def test_flags_no_env_var_flags(self):
    tmpdir = tempfile.mkdtemp(dir=absltest.TEST_TMPDIR.value)
    srcdir = tempfile.mkdtemp(dir=absltest.TEST_TMPDIR.value)
    self.run_helper(
        3,
        ['--test_random_seed=123', '--test_srcdir={}'.format(srcdir),
         '--test_tmpdir={}'.format(tmpdir)],
        {'TEST_RANDOM_SEED': None,
         'TEST_SRCDIR': None,
         'TEST_TMPDIR': None,
         'ABSLTEST_TEST_HELPER_EXPECTED_TEST_SRCDIR': srcdir,
         'ABSLTEST_TEST_HELPER_EXPECTED_TEST_TMPDIR': tmpdir,
        },
        expect_success=True)

  def test_flags_env_var_flags(self):
    tmpdir_from_flag = tempfile.mkdtemp(dir=absltest.TEST_TMPDIR.value)
    srcdir_from_flag = tempfile.mkdtemp(dir=absltest.TEST_TMPDIR.value)
    tmpdir_from_env_var = tempfile.mkdtemp(dir=absltest.TEST_TMPDIR.value)
    srcdir_from_env_var = tempfile.mkdtemp(dir=absltest.TEST_TMPDIR.value)
    self.run_helper(
        4,
        ['--test_random_seed=221', '--test_srcdir={}'.format(srcdir_from_flag),
         '--test_tmpdir={}'.format(tmpdir_from_flag)],
        {'TEST_RANDOM_SEED': '123',
         'TEST_SRCDIR': srcdir_from_env_var,
         'TEST_TMPDIR': tmpdir_from_env_var,
         'ABSLTEST_TEST_HELPER_EXPECTED_TEST_SRCDIR': srcdir_from_flag,
         'ABSLTEST_TEST_HELPER_EXPECTED_TEST_TMPDIR': tmpdir_from_flag,
        },
        expect_success=True)

  def test_xml_output_file_from_xml_output_file_env(self):
    xml_dir = tempfile.mkdtemp(dir=absltest.TEST_TMPDIR.value)
    xml_output_file_env = os.path.join(xml_dir, 'xml_output_file.xml')
    random_dir = tempfile.mkdtemp(dir=absltest.TEST_TMPDIR.value)
    self.run_helper(
        6,
        [],
        {'XML_OUTPUT_FILE': xml_output_file_env,
         'RUNNING_UNDER_TEST_DAEMON': '1',
         'TEST_XMLOUTPUTDIR': random_dir,
         'ABSLTEST_TEST_HELPER_EXPECTED_XML_OUTPUT_FILE': xml_output_file_env,
        },
        expect_success=True)

  def test_xml_output_file_from_daemon(self):
    tmpdir = os.path.join(tempfile.mkdtemp(
        dir=absltest.TEST_TMPDIR.value), 'sub_dir')
    random_dir = tempfile.mkdtemp(dir=absltest.TEST_TMPDIR.value)
    self.run_helper(
        6,
        ['--test_tmpdir', tmpdir],
        {'XML_OUTPUT_FILE': None,
         'RUNNING_UNDER_TEST_DAEMON': '1',
         'TEST_XMLOUTPUTDIR': random_dir,
         'ABSLTEST_TEST_HELPER_EXPECTED_XML_OUTPUT_FILE': os.path.join(
             os.path.dirname(tmpdir), 'test_detail.xml'),
        },
        expect_success=True)

  def test_xml_output_file_from_test_xmloutputdir_env(self):
    xml_output_dir = tempfile.mkdtemp(dir=absltest.TEST_TMPDIR.value)
    expected_xml_file = 'absltest_test_helper.xml'
    self.run_helper(
        6,
        [],
        {'XML_OUTPUT_FILE': None,
         'RUNNING_UNDER_TEST_DAEMON': None,
         'TEST_XMLOUTPUTDIR': xml_output_dir,
         'ABSLTEST_TEST_HELPER_EXPECTED_XML_OUTPUT_FILE': os.path.join(
             xml_output_dir, expected_xml_file),
        },
        expect_success=True)

  def test_xml_output_file_from_flag(self):
    random_dir = tempfile.mkdtemp(dir=absltest.TEST_TMPDIR.value)
    flag_file = os.path.join(
        tempfile.mkdtemp(dir=absltest.TEST_TMPDIR.value), 'output.xml')
    self.run_helper(
        6,
        ['--xml_output_file', flag_file],
        {'XML_OUTPUT_FILE': os.path.join(random_dir, 'output.xml'),
         'RUNNING_UNDER_TEST_DAEMON': '1',
         'TEST_XMLOUTPUTDIR': random_dir,
         'ABSLTEST_TEST_HELPER_EXPECTED_XML_OUTPUT_FILE': flag_file,
        },
        expect_success=True)

  def test_app_run(self):
    stdout, _ = self.run_helper(
        7,
        ['--name=cat', '--name=dog'],
        {'ABSLTEST_TEST_HELPER_USE_APP_RUN': '1'},
        expect_success=True)
    self.assertIn('Names in main() are: cat dog', stdout)
    self.assertIn('Names in test_name_flag() are: cat dog', stdout)

  def test_assert_in(self):
    animals = {'monkey': 'banana', 'cow': 'grass', 'seal': 'fish'}

    self.assertIn('a', 'abc')
    self.assertIn(2, [1, 2, 3])
    self.assertIn('monkey', animals)

    self.assertNotIn('d', 'abc')
    self.assertNotIn(0, [1, 2, 3])
    self.assertNotIn('otter', animals)

    self.assertRaises(AssertionError, self.assertIn, 'x', 'abc')
    self.assertRaises(AssertionError, self.assertIn, 4, [1, 2, 3])
    self.assertRaises(AssertionError, self.assertIn, 'elephant', animals)

    self.assertRaises(AssertionError, self.assertNotIn, 'c', 'abc')
    self.assertRaises(AssertionError, self.assertNotIn, 1, [1, 2, 3])
    self.assertRaises(AssertionError, self.assertNotIn, 'cow', animals)

  @absltest.expectedFailure
  def test_expected_failure(self):
    self.assertEqual(1, 2)  # the expected failure

  @absltest.expectedFailureIf(True, 'always true')
  def test_expected_failure_if(self):
    self.assertEqual(1, 2)  # the expected failure

  def test_expected_failure_success(self):
    _, stderr = self.run_helper(5, ['--', '-v'], {}, expect_success=False)
    self.assertRegex(stderr, r'FAILED \(.*unexpected successes=1\)')

  def test_assert_equal(self):
    self.assertListEqual([], [])
    self.assertTupleEqual((), ())
    self.assertSequenceEqual([], ())

    a = [0, 'a', []]
    b = []
    self.assertRaises(absltest.TestCase.failureException,
                      self.assertListEqual, a, b)
    self.assertRaises(absltest.TestCase.failureException,
                      self.assertListEqual, tuple(a), tuple(b))
    self.assertRaises(absltest.TestCase.failureException,
                      self.assertSequenceEqual, a, tuple(b))

    b.extend(a)
    self.assertListEqual(a, b)
    self.assertTupleEqual(tuple(a), tuple(b))
    self.assertSequenceEqual(a, tuple(b))
    self.assertSequenceEqual(tuple(a), b)

    self.assertRaises(AssertionError, self.assertListEqual, a, tuple(b))
    self.assertRaises(AssertionError, self.assertTupleEqual, tuple(a), b)
    self.assertRaises(AssertionError, self.assertListEqual, None, b)
    self.assertRaises(AssertionError, self.assertTupleEqual, None, tuple(b))
    self.assertRaises(AssertionError, self.assertSequenceEqual, None, tuple(b))
    self.assertRaises(AssertionError, self.assertListEqual, 1, 1)
    self.assertRaises(AssertionError, self.assertTupleEqual, 1, 1)
    self.assertRaises(AssertionError, self.assertSequenceEqual, 1, 1)

    self.assertSameElements([1, 2, 3], [3, 2, 1])
    self.assertSameElements([1, 2] + [3] * 100, [1] * 100 + [2, 3])
    self.assertSameElements(['foo', 'bar', 'baz'], ['bar', 'baz', 'foo'])
    self.assertRaises(AssertionError, self.assertSameElements, [10], [10, 11])
    self.assertRaises(AssertionError, self.assertSameElements, [10, 11], [10])

    # Test that sequences of unhashable objects can be tested for sameness:
    self.assertSameElements([[1, 2], [3, 4]], [[3, 4], [1, 2]])
    self.assertRaises(AssertionError, self.assertSameElements, [[1]], [[2]])

  def test_assert_items_equal_hotfix(self):
    """Confirm that http://bugs.python.org/issue14832 - b/10038517 is gone."""
    for assert_items_method in (self.assertItemsEqual, self.assertCountEqual):
      with self.assertRaises(self.failureException) as error_context:
        assert_items_method([4], [2])
      error_message = str(error_context.exception)
      # Confirm that the bug is either no longer present in Python or that our
      # assertItemsEqual patching version of the method in absltest.TestCase
      # doesn't get used.
      self.assertIn('First has 1, Second has 0:  4', error_message)
      self.assertIn('First has 0, Second has 1:  2', error_message)

  def test_assert_dict_equal(self):
    self.assertDictEqual({}, {})

    c = {'x': 1}
    d = {}
    self.assertRaises(absltest.TestCase.failureException,
                      self.assertDictEqual, c, d)

    d.update(c)
    self.assertDictEqual(c, d)

    d['x'] = 0
    self.assertRaises(absltest.TestCase.failureException,
                      self.assertDictEqual, c, d, 'These are unequal')

    self.assertRaises(AssertionError, self.assertDictEqual, None, d)
    self.assertRaises(AssertionError, self.assertDictEqual, [], d)
    self.assertRaises(AssertionError, self.assertDictEqual, 1, 1)

    try:
      # Ensure we use equality as the sole measure of elements, not type, since
      # that is consistent with dict equality.
      self.assertDictEqual({1: 1.0, 2: 2}, {1: 1, 2: 3})
    except AssertionError as e:
      self.assertMultiLineEqual('{1: 1.0, 2: 2} != {1: 1, 2: 3}\n'
                                'repr() of differing entries:\n2: 2 != 3\n',
                                str(e))

    try:
      self.assertDictEqual({}, {'x': 1})
    except AssertionError as e:
      self.assertMultiLineEqual("{} != {'x': 1}\n"
                                "Unexpected, but present entries:\n'x': 1\n",
                                str(e))
    else:
      self.fail('Expecting AssertionError')

    try:
      self.assertDictEqual({}, {'x': 1}, 'a message')
    except AssertionError as e:
      self.assertIn('a message', str(e))
    else:
      self.fail('Expecting AssertionError')

    expected = {'a': 1, 'b': 2, 'c': 3}
    seen = {'a': 2, 'c': 3, 'd': 4}
    try:
      self.assertDictEqual(expected, seen)
    except AssertionError as e:
      self.assertMultiLineEqual("""\
{'a': 1, 'b': 2, 'c': 3} != {'a': 2, 'c': 3, 'd': 4}
Unexpected, but present entries:
'd': 4

repr() of differing entries:
'a': 1 != 2

Missing entries:
'b': 2
""", str(e))
    else:
      self.fail('Expecting AssertionError')

    self.assertRaises(AssertionError, self.assertDictEqual, (1, 2), {})
    self.assertRaises(AssertionError, self.assertDictEqual, {}, (1, 2))

    # Ensure deterministic output of keys in dictionaries whose sort order
    # doesn't match the lexical ordering of repr -- this is most Python objects,
    # which are keyed by memory address.
    class Obj(object):

      def __init__(self, name):
        self.name = name

      def __repr__(self):
        return self.name

    try:
      self.assertDictEqual(
          {'a': Obj('A'), Obj('b'): Obj('B'), Obj('c'): Obj('C')},
          {'a': Obj('A'), Obj('d'): Obj('D'), Obj('e'): Obj('E')})
    except AssertionError as e:
      # Do as best we can not to be misleading when objects have the same repr
      # but aren't equal.
      err_str = str(e)
      self.assertStartsWith(err_str,
                            "{'a': A, b: B, c: C} != {'a': A, d: D, e: E}\n")
      self.assertRegex(
          err_str, r'(?ms).*^Unexpected, but present entries:\s+'
          r'^(d: D$\s+^e: E|e: E$\s+^d: D)$')
      self.assertRegex(
          err_str, r'(?ms).*^repr\(\) of differing entries:\s+'
          r'^.a.: A != A$', err_str)
      self.assertRegex(
          err_str, r'(?ms).*^Missing entries:\s+'
          r'^(b: B$\s+^c: C|c: C$\s+^b: B)$')
    else:
      self.fail('Expecting AssertionError')

    # Confirm that safe_repr, not repr, is being used.
    class RaisesOnRepr(object):

      def __repr__(self):
        return 1/0  # Intentionally broken __repr__ implementation.

    try:
      self.assertDictEqual(
          {RaisesOnRepr(): RaisesOnRepr()},
          {RaisesOnRepr(): RaisesOnRepr()}
          )
      self.fail('Expected dicts not to match')
    except AssertionError as e:
      # Depending on the testing environment, the object may get a __main__
      # prefix or a absltest_test prefix, so strip that for comparison.
      error_msg = re.sub(
          r'( at 0x[^>]+)|__main__\.|absltest_test\.', '', str(e))
      self.assertRegex(error_msg, """(?m)\
{<.*RaisesOnRepr object.*>: <.*RaisesOnRepr object.*>} != \
{<.*RaisesOnRepr object.*>: <.*RaisesOnRepr object.*>}
Unexpected, but present entries:
<.*RaisesOnRepr object.*>: <.*RaisesOnRepr object.*>

Missing entries:
<.*RaisesOnRepr object.*>: <.*RaisesOnRepr object.*>
""")

    # Confirm that safe_repr, not repr, is being used.
    class RaisesOnLt(object):

      def __lt__(self, unused_other):
        raise TypeError('Object is unordered.')

      def __repr__(self):
        return '<RaisesOnLt object>'

    try:
      self.assertDictEqual(
          {RaisesOnLt(): RaisesOnLt()},
          {RaisesOnLt(): RaisesOnLt()})
    except AssertionError as e:
      self.assertIn('Unexpected, but present entries:\n<RaisesOnLt', str(e))
      self.assertIn('Missing entries:\n<RaisesOnLt', str(e))

  def test_assert_set_equal(self):
    set1 = set()
    set2 = set()
    self.assertSetEqual(set1, set2)

    self.assertRaises(AssertionError, self.assertSetEqual, None, set2)
    self.assertRaises(AssertionError, self.assertSetEqual, [], set2)
    self.assertRaises(AssertionError, self.assertSetEqual, set1, None)
    self.assertRaises(AssertionError, self.assertSetEqual, set1, [])

    set1 = set(['a'])
    set2 = set()
    self.assertRaises(AssertionError, self.assertSetEqual, set1, set2)

    set1 = set(['a'])
    set2 = set(['a'])
    self.assertSetEqual(set1, set2)

    set1 = set(['a'])
    set2 = set(['a', 'b'])
    self.assertRaises(AssertionError, self.assertSetEqual, set1, set2)

    set1 = set(['a'])
    set2 = frozenset(['a', 'b'])
    self.assertRaises(AssertionError, self.assertSetEqual, set1, set2)

    set1 = set(['a', 'b'])
    set2 = frozenset(['a', 'b'])
    self.assertSetEqual(set1, set2)

    set1 = set()
    set2 = 'foo'
    self.assertRaises(AssertionError, self.assertSetEqual, set1, set2)
    self.assertRaises(AssertionError, self.assertSetEqual, set2, set1)

    # make sure any string formatting is tuple-safe
    set1 = set([(0, 1), (2, 3)])
    set2 = set([(4, 5)])
    self.assertRaises(AssertionError, self.assertSetEqual, set1, set2)

  def test_assert_dict_contains_subset(self):
    self.assertDictContainsSubset({}, {})

    self.assertDictContainsSubset({}, {'a': 1})

    self.assertDictContainsSubset({'a': 1}, {'a': 1})

    self.assertDictContainsSubset({'a': 1}, {'a': 1, 'b': 2})

    self.assertDictContainsSubset({'a': 1, 'b': 2}, {'a': 1, 'b': 2})

    self.assertRaises(absltest.TestCase.failureException,
                      self.assertDictContainsSubset, {'a': 2}, {'a': 1},
                      '.*Mismatched values:.*')

    self.assertRaises(absltest.TestCase.failureException,
                      self.assertDictContainsSubset, {'c': 1}, {'a': 1},
                      '.*Missing:.*')

    self.assertRaises(absltest.TestCase.failureException,
                      self.assertDictContainsSubset, {'a': 1, 'c': 1}, {'a': 1},
                      '.*Missing:.*')

    self.assertRaises(absltest.TestCase.failureException,
                      self.assertDictContainsSubset, {'a': 1, 'c': 1}, {'a': 1},
                      '.*Missing:.*Mismatched values:.*')

  def test_assert_sequence_almost_equal(self):
    actual = (1.1, 1.2, 1.4)

    # Test across sequence types.
    self.assertSequenceAlmostEqual((1.1, 1.2, 1.4), actual)
    self.assertSequenceAlmostEqual([1.1, 1.2, 1.4], actual)

    # Test sequence size mismatch.
    with self.assertRaises(AssertionError):
      self.assertSequenceAlmostEqual([1.1, 1.2], actual)
    with self.assertRaises(AssertionError):
      self.assertSequenceAlmostEqual([1.1, 1.2, 1.4, 1.5], actual)

    # Test delta.
    with self.assertRaises(AssertionError):
      self.assertSequenceAlmostEqual((1.15, 1.15, 1.4), actual)
    self.assertSequenceAlmostEqual((1.15, 1.15, 1.4), actual, delta=0.1)

    # Test places.
    with self.assertRaises(AssertionError):
      self.assertSequenceAlmostEqual((1.1001, 1.2001, 1.3999), actual)
    self.assertSequenceAlmostEqual((1.1001, 1.2001, 1.3999), actual, places=3)

  def test_assert_contains_subset(self):
    # sets, lists, tuples, dicts all ok.  Types of set and subset do not have to
    # match.
    actual = ('a', 'b', 'c')
    self.assertContainsSubset({'a', 'b'}, actual)
    self.assertContainsSubset(('b', 'c'), actual)
    self.assertContainsSubset({'b': 1, 'c': 2}, list(actual))
    self.assertContainsSubset(['c', 'a'], set(actual))
    self.assertContainsSubset([], set())
    self.assertContainsSubset([], {'a': 1})

    self.assertRaises(AssertionError, self.assertContainsSubset, ('d',), actual)
    self.assertRaises(AssertionError, self.assertContainsSubset, ['d'],
                      set(actual))
    self.assertRaises(AssertionError, self.assertContainsSubset, {'a': 1}, [])

    with self.assertRaisesRegex(AssertionError, 'Missing elements'):
      self.assertContainsSubset({1, 2, 3}, {1, 2})

    with self.assertRaisesRegex(
        AssertionError,
        re.compile('Missing elements .* Custom message', re.DOTALL)):
      self.assertContainsSubset({1, 2}, {1}, 'Custom message')

  def test_assert_no_common_elements(self):
    actual = ('a', 'b', 'c')
    self.assertNoCommonElements((), actual)
    self.assertNoCommonElements(('d', 'e'), actual)
    self.assertNoCommonElements({'d', 'e'}, actual)

    with self.assertRaisesRegex(
        AssertionError,
        re.compile('Common elements .* Custom message', re.DOTALL)):
      self.assertNoCommonElements({1, 2}, {1}, 'Custom message')

    with self.assertRaises(AssertionError):
      self.assertNoCommonElements(['a'], actual)

    with self.assertRaises(AssertionError):
      self.assertNoCommonElements({'a', 'b', 'c'}, actual)

    with self.assertRaises(AssertionError):
      self.assertNoCommonElements({'b', 'c'}, set(actual))

  def test_assert_almost_equal(self):
    self.assertAlmostEqual(1.00000001, 1.0)
    self.assertNotAlmostEqual(1.0000001, 1.0)

  def test_assert_almost_equals_with_delta(self):
    self.assertAlmostEqual(3.14, 3, delta=0.2)
    self.assertAlmostEqual(2.81, 3.14, delta=1)
    self.assertAlmostEqual(-1, 1, delta=3)
    self.assertRaises(AssertionError, self.assertAlmostEqual,
                      3.14, 2.81, delta=0.1)
    self.assertRaises(AssertionError, self.assertAlmostEqual,
                      1, 2, delta=0.5)
    self.assertNotAlmostEqual(3.14, 2.81, delta=0.1)

  def test_assert_starts_with(self):
    self.assertStartsWith('foobar', 'foo')
    self.assertStartsWith('foobar', 'foobar')
    msg = 'This is a useful message'
    whole_msg = "'foobar' does not start with 'bar' : This is a useful message"
    self.assertRaisesWithLiteralMatch(AssertionError, whole_msg,
                                      self.assertStartsWith,
                                      'foobar', 'bar', msg)
    self.assertRaises(AssertionError, self.assertStartsWith, 'foobar', 'blah')

  def test_assert_not_starts_with(self):
    self.assertNotStartsWith('foobar', 'bar')
    self.assertNotStartsWith('foobar', 'blah')
    msg = 'This is a useful message'
    whole_msg = "'foobar' does start with 'foo' : This is a useful message"
    self.assertRaisesWithLiteralMatch(AssertionError, whole_msg,
                                      self.assertNotStartsWith,
                                      'foobar', 'foo', msg)
    self.assertRaises(AssertionError, self.assertNotStartsWith, 'foobar',
                      'foobar')

  def test_assert_ends_with(self):
    self.assertEndsWith('foobar', 'bar')
    self.assertEndsWith('foobar', 'foobar')
    msg = 'This is a useful message'
    whole_msg = "'foobar' does not end with 'foo' : This is a useful message"
    self.assertRaisesWithLiteralMatch(AssertionError, whole_msg,
                                      self.assertEndsWith,
                                      'foobar', 'foo', msg)
    self.assertRaises(AssertionError, self.assertEndsWith, 'foobar', 'blah')

  def test_assert_not_ends_with(self):
    self.assertNotEndsWith('foobar', 'foo')
    self.assertNotEndsWith('foobar', 'blah')
    msg = 'This is a useful message'
    whole_msg = "'foobar' does end with 'bar' : This is a useful message"
    self.assertRaisesWithLiteralMatch(AssertionError, whole_msg,
                                      self.assertNotEndsWith,
                                      'foobar', 'bar', msg)
    self.assertRaises(AssertionError, self.assertNotEndsWith, 'foobar',
                      'foobar')

  def test_assert_regex_backports(self):
    self.assertRegex('regex', 'regex')
    self.assertNotRegex('not-regex', 'no-match')
    with self.assertRaisesRegex(ValueError, 'pattern'):
      raise ValueError('pattern')

  def test_assert_regex_match_matches(self):
    self.assertRegexMatch('str', ['str'])

  def test_assert_regex_match_matches_substring(self):
    self.assertRegexMatch('pre-str-post', ['str'])

  def test_assert_regex_match_multiple_regex_matches(self):
    self.assertRegexMatch('str', ['rts', 'str'])

  def test_assert_regex_match_empty_list_fails(self):
    expected_re = re.compile(r'No regexes specified\.', re.MULTILINE)

    with self.assertRaisesRegex(AssertionError, expected_re):
      self.assertRegexMatch('str', regexes=[])

  def test_assert_regex_match_bad_arguments(self):
    with self.assertRaisesRegex(AssertionError,
                                'regexes is string or bytes;.*'):
      self.assertRegexMatch('1.*2', '1 2')

  def test_assert_regex_match_unicode_vs_bytes(self):
    """Ensure proper utf-8 encoding or decoding happens automatically."""
    self.assertRegexMatch(u'str', [b'str'])
    self.assertRegexMatch(b'str', [u'str'])

  def test_assert_regex_match_unicode(self):
    self.assertRegexMatch(u'foo str', [u'str'])

  def test_assert_regex_match_bytes(self):
    self.assertRegexMatch(b'foo str', [b'str'])

  def test_assert_regex_match_all_the_same_type(self):
    with self.assertRaisesRegex(AssertionError, 'regexes .* same type'):
      self.assertRegexMatch('foo str', [b'str', u'foo'])

  def test_assert_command_fails_stderr(self):
    tmpdir = tempfile.mkdtemp(dir=absltest.TEST_TMPDIR.value)
    self.assertCommandFails(
        ['cat', os.path.join(tmpdir, 'file.txt')],
        ['No such file or directory'],
        env=_env_for_command_tests())

  def test_assert_command_fails_with_list_of_string(self):
    self.assertCommandFails(
        ['false'], [''], env=_env_for_command_tests())

  def test_assert_command_fails_with_list_of_unicode_string(self):
    self.assertCommandFails(
        [u'false'], [''], env=_env_for_command_tests())

  def test_assert_command_fails_with_unicode_string(self):
    self.assertCommandFails(
        u'false', [u''], env=_env_for_command_tests())

  def test_assert_command_fails_with_unicode_string_bytes_regex(self):
    self.assertCommandFails(
        u'false', [b''], env=_env_for_command_tests())

  def test_assert_command_fails_with_message(self):
    msg = 'This is a useful message'
    expected_re = re.compile('The following command succeeded while expected to'
                             ' fail:.* This is a useful message', re.DOTALL)

    with self.assertRaisesRegex(AssertionError, expected_re):
      self.assertCommandFails(
          [u'true'], [''], msg=msg, env=_env_for_command_tests())

  def test_assert_command_succeeds_stderr(self):
    expected_re = re.compile('No such file or directory')
    tmpdir = tempfile.mkdtemp(dir=absltest.TEST_TMPDIR.value)

    with self.assertRaisesRegex(AssertionError, expected_re):
      self.assertCommandSucceeds(
          ['cat', os.path.join(tmpdir, 'file.txt')],
          env=_env_for_command_tests())

  def test_assert_command_succeeds_with_matching_unicode_regexes(self):
    self.assertCommandSucceeds(
        ['echo', 'SUCCESS'], regexes=[u'SUCCESS'],
        env=_env_for_command_tests())

  def test_assert_command_succeeds_with_matching_bytes_regexes(self):
    self.assertCommandSucceeds(
        ['echo', 'SUCCESS'], regexes=[b'SUCCESS'],
        env=_env_for_command_tests())

  def test_assert_command_succeeds_with_non_matching_regexes(self):
    expected_re = re.compile('Running command.* This is a useful message',
                             re.DOTALL)
    msg = 'This is a useful message'

    with self.assertRaisesRegex(AssertionError, expected_re):
      self.assertCommandSucceeds(