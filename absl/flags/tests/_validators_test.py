
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