
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
"""Tests for absl.flags used as a package."""

import contextlib
import enum
import io
import os
import shutil
import sys
import tempfile
import unittest

from absl import flags
from absl.flags import _exceptions
from absl.flags import _helpers
from absl.flags.tests import module_bar
from absl.flags.tests import module_baz
from absl.flags.tests import module_foo
from absl.testing import absltest

FLAGS = flags.FLAGS


@contextlib.contextmanager
def _use_gnu_getopt(flag_values, use_gnu_get_opt):
  old_use_gnu_get_opt = flag_values.is_gnu_getopt()
  flag_values.set_gnu_getopt(use_gnu_get_opt)
  yield
  flag_values.set_gnu_getopt(old_use_gnu_get_opt)


class FlagDictToArgsTest(absltest.TestCase):

  def test_flatten_google_flag_map(self):
    arg_dict = {
        'week-end': None,
        'estudia': False,
        'trabaja': False,
        'party': True,
        'monday': 'party',
        'score': 42,
        'loadthatstuff': [42, 'hello', 'goodbye'],
    }
    self.assertSameElements(
        ('--week-end', '--noestudia', '--notrabaja', '--party',
         '--monday=party', '--score=42', '--loadthatstuff=42,hello,goodbye'),
        flags.flag_dict_to_args(arg_dict))

  def test_flatten_google_flag_map_with_multi_flag(self):
    arg_dict = {
        'some_list': ['value1', 'value2'],
        'some_multi_string': ['value3', 'value4'],
    }
    self.assertSameElements(
        ('--some_list=value1,value2', '--some_multi_string=value3',
         '--some_multi_string=value4'),
        flags.flag_dict_to_args(arg_dict, multi_flags={'some_multi_string'}))


class Fruit(enum.Enum):
  APPLE = object()
  ORANGE = object()


class CaseSensitiveFruit(enum.Enum):
  apple = 1
  orange = 2
  APPLE = 3


class EmptyEnum(enum.Enum):
  pass


class AliasFlagsTest(absltest.TestCase):

  def setUp(self):
    super(AliasFlagsTest, self).setUp()
    self.flags = flags.FlagValues()

  @property
  def alias(self):
    return self.flags['alias']

  @property
  def aliased(self):
    return self.flags['aliased']

  def define_alias(self, *args, **kwargs):
    flags.DEFINE_alias(*args, flag_values=self.flags, **kwargs)

  def define_integer(self, *args, **kwargs):
    flags.DEFINE_integer(*args, flag_values=self.flags, **kwargs)

  def define_multi_integer(self, *args, **kwargs):
    flags.DEFINE_multi_integer(*args, flag_values=self.flags, **kwargs)

  def define_string(self, *args, **kwargs):
    flags.DEFINE_string(*args, flag_values=self.flags, **kwargs)

  def assert_alias_mirrors_aliased(self, alias, aliased, ignore_due_to_bug=()):
    # A few sanity checks to avoid false success
    self.assertIn('FlagAlias', alias.__class__.__qualname__)
    self.assertIsNot(alias, aliased)
    self.assertNotEqual(aliased.name, alias.name)

    alias_state = {}
    aliased_state = {}
    attrs = {
        'allow_hide_cpp',
        'allow_override',
        'allow_override_cpp',
        'allow_overwrite',
        'allow_using_method_names',
        'boolean',
        'default',
        'default_as_str',
        'default_unparsed',
        # TODO(rlevasseur): This should match, but a bug prevents it from being
        # in sync.
        # 'using_default_value',
        'value',
    }
    attrs.difference_update(ignore_due_to_bug)

    for attr in attrs:
      alias_state[attr] = getattr(alias, attr)
      aliased_state[attr] = getattr(aliased, attr)

    self.assertEqual(aliased_state, alias_state, 'LHS is aliased; RHS is alias')

  def test_serialize_multi(self):
    self.define_multi_integer('aliased', [0, 1], '')
    self.define_alias('alias', 'aliased')

    actual = self.alias.serialize()
    # TODO(rlevasseur): This should check for --alias=0\n--alias=1, but
    # a bug causes it to serialize incorrectly.
    self.assertEqual('--alias=[0, 1]', actual)

  def test_allow_overwrite_false(self):
    self.define_integer('aliased', None, 'help', allow_overwrite=False)
    self.define_alias('alias', 'aliased')

    with self.assertRaisesRegex(flags.IllegalFlagValueError, 'already defined'):
      self.flags(['./program', '--alias=1', '--aliased=2'])

    self.assertEqual(1, self.alias.value)
    self.assertEqual(1, self.aliased.value)

  def test_aliasing_multi_no_default(self):

    def define_flags():
      self.flags = flags.FlagValues()
      self.define_multi_integer('aliased', None, 'help')
      self.define_alias('alias', 'aliased')

    with self.subTest('after defining'):
      define_flags()
      self.assert_alias_mirrors_aliased(self.alias, self.aliased)
      self.assertIsNone(self.alias.value)

    with self.subTest('set alias'):
      define_flags()
      self.flags(['./program', '--alias=1', '--alias=2'])
      self.assertEqual([1, 2], self.alias.value)
      self.assert_alias_mirrors_aliased(self.alias, self.aliased)

    with self.subTest('set aliased'):
      define_flags()
      self.flags(['./program', '--aliased=1', '--aliased=2'])
      self.assertEqual([1, 2], self.alias.value)
      self.assert_alias_mirrors_aliased(self.alias, self.aliased)

    with self.subTest('not setting anything'):
      define_flags()
      self.flags(['./program'])
      self.assertEqual(None, self.alias.value)
      self.assert_alias_mirrors_aliased(self.alias, self.aliased)

  def test_aliasing_multi_with_default(self):

    def define_flags():
      self.flags = flags.FlagValues()
      self.define_multi_integer('aliased', [0], 'help')
      self.define_alias('alias', 'aliased')

    with self.subTest('after defining'):
      define_flags()
      self.assertEqual([0], self.alias.default)
      self.assert_alias_mirrors_aliased(self.alias, self.aliased)

    with self.subTest('set alias'):
      define_flags()
      self.flags(['./program', '--alias=1', '--alias=2'])
      self.assertEqual([1, 2], self.alias.value)
      self.assert_alias_mirrors_aliased(self.alias, self.aliased)

      self.assertEqual(2, self.alias.present)
      # TODO(rlevasseur): This should assert 0, but a bug with aliases and
      # MultiFlag causes the alias to increment aliased's present counter.
      self.assertEqual(2, self.aliased.present)

    with self.subTest('set aliased'):
      define_flags()
      self.flags(['./program', '--aliased=1', '--aliased=2'])
      self.assertEqual([1, 2], self.alias.value)
      self.assert_alias_mirrors_aliased(self.alias, self.aliased)
      self.assertEqual(0, self.alias.present)

      # TODO(rlevasseur): This should assert 0, but a bug with aliases and
      # MultiFlag causes the alias to increment aliased present counter.
      self.assertEqual(2, self.aliased.present)

    with self.subTest('not setting anything'):
      define_flags()
      self.flags(['./program'])
      self.assertEqual([0], self.alias.value)
      self.assert_alias_mirrors_aliased(self.alias, self.aliased)
      self.assertEqual(0, self.alias.present)
      self.assertEqual(0, self.aliased.present)

  def test_aliasing_regular(self):

    def define_flags():
      self.flags = flags.FlagValues()
      self.define_string('aliased', '', 'help')
      self.define_alias('alias', 'aliased')

    define_flags()
    self.assert_alias_mirrors_aliased(self.alias, self.aliased)

    self.flags(['./program', '--alias=1'])
    self.assertEqual('1', self.alias.value)
    self.assert_alias_mirrors_aliased(self.alias, self.aliased)
    self.assertEqual(1, self.alias.present)
    self.assertEqual('--alias=1', self.alias.serialize())
    self.assertEqual(1, self.aliased.present)

    define_flags()
    self.flags(['./program', '--aliased=2'])
    self.assertEqual('2', self.alias.value)
    self.assert_alias_mirrors_aliased(self.alias, self.aliased)
    self.assertEqual(0, self.alias.present)
    self.assertEqual('--alias=2', self.alias.serialize())
    self.assertEqual(1, self.aliased.present)

  def test_defining_alias_doesnt_affect_aliased_state_regular(self):
    self.define_string('aliased', 'default', 'help')
    self.define_alias('alias', 'aliased')

    self.assertEqual(0, self.aliased.present)
    self.assertEqual(0, self.alias.present)

  def test_defining_alias_doesnt_affect_aliased_state_multi(self):
    self.define_multi_integer('aliased', [0], 'help')
    self.define_alias('alias', 'aliased')

    self.assertEqual([0], self.aliased.value)
    self.assertEqual([0], self.aliased.default)
    self.assertEqual(0, self.aliased.present)

    self.assertEqual([0], self.aliased.value)
    self.assertEqual([0], self.aliased.default)
    self.assertEqual(0, self.alias.present)


class FlagsUnitTest(absltest.TestCase):
  """Flags Unit Test."""

  maxDiff = None

  def test_flags(self):
    """Test normal usage with no (expected) errors."""
    # Define flags
    number_test_framework_flags = len(FLAGS)
    repeat_help = 'how many times to repeat (0-5)'
    flags.DEFINE_integer(
        'repeat', 4, repeat_help, lower_bound=0, short_name='r')
    flags.DEFINE_string('name', 'Bob', 'namehelp')
    flags.DEFINE_boolean('debug', 0, 'debughelp')
    flags.DEFINE_boolean('q', 1, 'quiet mode')
    flags.DEFINE_boolean('quack', 0, "superstring of 'q'")
    flags.DEFINE_boolean('noexec', 1, 'boolean flag with no as prefix')
    flags.DEFINE_float('float', 3.14, 'using floats')
    flags.DEFINE_integer('octal', '0o666', 'using octals')
    flags.DEFINE_integer('decimal', '666', 'using decimals')
    flags.DEFINE_integer('hexadecimal', '0x666', 'using hexadecimals')
    flags.DEFINE_integer('x', 3, 'how eXtreme to be')
    flags.DEFINE_integer('l', 0x7fffffff00000000, 'how long to be')
    flags.DEFINE_list('args', 'v=1,"vmodule=a=0,b=2"', 'a list of arguments')
    flags.DEFINE_list('letters', 'a,b,c', 'a list of letters')
    flags.DEFINE_list('numbers', [1, 2, 3], 'a list of numbers')
    flags.DEFINE_enum('kwery', None, ['who', 'what', 'Why', 'where', 'when'],
                      '?')
    flags.DEFINE_enum(
        'sense', None, ['Case', 'case', 'CASE'], '?', case_sensitive=True)
    flags.DEFINE_enum(
        'cases',
        None, ['UPPER', 'lower', 'Initial', 'Ot_HeR'],
        '?',
        case_sensitive=False)
    flags.DEFINE_enum(
        'funny',
        None, ['Joke', 'ha', 'ha', 'ha', 'ha'],
        '?',
        case_sensitive=True)
    flags.DEFINE_enum(
        'blah',
        None, ['bla', 'Blah', 'BLAH', 'blah'],
        '?',
        case_sensitive=False)
    flags.DEFINE_string(
        'only_once', None, 'test only sets this once', allow_overwrite=False)
    flags.DEFINE_string(
        'universe',
        None,
        'test tries to set this three times',
        allow_overwrite=False)

    # Specify number of flags defined above.  The short_name defined
    # for 'repeat' counts as an extra flag.
    number_defined_flags = 22 + 1
    self.assertLen(FLAGS, number_defined_flags + number_test_framework_flags)

    self.assertEqual(FLAGS.repeat, 4)
    self.assertEqual(FLAGS.name, 'Bob')
    self.assertEqual(FLAGS.debug, 0)
    self.assertEqual(FLAGS.q, 1)
    self.assertEqual(FLAGS.octal, 0o666)
    self.assertEqual(FLAGS.decimal, 666)
    self.assertEqual(FLAGS.hexadecimal, 0x666)
    self.assertEqual(FLAGS.x, 3)
    self.assertEqual(FLAGS.l, 0x7fffffff00000000)
    self.assertEqual(FLAGS.args, ['v=1', 'vmodule=a=0,b=2'])
    self.assertEqual(FLAGS.letters, ['a', 'b', 'c'])
    self.assertEqual(FLAGS.numbers, [1, 2, 3])
    self.assertIsNone(FLAGS.kwery)
    self.assertIsNone(FLAGS.sense)
    self.assertIsNone(FLAGS.cases)
    self.assertIsNone(FLAGS.funny)
    self.assertIsNone(FLAGS.blah)

    flag_values = FLAGS.flag_values_dict()
    self.assertEqual(flag_values['repeat'], 4)
    self.assertEqual(flag_values['name'], 'Bob')
    self.assertEqual(flag_values['debug'], 0)
    self.assertEqual(flag_values['r'], 4)  # Short for repeat.
    self.assertEqual(flag_values['q'], 1)
    self.assertEqual(flag_values['quack'], 0)
    self.assertEqual(flag_values['x'], 3)
    self.assertEqual(flag_values['l'], 0x7fffffff00000000)
    self.assertEqual(flag_values['args'], ['v=1', 'vmodule=a=0,b=2'])
    self.assertEqual(flag_values['letters'], ['a', 'b', 'c'])
    self.assertEqual(flag_values['numbers'], [1, 2, 3])
    self.assertIsNone(flag_values['kwery'])
    self.assertIsNone(flag_values['sense'])
    self.assertIsNone(flag_values['cases'])
    self.assertIsNone(flag_values['funny'])
    self.assertIsNone(flag_values['blah'])

    # Verify string form of defaults
    self.assertEqual(FLAGS['repeat'].default_as_str, "'4'")
    self.assertEqual(FLAGS['name'].default_as_str, "'Bob'")
    self.assertEqual(FLAGS['debug'].default_as_str, "'false'")
    self.assertEqual(FLAGS['q'].default_as_str, "'true'")
    self.assertEqual(FLAGS['quack'].default_as_str, "'false'")
    self.assertEqual(FLAGS['noexec'].default_as_str, "'true'")
    self.assertEqual(FLAGS['x'].default_as_str, "'3'")
    self.assertEqual(FLAGS['l'].default_as_str, "'9223372032559808512'")
    self.assertEqual(FLAGS['args'].default_as_str, '\'v=1,"vmodule=a=0,b=2"\'')
    self.assertEqual(FLAGS['letters'].default_as_str, "'a,b,c'")
    self.assertEqual(FLAGS['numbers'].default_as_str, "'1,2,3'")

    # Verify that the iterator for flags yields all the keys
    keys = list(FLAGS)
    keys.sort()
    reg_flags = list(FLAGS._flags())
    reg_flags.sort()
    self.assertEqual(keys, reg_flags)

    # Parse flags
    # .. empty command line
    argv = ('./program',)
    argv = FLAGS(argv)
    self.assertLen(argv, 1, 'wrong number of arguments pulled')
    self.assertEqual(argv[0], './program', 'program name not preserved')

    # .. non-empty command line
    argv = ('./program', '--debug', '--name=Bob', '-q', '--x=8')
    argv = FLAGS(argv)
    self.assertLen(argv, 1, 'wrong number of arguments pulled')
    self.assertEqual(argv[0], './program', 'program name not preserved')
    self.assertEqual(FLAGS['debug'].present, 1)
    FLAGS['debug'].present = 0  # Reset
    self.assertEqual(FLAGS['name'].present, 1)
    FLAGS['name'].present = 0  # Reset
    self.assertEqual(FLAGS['q'].present, 1)
    FLAGS['q'].present = 0  # Reset
    self.assertEqual(FLAGS['x'].present, 1)
    FLAGS['x'].present = 0  # Reset

    # Flags list.
    self.assertLen(FLAGS, number_defined_flags + number_test_framework_flags)
    self.assertIn('name', FLAGS)
    self.assertIn('debug', FLAGS)
    self.assertIn('repeat', FLAGS)
    self.assertIn('r', FLAGS)
    self.assertIn('q', FLAGS)
    self.assertIn('quack', FLAGS)
    self.assertIn('x', FLAGS)
    self.assertIn('l', FLAGS)
    self.assertIn('args', FLAGS)
    self.assertIn('letters', FLAGS)
    self.assertIn('numbers', FLAGS)

    # __contains__
    self.assertIn('name', FLAGS)
    self.assertNotIn('name2', FLAGS)

    # try deleting a flag
    del FLAGS.r
    self.assertLen(FLAGS,
                   number_defined_flags - 1 + number_test_framework_flags)
    self.assertNotIn('r', FLAGS)

    # .. command line with extra stuff
    argv = ('./program', '--debug', '--name=Bob', 'extra')
    argv = FLAGS(argv)
    self.assertLen(argv, 2, 'wrong number of arguments pulled')
    self.assertEqual(argv[0], './program', 'program name not preserved')
    self.assertEqual(argv[1], 'extra', 'extra argument not preserved')
    self.assertEqual(FLAGS['debug'].present, 1)
    FLAGS['debug'].present = 0  # Reset
    self.assertEqual(FLAGS['name'].present, 1)
    FLAGS['name'].present = 0  # Reset

    # Test reset
    argv = ('./program', '--debug')
    argv = FLAGS(argv)
    self.assertLen(argv, 1, 'wrong number of arguments pulled')
    self.assertEqual(argv[0], './program', 'program name not preserved')
    self.assertEqual(FLAGS['debug'].present, 1)
    self.assertTrue(FLAGS['debug'].value)
    FLAGS.unparse_flags()
    self.assertEqual(FLAGS['debug'].present, 0)
    self.assertFalse(FLAGS['debug'].value)

    # Test that reset restores default value when default value is None.
    argv = ('./program', '--kwery=who')
    argv = FLAGS(argv)
    self.assertLen(argv, 1, 'wrong number of arguments pulled')
    self.assertEqual(argv[0], './program', 'program name not preserved')
    self.assertEqual(FLAGS['kwery'].present, 1)
    self.assertEqual(FLAGS['kwery'].value, 'who')
    FLAGS.unparse_flags()
    argv = ('./program', '--kwery=Why')
    argv = FLAGS(argv)
    self.assertLen(argv, 1, 'wrong number of arguments pulled')
    self.assertEqual(argv[0], './program', 'program name not preserved')
    self.assertEqual(FLAGS['kwery'].present, 1)
    self.assertEqual(FLAGS['kwery'].value, 'Why')
    FLAGS.unparse_flags()
    self.assertEqual(FLAGS['kwery'].present, 0)
    self.assertIsNone(FLAGS['kwery'].value)

    # Test case sensitive enum.
    argv = ('./program', '--sense=CASE')
    argv = FLAGS(argv)
    self.assertLen(argv, 1, 'wrong number of arguments pulled')
    self.assertEqual(argv[0], './program', 'program name not preserved')
    self.assertEqual(FLAGS['sense'].present, 1)
    self.assertEqual(FLAGS['sense'].value, 'CASE')
    FLAGS.unparse_flags()
    argv = ('./program', '--sense=Case')
    argv = FLAGS(argv)
    self.assertLen(argv, 1, 'wrong number of arguments pulled')
    self.assertEqual(argv[0], './program', 'program name not preserved')
    self.assertEqual(FLAGS['sense'].present, 1)
    self.assertEqual(FLAGS['sense'].value, 'Case')
    FLAGS.unparse_flags()

    # Test case insensitive enum.
    argv = ('./program', '--cases=upper')
    argv = FLAGS(argv)
    self.assertLen(argv, 1, 'wrong number of arguments pulled')
    self.assertEqual(argv[0], './program', 'program name not preserved')
    self.assertEqual(FLAGS['cases'].present, 1)
    self.assertEqual(FLAGS['cases'].value, 'UPPER')
    FLAGS.unparse_flags()

    # Test case sensitive enum with duplicates.
    argv = ('./program', '--funny=ha')
    argv = FLAGS(argv)
    self.assertLen(argv, 1, 'wrong number of arguments pulled')
    self.assertEqual(argv[0], './program', 'program name not preserved')
    self.assertEqual(FLAGS['funny'].present, 1)
    self.assertEqual(FLAGS['funny'].value, 'ha')