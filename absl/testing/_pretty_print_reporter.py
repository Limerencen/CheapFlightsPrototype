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

"""TestResult implementing default output for test execution status."""

import unittest


class TextTestResult(unittest.TextTestResult):
  """TestResult class that provides the default text result formatting."""

  def __init__(self, stream, descriptions, verbosity):
    # Disable the verbose per-test output from the superclass, since it would
    # conflict with our customized output.
    super(TextTestResult, self).__init__(stream, descriptions, 0)
    self._per_test_output = verbosity > 0

  def _print_status(self, tag, test):
    if self._per_test_output:
      test_id = test.id()
      if test_id.startswith('__main__.'):
        test_id = te