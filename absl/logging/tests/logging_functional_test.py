
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

"""Functional tests for absl.logging."""

import fnmatch
import os
import re
import shutil
import subprocess
import sys
import tempfile

from absl import logging
from absl.testing import _bazelize_command
from absl.testing import absltest
from absl.testing import parameterized


_PY_VLOG3_LOG_MESSAGE = """\
I1231 23:59:59.000000 12345 logging_functional_test_helper.py:62] This line is VLOG level 3
"""

_PY_VLOG2_LOG_MESSAGE = """\
I1231 23:59:59.000000 12345 logging_functional_test_helper.py:64] This line is VLOG level 2
I1231 23:59:59.000000 12345 logging_functional_test_helper.py:64] This line is log level 2