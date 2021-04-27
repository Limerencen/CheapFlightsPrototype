
# Copyright 2018 The Abseil Authors.
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

"""Tests for absl.flags.argparse_flags."""

import io
import os
import subprocess
import sys
import tempfile
from unittest import mock

from absl import flags
from absl import logging
from absl.flags import argparse_flags
from absl.testing import _bazelize_command
from absl.testing import absltest
from absl.testing import parameterized


class ArgparseFlagsTest(parameterized.TestCase):

  def setUp(self):
    super().setUp()
    self._absl_flags = flags.FlagValues()
    flags.DEFINE_bool(
        'absl_bool', None, 'help for --absl_bool.',
        short_name='b', flag_values=self._absl_flags)
    # Add a boolean flag that starts with "no", to verify it can correctly
    # handle the "no" prefixes in boolean flags.
    flags.DEFINE_bool(