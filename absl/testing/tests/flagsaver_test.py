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
      self.assertTrue(STR_FLAG.present)
      self.assertEqual(123, INT_FLAG.value)
      self.assertEqual('new value', FLAGS.flagsaver_test_flag0)
      # Even if we change other flags, they will reset on context exit.
      FLAGS.flagsaver_test_flag1 = 'new value 1'

    # The flags have all reset to their pre-flagsaver values.
    self.assertEqual('str default', STR_FLAG.value)
    self.assertFalse(STR_FLAG.present)
    self.assertEqual(1, INT_FLAG.value)
    self.assertEqual('unchanged0', FLAGS.flagsaver_test_flag0)
    self.assertEqual('outside flagsaver', FLAGS.flagsaver_test_flag1)

  def test_as_parsed_decorator(self):
    # flagsaver.as_parsed can also be used as a decorator.
    @flagsaver.as_parsed((INT_FLAG, '123'))
    def do_something_with_flags():
      self.assertEqual(123, INT_FLAG.value)
      self.assertTrue(INT_FLAG.present)

    do_something_with_flags()
    self.assertEqual(1, INT_FLAG.value)
    self.assertFalse(INT_FLAG.present)

  def test_flagsaver_flagsaver(self):
    # If you don't want the flags to go through parsing, you can instead use
    # flagsaver.flagsaver(). With this method, you provide the native python
    # value you'd like the flags to take on. Otherwise it functions similar to
    # flagsaver.as_parsed().
    @flagsaver.flagsaver((INT_FLAG, 345))
    def do_something_with_flags():
      self.assertEqual(345, INT_FLAG.value)
      # Note that because this flag was never parsed, it will not register as
      # .present unless you manually set that attribute.
      self.assertFalse(INT_FLAG.present)
      # If you do chose to modify things about the flag (such as .present) those
      # changes will still be cleaned up when flagsaver.flagsaver() exits.
      INT_FLAG.present = True

    self.assertEqual(1, INT_FLAG.value)
    # flagsaver.flagsaver() restored INT_FLAG.present to the state it was in
    # before entering the context.
    self.assertFalse(INT_FLAG.present)


class SaveFlagValuesTest(absltest.TestCase):
  """Test flagsaver.save_flag_values() and flagsaver.restore_flag_values().

  In this test, we insure that *all* properties of flags get restored. In other
  tests we only try changing the flag value.
  """

  def test_assign_value(self):
    # First save the flag values.
    saved_flag_values = flagsaver.save_flag_values()

    # Now mutate the flag's value field and check that it changed.
    FLAGS.flagsaver_test_flag0 = 'new value'
    self.assertEqual('new value', FLAGS.flagsaver_test_flag0)

    # Now restore the flag to its original value.
    flagsaver.restore_flag_values(saved_flag_values)
    self.assertEqual('unchanged0', FLAGS.flagsaver_test_flag0)

  def test_set_default(self):
    # First save the flag.
    saved_flag_values = flagsaver.save_flag_values()

    # Now mutate the flag's default field and check that it changed.
    FLAGS.set_default('flagsaver_test_flag0', 'new_default')
    self.assertEqual('new_default', FLAGS['flagsaver_test_flag0'].default)

    # Now restore the flag's default field.
    flagsaver.restore_flag_values(saved_flag_values)
    self.assertEqual('unchanged0', FLAGS['flagsaver_test_flag0'].default)

  def test_parse(self):
    # First save the flag.
    saved_flag_values = flagsaver.save_flag_values()

    # Sanity check (would fail if called with --flagsaver_test_flag0).
    self.assertEqual(0, FLAGS['flagsaver_test_flag0'].present)
    # Now populate the flag and check that it changed.
    FLAGS['flagsaver_test_flag0'].parse('new value')
    self.assertEqual('new value', FLAGS['flagsaver_test_flag0'].value)
    self.assertEqual(1, FLAGS['flagsaver_test_flag0'].present)

    # Now restore the flag to its original value.
    flagsaver.restore_flag_values(saved_flag_values)
    self.assertEqual('unchanged0', FLAGS['flagsaver_test_flag0'].value)
    self.assertEqual(0, FLAGS['flagsaver_test_flag0'].present)

  def test_assign_validators(self):
    # First save the flag.
    saved_flag_values = flagsaver.save_flag_values()

    # Sanity check that a validator already exists.
    self.assertLen(FLAGS['flagsaver_test_flag0'].validators, 1)
    original_validators = list(FLAGS['flagsaver_test_flag0'].validators)

    def no_space(value):
      return ' ' not in value

    # Add a new validator.
    flags.register_validator('flagsaver_test_flag0', no_space)
    self.assertLen(FLAGS['flagsaver_test_flag0'].validators, 2)

    # Now restore the flag to its original value.
    flagsaver.restore_flag_values(saved_flag_values)
    self.assertEqual(
        original_validators, FLAGS['flagsaver_test_flag0'].validators
    )


@parameterized.named_parameters(
    dict(
        testcase_name='flagsaver.flagsaver',
        flagsaver_method=flagsaver.flagsaver,
    ),
    dict(
        testcase_name='flagsaver.as_parsed',
        flagsaver_method=flagsaver.as_parsed,
    ),
)
class NoOverridesTest(parameterized.TestCase):
  """Test flagsaver.flagsaver and flagsaver.as_parsed without overrides."""

  def test_context_manager_with_call(self, flagsaver_method):
    with flagsaver_method():
      FLAGS.flagsaver_test_flag0 = 'new value'
    self.assertEqual('unchanged0', FLAGS.flagsaver_test_flag0)

  def test_context_manager_with_exception(self, flagsaver_method):
    with self.assertRaises(_TestError):
      with flagsaver_method():
        FLAGS.flagsaver_test_flag0 = 'new value'
        # Simulate a failed test.
        raise _TestError('something happened')
    self.assertEqual('unchanged0', FLAGS.flagsaver_test_flag0)

  def test_decorator_without_call(self, flagsaver_method):
    @flagsaver_method
    def mutate_flags():
      FLAGS.flagsaver_test_flag0 = 'new value'

    mutate_flags()
    self.assertEqual('unchanged0', FLAGS.flagsaver_test_flag0)

  def test_decorator_with_call(self, flagsaver_method):
    @flagsaver_method()
    def mutate_flags():
      FLAGS.flagsaver_test_flag0 = 'new value'

    mutate_flags()
    self.assertEqual('unchanged0', FLAGS.flagsaver_test_flag0)

  def test_decorator_with_exception(self, flagsaver_method):
    @flagsaver_method()
    def raise_exception():
      FLAGS.flagsaver_test_flag0 = 'new value'
      # Simulate a failed test.
      raise _TestError('something happened')

    self.assertEqual('unchanged0', FLAGS.flagsaver_test_flag0)
    self.assertRaises(_TestError, raise_exception)
    self.assertEqual('unchanged0', FLAGS.flagsaver_test_flag0)


@parameterized.named_parameters(
    dict(
        testcase_name='flagsaver.flagsaver',
        flagsaver_method=flagsaver.flagsaver,
    ),
    dict(
        testcase_name='flagsaver.as_parsed',
        flagsaver_method=flagsaver.as_parsed,
    ),
)
class TestStringFlagOverrides(parameterized.TestCase):
  """Test flagsaver.flagsaver and flagsaver.as_parsed with string overrides.

  Note that these tests can be parameterized because both .flagsaver and
  .as_parsed expect a str input when overriding a string flag. For non-string
  flags these two flagsaver methods have separate tests elsewhere in this file.

  Each test is one class of overrides, executed twice. Once as a context
  manager, and once as a decorator on a mutate_flags() method.
  """

  def test_keyword_overrides(self, flagsaver_method):
    # Context manager:
    with flagsaver_method(flagsaver_test_flag0='new value'):
      self.assertEqual('new value', FLAGS.flagsaver_test_flag0)
    self.assertEqual('unchanged0', FLAGS.flagsaver_test_flag0)

    # Decorator:
    @flagsaver_method(flagsaver_test_flag0='new value')
    def mutate_flags():
      self.assertEqual('new value', FLAGS.flagsaver_test_flag0)

    mutate_flags()
    self.assertEqual('unchanged0', FLAGS.flagsaver_test_flag0)

  def test_flagholder_overrides(self, flagsaver_method):
    with flagsaver_method((STR_FLAG, 'new value')):
      self.assertEqual('new value', STR_FLAG.value)
    self.assertEqual('str default', STR_FLAG.value)

    @flagsaver