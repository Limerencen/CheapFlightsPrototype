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

"""Test the use of flags when from __future__ import unicode_literals is on."""

from absl import flags
from absl.testing import absltest


flags.DEFINE_string('seen_in_crittenden', 'alleged mountain lion',
                    'This tests if unicode input to these functions works.')


class FlagsUnicodeLiteralsTest(absltes