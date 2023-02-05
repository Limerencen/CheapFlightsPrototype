
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

"""Tests for app.py."""

import contextlib
import copy
import enum
import io
import os
import re
import subprocess
import sys
import tempfile
from unittest import mock

from absl import app
from absl import flags
from absl.testing import _bazelize_command
from absl.testing import absltest
from absl.testing import flagsaver
from absl.tests import app_test_helper


FLAGS = flags.FLAGS


_newline_regex = re.compile('(\r\n)|\r')


@contextlib.contextmanager
def patch_main_module_docstring(docstring):
  old_doc = sys.modules['__main__'].__doc__
  sys.modules['__main__'].__doc__ = docstring
  yield
  sys.modules['__main__'].__doc__ = old_doc


def _normalize_newlines(s):
  return re.sub('(\r\n)|\r', '\n', s)


class UnitTests(absltest.TestCase):

  def test_install_exception_handler(self):
    with self.assertRaises(TypeError):
      app.install_exception_handler(1)

  def test_usage(self):
    with mock.patch.object(
        sys, 'stderr', new=io.StringIO()) as mock_stderr:
      app.usage()
    self.assertIn(__doc__, mock_stderr.getvalue())
    # Assert that flags are written to stderr.
    self.assertIn('\n  --[no]helpfull:', mock_stderr.getvalue())

  def test_usage_shorthelp(self):
    with mock.patch.object(
        sys, 'stderr', new=io.StringIO()) as mock_stderr:
      app.usage(shorthelp=True)
    # Assert that flags are NOT written to stderr.
    self.assertNotIn('  --', mock_stderr.getvalue())

  def test_usage_writeto_stderr(self):
    with mock.patch.object(
        sys, 'stdout', new=io.StringIO()) as mock_stdout:
      app.usage(writeto_stdout=True)
    self.assertIn(__doc__, mock_stdout.getvalue())

  def test_usage_detailed_error(self):
    with mock.patch.object(
        sys, 'stderr', new=io.StringIO()) as mock_stderr:
      app.usage(detailed_error='BAZBAZ')
    self.assertIn('BAZBAZ', mock_stderr.getvalue())

  def test_usage_exitcode(self):
    with mock.patch.object(sys, 'stderr', new=sys.stderr):
      try:
        app.usage(exitcode=2)
        self.fail('app.usage(exitcode=1) should raise SystemExit')
      except SystemExit as e:
        self.assertEqual(2, e.code)

  def test_usage_expands_docstring(self):
    with patch_main_module_docstring('Name: %s, %%s'):
      with mock.patch.object(
          sys, 'stderr', new=io.StringIO()) as mock_stderr:
        app.usage()