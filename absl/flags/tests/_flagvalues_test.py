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

"""Tests for flags.FlagValues class."""

import collections
import copy
import pickle
import types
from unittest import mock

from absl import logging
from absl.flags import _defines
from absl.flags import _exceptions
from absl.flags import _flagvalues
from absl.flags import _helpers
from absl.flags import _validators
from absl.flags.tests import module_foo
from absl.testing import absltest
from absl.testing import parameterized


class FlagValuesTest(absltest.TestCase):

  def test_bool_flags(self):
    for arg, expected in (('--nothing', True),
                          ('--nothing=true', True),
                          ('--nothing=false', False),
                          ('--nonothing', False)):
      fv = _flagvalues.FlagValues()
      _defines.DEFINE_boolean('nothing', None, '', flag_values=fv)
      fv(('./program', arg))
      self.assertIs(expected, fv.nothing)

    for arg in ('--nonothing=true', '--nonothing=false'):
      fv = _flagvalues.FlagValues()
      _defines.DEFINE_boolean('nothing', None, '', flag_values=fv)
      with self.assertRaises(ValueError):
        fv(('./program', arg))

  def test_boolean_flag_parser_gets_string_argument(self):
    for arg, expected in (('--nothing', 'true'),
                          ('--nothing=true', 'true'),
                          ('--nothing=false', 'false'),
                          ('--nonothing', 'false')):
      fv = _flagvalues.FlagValues()
      _defines.DEFINE_boolean('nothing', None, '', flag_values=fv)
      with mock.patch.object(fv['nothing'].parser, 'parse') as mock_parse:
        fv(('./program', arg))
        mock_parse.assert_called_once_with(expected)

  def test_unregistered_flags_are_cleaned_up(self):
    fv = _flagvalues.FlagValues()
    module, module_name = _helpers.get_calling_module_object_and_name()

    # Define first flag.
    _defines.DEFINE_integer('cores', 4, '', flag_values=fv, short_name='c')
    old_cores_flag = fv['cores']
    fv.register_key_flag_for_module(module_name, old_cores_flag)
    self.assertEqual(fv.flags_by_module_dict(),
                     {module_name: [old_cores_flag]})
    self.assertEqual(fv.flags_by_module_id_dict(),
                     {id(module): [old_cores_flag]})
    self.assertEqual(fv.key_flags_by_module_dict(),
                     {module_name: [old_cores_flag]})

    # Redefine the same flag.
    _defines.DEFINE_integer(
        'cores', 4, '', flag_values=fv, short_name='c', allow_override=True)
    new_cores_flag = fv['cores']
    self.assertNotEqual(old_cores_flag, new_cores_flag)
    self.assertEqual(fv.flags_by_module_dict(),
                     {module_name: [new_cores_flag]})
    self.assertEqual(fv.flags_by_module_id_dict(),
                     {id(module): [new_cores_flag]})
    # old_cores_flag is removed from key flags, and the new_cores_flag is
    # not automatically added because it must be registered explicitly.
    self.assertEqual(fv.key_flags_by_module_dict(), {module_name: []})

    # Define a new flag but with the same short_name.
    _defines.DEFINE_integer(
        'changelist',
        0,
        '',
        flag_values=fv,
        short_name='c',
        allow_override=True)
    old_changelist_flag = fv['changelist']
    fv.register_key_flag_for_module(module_name, old_changelist_flag)
    # The short named flag -c is overridden to be the old_changelist_flag.
    self.assertEqual(fv['c'], old_changelist_flag)
    self.assertNotEqual(fv['c'], new_cores_flag)
    self.assertEqual(fv.flags_by_module_dict(),
                     {module_name: [new_cores_flag, old_changelist_flag]})
    self.assertEqual(fv.flags_by_module_id_dict(),
                     {id(module): [new_cores_flag, old_changelist_flag]})
    self.assertEqual(fv.key_flags_by_module_dict(),
                     {module_name: [old_changelist_flag]})

    # Define a flag only with the same long name.
    _defines.DEFINE_integer(
        'changelist',
        0,
        '',
        flag_values=fv,
        short_name='l',
        allow_override=True)
    new_changelist_flag = fv['changelist']
    self.assertNotEqual(old_changelist_flag, new_changelist_flag)
    self.assertEqual(fv.flags_by_module_dict(),
                     {module_name: [new_cores_flag,
                                    old_changelist_flag,
                                    new_changelist_flag]})
    self.assertEqual(fv.flags_by_module_id_dict(),
                     {id(module): [new_cores_flag,
                                   old_changelist_flag,
                                   new_changelist_flag]})
    self.assertEqual(fv.key_flags_by_module_dict(),
                     {module_name: [old_changelist_flag]})

    # Delete the new changelist's long name, it should still be registered
    # because of its short name.
    del fv.changelist
    self.assertNotIn('changelist', fv)
    self.assertEqual(fv.flags_by_module_dict(