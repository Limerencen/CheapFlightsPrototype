
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
