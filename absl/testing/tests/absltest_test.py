
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