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

    # Delete the new changelist's short name, it should be removed.
    del fv.l
    self.assertNotIn('l', fv)
    self.assertEqual(fv.flags_by_module_dict(),
                     {module_name: [new_cores_flag,
                                    old_changelist_flag]})
    self.assertEqual(fv.flags_by_module_id_dict(),
                     {id(module): [new_cores_flag,
                                   old_changelist_flag]})
    self.assertEqual(fv.key_flags_by_module_dict(),
                     {module_name: [old_changelist_flag]})

  def _test_find_module_or_id_defining_flag(self, test_id):
    """Tests for find_module_defining_flag and find_module_id_defining_flag.

    Args:
      test_id: True to test find_module_id_defining_flag, False to test
          find_module_defining_flag.
    """
    fv = _flagvalues.FlagValues()
    current_module, current_module_name = (
        _helpers.get_calling_module_object_and_name())
    alt_module_name = _flagvalues.__name__

    if test_id:
      current_module_or_id = id(current_module)
      alt_module_or_id = id(_flagvalues)
      testing_fn = fv.find_module_id_defining_flag
    else:
      current_module_or_id = current_module_name
      alt_module_or_id = alt_module_name
      testing_fn = fv.find_module_defining_flag

    # Define first flag.
    _defines.DEFINE_integer('cores', 4, '', flag_values=fv, short_name='c')
    module_or_id_cores = testing_fn('cores')
    self.assertEqual(module_or_id_cores, current_module_or_id)
    module_or_id_c = testing_fn('c')
    self.assertEqual(module_or_id_c, current_module_or_id)

    # Redefine the same flag in another module.
    _defines.DEFINE_integer(
        'cores',
        4,
        '',
        flag_values=fv,
        module_name=alt_module_name,
        short_name='c',
        allow_override=True)
    module_or_id_cores = testing_fn('cores')
    self.assertEqual(module_or_id_cores, alt_module_or_id)
    module_or_id_c = testing_fn('c')
    self.assertEqual(module_or_id_c, alt_module_or_id)

    # Define a new flag but with the same short_name.
    _defines.DEFINE_integer(
        'changelist',
        0,
        '',
        flag_values=fv,
        short_name='c',
        allow_override=True)
    module_or_id_cores = testing_fn('cores')
    self.assertEqual(module_or_id_cores, alt_module_or_id)
    module_or_id_changelist = testing_fn('changelist')
    self.assertEqual(module_or_id_changelist, current_module_or_id)
    module_or_id_c = testing_fn('c')
    self.assertEqual(module_or_id_c, current_module_or_id)

    # Define a flag in another module only with the same long name.
    _defines.DEFINE_integer(
        'changelist',
        0,
        '',
        flag_values=fv,
        module_name=alt_module_name,
        short_name='l',
        allow_override=True)
    module_or_id_cores = testing_fn('cores')
    self.assertEqual(module_or_id_cores, alt_module_or_id)
    module_or_id_changelist = testing_fn('changelist')
    self.assertEqual(module_or_id_changelist, alt_module_or_id)
    module_or_id_c = testing_fn('c')
    self.assertEqual(module_or_id_c, current_module_or_id)
    module_or_id_l = testing_fn('l')
    self.assertEqual(module_or_id_l, alt_module_or_id)

    # Delete the changelist flag, its short name should still be registered.
    del fv.changelist
    module_or_id_changelist = testing_fn('changelist')
    self.assertIsNone(module_or_id_changelist)
    module_or_id_c = testing_fn('c')
    self.assertEqual(module_or_id_c, current_module_or_id)
    module_or_id_l = testing_fn('l')
    self.assertEqual(module_or_id_l, alt_module_or_id)

  def test_find_module_defining_flag(self):
    self._test_find_module_or_id_defining_flag(test_id=False)

  def test_find_module_id_defining_flag(self):
    self._test_find_module_or_id_defining_flag(test_id=True)

  def test_set_default(self):
    fv = _flagvalues.FlagValues()
    fv.mark_as_parsed()
    with self.assertRaises(_exceptions.UnrecognizedFlagError):
      fv.set_default('changelist', 1)
    _defines.DEFINE_integer('changelist', 0, 'help', flag_values=fv)
    self.assertEqual(0, fv.changelist)
    fv.set_default('changelist', 2)
    self.assertEqual(2, fv.chan