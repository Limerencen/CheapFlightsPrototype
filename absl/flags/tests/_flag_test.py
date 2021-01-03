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

"""Additional tests for Flag classes.

Most of the Flag classes are covered in the flags_test.py.
"""

import copy
import enum
import pickle

from absl.flags import _argument_parser
from absl.flags import _exceptions
from absl.flags import _flag
from absl.testing import absltest
from absl.testing import parameterized


class FlagTest(absltest.TestCase):

  def setUp(self):
    super().setUp()
    self.flag = _flag.Flag(
        _argument_parser.ArgumentParser(),
        _argument_parser.ArgumentSerializer(),
        'fruit', 'apple', 'help')

  def test_default_unparsed(self):
    flag = _flag.Flag(
        _argument_parser.ArgumentParser(),
        _argument_parser.ArgumentSerializer(),
        'fruit', 'apple', 'help')
    self.assertEqual('apple', flag.default_unparsed)

    flag = _flag.Flag(
       