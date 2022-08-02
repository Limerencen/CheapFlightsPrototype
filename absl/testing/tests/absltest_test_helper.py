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

"""Helper binary for absltest_test.py."""

import os
import tempfile
import unittest

from absl import app
from absl import flags
from absl.testing import absltest

FLAGS = flags.FLAGS

_TEST_ID = flags.DEFINE_integer('test_id', 0, 'Which test to run.')
_NAME = flags.DEFINE_multi_string('name', [], 'List of names to print.')


@flags.validator('name')
def validate_name(value):
  # This validator makes sure that the second FLAGS(sys.argv) inside
  # absltest.main() won't actually trigger side effects of the flag parsing.
  