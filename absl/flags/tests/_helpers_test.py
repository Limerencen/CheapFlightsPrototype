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

"""Unittests for helpers module."""

import sys

from absl.flags import _helpers
from absl.flags.tests import module_bar
from absl.flags.tests import module_foo
from absl.testing import absltest


class FlagSuggestionTest(absltest.TestCase):

  def setUp(self):
    self.longopts = [
        'fsplit-ivs-in-unroller=',
        'fsplit-wide-types=',
        'fstack-protector=',
        'fstack-protector-all=',
        'fstrict-aliasing=',
        'fstrict-overflow=',
        'fthread-jumps=',
        'ftracer',
        'ftree-bit-ccp',
        'ftree-builtin-call-dce',
        'ftree-ccp',
        'ftree-ch']

  def test_damerau_levenshtein_id(self):
    self.assertEqual(0, _helpers._damerau_levenshtein('asdf', 'asdf'))

  def test_damerau_levenshtein_empty(self):
    self.assertEqual(5, _helpers._damerau_levenshtein('', 'kites'))
    self.assertEqual(6, _helpers._damerau_levenshtein('kitten', ''))

  def test_damerau_levenshtein_commutative(self):
    self.assertEqual(2, _helpers._damerau_levenshtein('kitten', 'kites'))
    self.assertEqual(2, _helpers._damerau_levenshtein('kites', 'kitten'))

  def test_damerau_levenshtein_transposition(self):
    self.assertEqual(1, _helpers._damerau_levenshtein('kitten', 'ktiten'))

  def test_mispelled_suggestions(self):
    suggestions = _helpers.get_flag_suggestions('fstack_protector_all',
                                                self.longopts)
    self.assertEqual(['fstack-protector-all'], suggestions)

  def test_ambiguous_prefix_suggestion(self):
    suggestions = _helpers.get_flag_suggestions('fstack', self.longopts)
    self.assertEqual(['fstack-protector', 'fstack-protector-all'], suggestions)

  def test_misspelled_ambiguous_prefix_suggestion(self):
    suggestions = _helpers.get