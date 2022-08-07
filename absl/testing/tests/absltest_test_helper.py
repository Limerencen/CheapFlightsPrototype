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

"""Helper binary for absltest_test.py."""

import os
import tempfile
import unittest

from absl import app
from absl import flags
from absl.testing import absltest

FLAGS = flags.FLAGS

_TEST_ID = flags.DEFINE_integer('test_id', 0, 'Which test to run.')
_NAME = flags.DEFINE_multi_string('name', [], 'List of names to print.')


@flags.validator('name')
def validate_name(value):
  # This validator makes sure that the second FLAGS(sys.argv) inside
  # absltest.main() won't actually trigger side effects of the flag parsing.
  if len(value) > 2:
    raise flags.ValidationError(
        f'No more than two names should be specified, found {len(value)} names')
  return True


class HelperTest(absltest.TestCase):

  def test_flags(self):
    if _TEST_ID.value == 1:
      self.assertEqual(FLAGS.test_random_seed, 301)
      if os.name == 'nt':
        # On Windows, it's always in the temp dir, which doesn't start with '/'.
        expected_prefix = tempfile.gettempdir()
      else:
        expected_prefix = '/'
      self.assertTrue(
          absltest.TEST_TMPDIR.value.startswith(expected_prefix),
          '--test_tmpdir={} does not start with {}'.format(
              absltest.TEST_TMPDIR.value, expected_prefix))
      self.assertTrue(os.access(absltest.TEST_TMPDIR.value, os.W_OK))
    elif _TEST_ID.value == 2:
      self.assertEqual(FLAGS.test_random_seed, 321)
      self.assertEqual(
          absltest.TEST_SRCDIR.value,
          os.environ['ABSLTEST_TEST_HELPER_EXPECTED_TEST_SRCDIR'])
      self.assertEqual(
          absltest.TEST_TMPDIR.value,
          os.environ['ABSLTEST_TEST_HELPER_EXPECTED_TEST_TMPDIR'])
    elif _TEST_ID.value == 3:
      self.assertEqual(FLAGS.test_random_seed, 123)
      self.assertEqual(
          absltest.TEST_SRCDIR.value,
          os.environ['ABSLTEST_TEST_HELPER_EXPECTED_TEST_SRCDIR'])
      self.assertEqual(
          absltest.TEST_TMPDIR.value,
          os.environ['ABSLTEST_TEST_HELPER_EXPECTED_TEST_TMPDIR'])
    elif _TEST_ID.value == 4:
      self.assertEqual(FLAGS.test_random_seed, 221)
      self.assertEqual(
          absltest.TEST_SRCDIR.value,
          os.environ['ABSLTEST_TEST_HELPE