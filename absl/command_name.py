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

"""A tiny stand alone library to change the kernel process name on Linux."""

import os
import sys

# This library must be kept small and stand alone.  It is used by small things
# that require no extension modules.


def make_process_name_useful():
  """Sets the process name to something better than 'python' if possible."""
  set_kernel_process_name(os.path.basename(sys.argv[0]))


def set_kernel_process_name(name):
  """Changes the Kernel's /proc/self/status process name on Linux.

  The kernel name is NOT what will be shown by the ps or top command.
  It is a 15 character string stored in the kernel's process table that
  is 