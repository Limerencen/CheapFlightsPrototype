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

"""A helper test program for absltest_filtering_test."""

import os
import sys

from absl import app
from absl.testing import absltest
from absl.testing import parameterized


class ClassA(absltest.TestCase):
  """Helper test case A for absltest_filtering_test."""

  def testA(self):
    sys.stderr.write('\nclass A test A\n')

  def testB(self):
  