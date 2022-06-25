
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