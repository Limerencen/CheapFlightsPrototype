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
"""Tests for flagsaver."""

from absl import flags
from absl.testing import absltest
from absl.testing import flagsaver
from absl.testing import parameterized

flags.DEFINE_string('flagsaver_test_flag0', 'unchanged0', 'flag to test with')
flags.DEFINE_string('flagsaver_test_flag1', 'unchanged1', 'flag to test with')

flags.DEFINE_string('flagsaver_test_validated_flag', None, 'flag to test with