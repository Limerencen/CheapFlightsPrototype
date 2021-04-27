
# Copyright 2018 The Abseil Authors.
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

"""Tests for absl.flags.argparse_flags."""

import io
import os
import subprocess
import sys
import tempfile
from unittest import mock

from absl import flags
from absl import logging
from absl.flags import argparse_flags
from absl.testing import _bazelize_command
from absl.testing import absltest
from absl.testing import parameterized


class ArgparseFlagsTest(parameterized.TestCase):

  def setUp(self):
    super().setUp()
    self._absl_flags = flags.FlagValues()
    flags.DEFINE_bool(
        'absl_bool', None, 'help for --absl_bool.',
        short_name='b', flag_values=self._absl_flags)
    # Add a boolean flag that starts with "no", to verify it can correctly
    # handle the "no" prefixes in boolean flags.
    flags.DEFINE_bool(
        'notice', None, 'help for --notice.',
        flag_values=self._absl_flags)
    flags.DEFINE_string(
        'absl_string', 'default', 'help for --absl_string=%.',
        short_name='s', flag_values=self._absl_flags)
    flags.DEFINE_integer(
        'absl_integer', 1, 'help for --absl_integer.',
        flag_values=self._absl_flags)
    flags.DEFINE_float(
        'absl_float', 1, 'help for --absl_integer.',
        flag_values=self._absl_flags)
    flags.DEFINE_enum(
        'absl_enum', 'apple', ['apple', 'orange'], 'help for --absl_enum.',
        flag_values=self._absl_flags)

  def test_dash_as_prefix_char_only(self):
    with self.assertRaises(ValueError):
      argparse_flags.ArgumentParser(prefix_chars='/')

  def test_default_inherited_absl_flags_value(self):
    parser = argparse_flags.ArgumentParser()
    self.assertIs(parser._inherited_absl_flags, flags.FLAGS)

  def test_parse_absl_flags(self):
    parser = argparse_flags.ArgumentParser(
        inherited_absl_flags=self._absl_flags)
    self.assertFalse(self._absl_flags.is_parsed())
    self.assertTrue(self._absl_flags['absl_string'].using_default_value)
    self.assertTrue(self._absl_flags['absl_integer'].using_default_value)
    self.assertTrue(self._absl_flags['absl_float'].using_default_value)
    self.assertTrue(self._absl_flags['absl_enum'].using_default_value)

    parser.parse_args(
        ['--absl_string=new_string', '--absl_integer', '2'])
    self.assertEqual(self._absl_flags.absl_string, 'new_string')
    self.assertEqual(self._absl_flags.absl_integer, 2)
    self.assertTrue(self._absl_flags.is_parsed())
    self.assertFalse(self._absl_flags['absl_string'].using_default_value)
    self.assertFalse(self._absl_flags['absl_integer'].using_default_value)
    self.assertTrue(self._absl_flags['absl_float'].using_default_value)
    self.assertTrue(self._absl_flags['absl_enum'].using_default_value)

  @parameterized.named_parameters(
      ('true', ['--absl_bool'], True),
      ('false', ['--noabsl_bool'], False),
      ('does_not_accept_equal_value', ['--absl_bool=true'], SystemExit),
      ('does_not_accept_space_value', ['--absl_bool', 'true'], SystemExit),
      ('long_name_single_dash', ['-absl_bool'], SystemExit),
      ('short_name', ['-b'], True),
      ('short_name_false', ['-nob'], SystemExit),
      ('short_name_double_dash', ['--b'], SystemExit),
      ('short_name_double_dash_false', ['--nob'], SystemExit),
  )
  def test_parse_boolean_flags(self, args, expected):
    parser = argparse_flags.ArgumentParser(
        inherited_absl_flags=self._absl_flags)
    self.assertIsNone(self._absl_flags['absl_bool'].value)
    self.assertIsNone(self._absl_flags['b'].value)
    if isinstance(expected, bool):
      parser.parse_args(args)
      self.assertEqual(expected, self._absl_flags.absl_bool)
      self.assertEqual(expected, self._absl_flags.b)
    else:
      with self.assertRaises(expected):
        parser.parse_args(args)

  @parameterized.named_parameters(
      ('true', ['--notice'], True),
      ('false', ['--nonotice'], False),
  )
  def test_parse_boolean_existing_no_prefix(self, args, expected):
    parser = argparse_flags.ArgumentParser(
        inherited_absl_flags=self._absl_flags)
    self.assertIsNone(self._absl_flags['notice'].value)
    parser.parse_args(args)
    self.assertEqual(expected, self._absl_flags.notice)

  def test_unrecognized_flag(self):
    parser = argparse_flags.ArgumentParser(
        inherited_absl_flags=self._absl_flags)
    with self.assertRaises(SystemExit):
      parser.parse_args(['--unknown_flag=what'])

  def test_absl_validators(self):

    @flags.validator('absl_integer', flag_values=self._absl_flags)
    def ensure_positive(value):
      return value > 0

    parser = argparse_flags.ArgumentParser(
        inherited_absl_flags=self._absl_flags)
    with self.assertRaises(SystemExit):
      parser.parse_args(['--absl_integer', '-2'])

    del ensure_positive

  @parameterized.named_parameters(
      ('regular_name_double_dash', '--absl_string=new_string', 'new_string'),
      ('regular_name_single_dash', '-absl_string=new_string', SystemExit),
      ('short_name_double_dash', '--s=new_string', SystemExit),
      ('short_name_single_dash', '-s=new_string', 'new_string'),
  )
  def test_dashes(self, argument, expected):
    parser = argparse_flags.ArgumentParser(
        inherited_absl_flags=self._absl_flags)
    if isinstance(expected, str):
      parser.parse_args([argument])
      self.assertEqual(self._absl_flags.absl_string, expected)
    else:
      with self.assertRaises(expected):
        parser.parse_args([argument])

  def test_absl_flags_not_added_to_namespace(self):
    parser = argparse_flags.ArgumentParser(
        inherited_absl_flags=self._absl_flags)
    args = parser.parse_args(['--absl_string=new_string'])
    self.assertIsNone(getattr(args, 'absl_string', None))

  def test_mixed_flags_and_positional(self):
    parser = argparse_flags.ArgumentParser(
        inherited_absl_flags=self._absl_flags)
    parser.add_argument('--header', help='Header message to print.')
    parser.add_argument('integers', metavar='N', type=int, nargs='+',
                        help='an integer for the accumulator')

    args = parser.parse_args(
        ['--absl_string=new_string', '--header=HEADER', '--absl_integer',
         '2', '3', '4'])
    self.assertEqual(self._absl_flags.absl_string, 'new_string')
    self.assertEqual(self._absl_flags.absl_integer, 2)
    self.assertEqual(args.header, 'HEADER')
    self.assertListEqual(args.integers, [3, 4])

  def test_subparsers(self):
    parser = argparse_flags.ArgumentParser(
        inherited_absl_flags=self._absl_flags)
    parser.add_argument('--header', help='Header message to print.')
    subparsers = parser.add_subparsers(help='The command to execute.')

    sub_parser = subparsers.add_parser(
        'sub_cmd', help='Sub command.', inherited_absl_flags=self._absl_flags)
    sub_parser.add_argument('--sub_flag', help='Sub command flag.')

    def sub_command_func():
      pass

    sub_parser.set_defaults(command=sub_command_func)

    args = parser.parse_args([
        '--header=HEADER', '--absl_string=new_value', 'sub_cmd',
        '--absl_integer=2', '--sub_flag=new_sub_flag_value'])

    self.assertEqual(args.header, 'HEADER')
    self.assertEqual(self._absl_flags.absl_string, 'new_value')
    self.assertEqual(args.command, sub_command_func)
    self.assertEqual(self._absl_flags.absl_integer, 2)
    self.assertEqual(args.sub_flag, 'new_sub_flag_value')

  def test_subparsers_no_inherit_in_subparser(self):
    parser = argparse_flags.ArgumentParser(
        inherited_absl_flags=self._absl_flags)
    subparsers = parser.add_subparsers(help='The command to execute.')

    subparsers.add_parser(
        'sub_cmd', help='Sub command.',
        # Do not inherit absl flags in the subparser.
        # This is the behavior that this test exercises.
        inherited_absl_flags=None)

    with self.assertRaises(SystemExit):
      parser.parse_args(['sub_cmd', '--absl_string=new_value'])

  def test_help_main_module_flags(self):
    parser = argparse_flags.ArgumentParser(
        inherited_absl_flags=self._absl_flags)