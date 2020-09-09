
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

"""Generic entry point for Abseil Python applications.

To use this module, define a ``main`` function with a single ``argv`` argument
and call ``app.run(main)``. For example::

    def main(argv):
      if len(argv) > 1:
        raise app.UsageError('Too many command-line arguments.')

    if __name__ == '__main__':
      app.run(main)
"""

import collections
import errno
import os
import pdb
import sys
import textwrap
import traceback

from absl import command_name