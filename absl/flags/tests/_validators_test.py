
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

"""Testing that flags validators framework does work.

This file tests that each flag validator called when it should be, and that
failed validator will throw an exception, etc.
"""

import warnings


from absl.flags import _defines
from absl.flags import _exceptions
from absl.flags import _flagvalues
from absl.flags import _validators
from absl.testing import absltest


class SingleFlagValidatorTest(absltest.TestCase):
  """Testing _validators.register_validator() method."""

  def setUp(self):
    super(SingleFlagValidatorTest, self).setUp()
    self.flag_values = _flagvalues.FlagValues()
    self.call_args = []

  def test_success(self):
    def checker(x):
      self.call_args.append(x)
      return True
    _defines.DEFINE_integer(
        'test_flag', None, 'Usual integer flag', flag_values=self.flag_values)
    _validators.register_validator(
        'test_flag',
        checker,
        message='Errors happen',
        flag_values=self.flag_values)

    argv = ('./program',)
    self.flag_values(argv)
    self.assertIsNone(self.flag_values.test_flag)
    self.flag_values.test_flag = 2
    self.assertEqual(2, self.flag_values.test_flag)
    self.assertEqual([None, 2], self.call_args)

  def test_success_holder(self):
    def checker(x):
      self.call_args.append(x)
      return True

    flag_holder = _defines.DEFINE_integer(
        'test_flag', None, 'Usual integer flag', flag_values=self.flag_values)
    _validators.register_validator(
        flag_holder,
        checker,
        message='Errors happen',
        flag_values=self.flag_values)

    argv = ('./program',)
    self.flag_values(argv)
    self.assertIsNone(self.flag_values.test_flag)
    self.flag_values.test_flag = 2
    self.assertEqual(2, self.flag_values.test_flag)
    self.assertEqual([None, 2], self.call_args)

  def test_success_holder_infer_flagvalues(self):
    def checker(x):
      self.call_args.append(x)
      return True

    flag_holder = _defines.DEFINE_integer(
        'test_flag', None, 'Usual integer flag', flag_values=self.flag_values)
    _validators.register_validator(
        flag_holder,
        checker,
        message='Errors happen')

    argv = ('./program',)
    self.flag_values(argv)
    self.assertIsNone(self.flag_values.test_flag)
    self.flag_values.test_flag = 2
    self.assertEqual(2, self.flag_values.test_flag)
    self.assertEqual([None, 2], self.call_args)

  def test_default_value_not_used_success(self):
    def checker(x):
      self.call_args.append(x)
      return True
    _defines.DEFINE_integer(
        'test_flag', None, 'Usual integer flag', flag_values=self.flag_values)
    _validators.register_validator(
        'test_flag',
        checker,
        message='Errors happen',
        flag_values=self.flag_values)

    argv = ('./program', '--test_flag=1')
    self.flag_values(argv)
    self.assertEqual(1, self.flag_values.test_flag)
    self.assertEqual([1], self.call_args)

  def test_validator_not_called_when_other_flag_is_changed(self):
    def checker(x):
      self.call_args.append(x)
      return True
    _defines.DEFINE_integer(
        'test_flag', 1, 'Usual integer flag', flag_values=self.flag_values)
    _defines.DEFINE_integer(
        'other_flag', 2, 'Other integer flag', flag_values=self.flag_values)
    _validators.register_validator(
        'test_flag',
        checker,
        message='Errors happen',
        flag_values=self.flag_values)

    argv = ('./program',)
    self.flag_values(argv)
    self.assertEqual(1, self.flag_values.test_flag)
    self.flag_values.other_flag = 3
    self.assertEqual([1], self.call_args)

  def test_exception_raised_if_checker_fails(self):
    def checker(x):
      self.call_args.append(x)
      return x == 1
    _defines.DEFINE_integer(
        'test_flag', None, 'Usual integer flag', flag_values=self.flag_values)
    _validators.register_validator(
        'test_flag',
        checker,
        message='Errors happen',
        flag_values=self.flag_values)

    argv = ('./program', '--test_flag=1')
    self.flag_values(argv)
    with self.assertRaises(_exceptions.IllegalFlagValueError) as cm:
      self.flag_values.test_flag = 2
    self.assertEqual('flag --test_flag=2: Errors happen', str(cm.exception))
    self.assertEqual([1, 2], self.call_args)

  def test_exception_raised_if_checker_raises_exception(self):
    def checker(x):
      self.call_args.append(x)
      if x == 1:
        return True
      raise _exceptions.ValidationError('Specific message')

    _defines.DEFINE_integer(
        'test_flag', None, 'Usual integer flag', flag_values=self.flag_values)
    _validators.register_validator(
        'test_flag',
        checker,
        message='Errors happen',
        flag_values=self.flag_values)

    argv = ('./program', '--test_flag=1')
    self.flag_values(argv)
    with self.assertRaises(_exceptions.IllegalFlagValueError) as cm:
      self.flag_values.test_flag = 2
    self.assertEqual('flag --test_flag=2: Specific message', str(cm.exception))
    self.assertEqual([1, 2], self.call_args)

  def test_error_message_when_checker_returns_false_on_start(self):
    def checker(x):
      self.call_args.append(x)
      return False
    _defines.DEFINE_integer(
        'test_flag', None, 'Usual integer flag', flag_values=self.flag_values)
    _validators.register_validator(
        'test_flag',
        checker,
        message='Errors happen',
        flag_values=self.flag_values)

    argv = ('./program', '--test_flag=1')
    with self.assertRaises(_exceptions.IllegalFlagValueError) as cm:
      self.flag_values(argv)
    self.assertEqual('flag --test_flag=1: Errors happen', str(cm.exception))
    self.assertEqual([1], self.call_args)

  def test_error_message_when_checker_raises_exception_on_start(self):
    def checker(x):
      self.call_args.append(x)
      raise _exceptions.ValidationError('Specific message')

    _defines.DEFINE_integer(
        'test_flag', None, 'Usual integer flag', flag_values=self.flag_values)
    _validators.register_validator(
        'test_flag',
        checker,
        message='Errors happen',
        flag_values=self.flag_values)

    argv = ('./program', '--test_flag=1')
    with self.assertRaises(_exceptions.IllegalFlagValueError) as cm:
      self.flag_values(argv)
    self.assertEqual('flag --test_flag=1: Specific message', str(cm.exception))
    self.assertEqual([1], self.call_args)

  def test_validators_checked_in_order(self):

    def required(x):
      self.calls.append('required')
      return x is not None

    def even(x):
      self.calls.append('even')
      return x % 2 == 0

    self.calls = []
    self._define_flag_and_validators(required, even)
    self.assertEqual(['required', 'even'], self.calls)

    self.calls = []
    self._define_flag_and_validators(even, required)
    self.assertEqual(['even', 'required'], self.calls)

  def _define_flag_and_validators(self, first_validator, second_validator):
    local_flags = _flagvalues.FlagValues()
    _defines.DEFINE_integer(
        'test_flag', 2, 'test flag', flag_values=local_flags)
    _validators.register_validator(
        'test_flag', first_validator, message='', flag_values=local_flags)
    _validators.register_validator(
        'test_flag', second_validator, message='', flag_values=local_flags)
    argv = ('./program',)
    local_flags(argv)

  def test_validator_as_decorator(self):
    _defines.DEFINE_integer(
        'test_flag', None, 'Simple integer flag', flag_values=self.flag_values)

    @_validators.validator('test_flag', flag_values=self.flag_values)
    def checker(x):
      self.call_args.append(x)
      return True

    argv = ('./program',)
    self.flag_values(argv)
    self.assertIsNone(self.flag_values.test_flag)
    self.flag_values.test_flag = 2
    self.assertEqual(2, self.flag_values.test_flag)
    self.assertEqual([None, 2], self.call_args)
    # Check that 'Checker' is still a function and has not been replaced.
    self.assertTrue(checker(3))
    self.assertEqual([None, 2, 3], self.call_args)

  def test_mismatching_flagvalues(self):

    def checker(x):
      self.call_args.append(x)
      return True

    flag_holder = _defines.DEFINE_integer(
        'test_flag',
        None,
        'Usual integer flag',
        flag_values=_flagvalues.FlagValues())
    expected = (
        'flag_values must not be customized when operating on a FlagHolder')
    with self.assertRaisesWithLiteralMatch(ValueError, expected):
      _validators.register_validator(
          flag_holder,
          checker,
          message='Errors happen',
          flag_values=self.flag_values)


class MultiFlagsValidatorTest(absltest.TestCase):
  """Test flags multi-flag validators."""

  def setUp(self):
    super(MultiFlagsValidatorTest, self).setUp()
    self.flag_values = _flagvalues.FlagValues()
    self.call_args = []
    self.foo_holder = _defines.DEFINE_integer(
        'foo', 1, 'Usual integer flag', flag_values=self.flag_values)
    self.bar_holder = _defines.DEFINE_integer(
        'bar', 2, 'Usual integer flag', flag_values=self.flag_values)

  def test_success(self):
    def checker(flags_dict):
      self.call_args.append(flags_dict)
      return True
    _validators.register_multi_flags_validator(
        ['foo', 'bar'], checker, flag_values=self.flag_values)

    argv = ('./program', '--bar=2')
    self.flag_values(argv)
    self.assertEqual(1, self.flag_values.foo)
    self.assertEqual(2, self.flag_values.bar)
    self.assertEqual([{'foo': 1, 'bar': 2}], self.call_args)
    self.flag_values.foo = 3
    self.assertEqual(3, self.flag_values.foo)
    self.assertEqual([{'foo': 1, 'bar': 2}, {'foo': 3, 'bar': 2}],
                     self.call_args)

  def test_success_holder(self):

    def checker(flags_dict):
      self.call_args.append(flags_dict)
      return True

    _validators.register_multi_flags_validator(
        [self.foo_holder, self.bar_holder],
        checker,
        flag_values=self.flag_values)

    argv = ('./program', '--bar=2')
    self.flag_values(argv)
    self.assertEqual(1, self.flag_values.foo)
    self.assertEqual(2, self.flag_values.bar)
    self.assertEqual([{'foo': 1, 'bar': 2}], self.call_args)
    self.flag_values.foo = 3
    self.assertEqual(3, self.flag_values.foo)
    self.assertEqual([{
        'foo': 1,
        'bar': 2
    }, {
        'foo': 3,
        'bar': 2
    }], self.call_args)

  def test_success_holder_infer_flagvalues(self):
    def checker(flags_dict):
      self.call_args.append(flags_dict)
      return True

    _validators.register_multi_flags_validator(
        [self.foo_holder, self.bar_holder], checker)

    argv = ('./program', '--bar=2')
    self.flag_values(argv)
    self.assertEqual(1, self.flag_values.foo)
    self.assertEqual(2, self.flag_values.bar)
    self.assertEqual([{'foo': 1, 'bar': 2}], self.call_args)
    self.flag_values.foo = 3
    self.assertEqual(3, self.flag_values.foo)
    self.assertEqual([{
        'foo': 1,
        'bar': 2
    }, {
        'foo': 3,
        'bar': 2
    }], self.call_args)

  def test_validator_not_called_when_other_flag_is_changed(self):
    def checker(flags_dict):
      self.call_args.append(flags_dict)
      return True
    _defines.DEFINE_integer(
        'other_flag', 3, 'Other integer flag', flag_values=self.flag_values)
    _validators.register_multi_flags_validator(
        ['foo', 'bar'], checker, flag_values=self.flag_values)

    argv = ('./program',)
    self.flag_values(argv)
    self.flag_values.other_flag = 3
    self.assertEqual([{'foo': 1, 'bar': 2}], self.call_args)

  def test_exception_raised_if_checker_fails(self):
    def checker(flags_dict):
      self.call_args.append(flags_dict)
      values = flags_dict.values()
      # Make sure all the flags have different values.
      return len(set(values)) == len(values)