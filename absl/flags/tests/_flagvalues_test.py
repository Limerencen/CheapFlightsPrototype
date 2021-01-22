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

  def test_bo