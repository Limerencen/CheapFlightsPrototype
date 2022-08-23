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
"""Tests for flagsaver."""

from absl import flags
from absl.testing import absltest
from absl.testing import flagsaver
from absl.testing import parameterized

flags.DEFINE_string('flagsaver_test_flag0', 'unchanged0', 'flag to test with')
flags.DEFINE_string('flagsaver_test_flag1', 'unchanged1', 'flag to test with')

flags.DEFINE_string('flagsaver_test_validated_flag', None, 'flag to test with')
flags.register_validator('flagsaver_test_validated_flag', lambda x: not x)

flags.DEFINE_string('flagsaver_test_validated_flag1', None, 'flag to test with')
flags.DEFINE_string('flagsaver_test_validated_flag2', None, 'flag to test with')

INT_FLAG = flags.DEFINE_integer(
    'flagsaver_test_int_flag', default=1, help='help')
STR_FLAG = flags.DEFINE_string(
    'flagsaver_test_str_flag', default='str default', help='help')

MULTI_INT_FLAG = flags.DEFINE_multi_integer('flagsaver_test_multi_int_flag',
                                            None, 'flag to test with')


@flags.multi_flags_validator(
    ('flagsaver_test_validated_flag1', 'flagsaver_test_validated_flag2'))
def validate_test_flags(flag_dict):
  return (flag_dict['flagsaver_test_validated_flag1'] ==
          flag_dict['flagsaver_test_validated_flag2'])


FLAGS = flags.FLAGS


@flags.validator('flagsaver_test_flag0')
def check_no_upper_case(value):
  return value == value.lower()


class _TestError(Exception):
  """Exception class for use in these tests."""


class CommonUsageTest(absltest.TestCase):
  """These test cases cover the most common usages of flagsaver."""

  def test_as_parsed_context_manager(self):
    # Precondition check, we expect all the flags to start as their default.
    self.assertEqual('str default', STR_FLAG.value)
    self.assertFalse(STR_FLAG.present)
    self.assertEqual(1, INT_FLAG.value)
    self.assertEqual('unchanged0', FLAGS.flagsaver_test_flag0)
    self.assertEqual('unchanged1', FLAGS.flagsaver_test_flag1)

    # Flagsaver will also save the state of flags that have been modified.
    FLAGS.flagsaver_test_flag1 = 'outside flagsaver'

    # Save all existing flag state, and set some flags as if they were parsed on
    # the command line. Because of this, the new values must be provided as str,
    # even if the flag type is something other than string.
    with flagsaver.as_parsed(
        (STR_FLAG, 'new string value'),  # Override using flagholder object.
        (INT_FLAG, '123'),  # Override an int flag (NOTE: must specify as str).
        flagsaver_test_flag0='new value',  # Override using flag name.
    ):
      # All the flags have their overridden values.
      self.assertEqual('new string value', STR_FLAG.value)
 