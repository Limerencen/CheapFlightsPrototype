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

"""Internal helper for running tests on Windows Bazel."""

import os

from absl import flags

FLAGS = flags.FLAGS


def get_executable_path(py_binary_name):
  """Returns the executable path of a py_binary.

  This returns the executable path of a py_binary that is in another Bazel
  target's data dependencies.

  On Linux/macOS, the path and __file__ has the same root directory.
  On Windows, bazel builds an .exe file and we need to use the MANIFEST file
  the location the actual binary.

  Args:
    py_binary_name: string, the name of a py_binary tha