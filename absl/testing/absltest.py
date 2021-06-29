
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

"""Base functionality for Abseil Python tests.

This module contains base classes and high-level functions for Abseil-style
tests.
"""

from collections import abc
import contextlib
import difflib
import enum
import errno
import getpass
import inspect
import io
import itertools
import json
import os
import random
import re
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock  # pylint: disable=unused-import Allow absltest.mock.
from urllib import parse

try:
  # The faulthandler module isn't always available, and pytype doesn't
  # understand that we're catching ImportError, so suppress the error.
  # pytype: disable=import-error
  import faulthandler
  # pytype: enable=import-error
except ImportError:
  # We use faulthandler if it is available.
  faulthandler = None

from absl import app
from absl import flags
from absl import logging
from absl.testing import _pretty_print_reporter
from absl.testing import xml_reporter

# Make typing an optional import to avoid it being a required dependency
# in Python 2. Type checkers will still understand the imports.
try:
  # pylint: disable=unused-import
  import typing
  from typing import Any, AnyStr, BinaryIO, Callable, ContextManager, IO, Iterator, List, Mapping, MutableMapping, MutableSequence, Optional, Sequence, Text, TextIO, Tuple, Type, Union
  # pylint: enable=unused-import
except ImportError:
  pass
else:
  # Use an if-type-checking block to prevent leakage of type-checking only
  # symbols. We don't want people relying on these at runtime.
  if typing.TYPE_CHECKING:
    # Unbounded TypeVar for general usage
    _T = typing.TypeVar('_T')

    import unittest.case
    _OutcomeType = unittest.case._Outcome  # pytype: disable=module-attr



# Re-export a bunch of unittest functions we support so that people don't
# have to import unittest to get them
# pylint: disable=invalid-name
skip = unittest.skip
skipIf = unittest.skipIf
skipUnless = unittest.skipUnless
SkipTest = unittest.SkipTest
expectedFailure = unittest.expectedFailure
# pylint: enable=invalid-name

# End unittest re-exports

FLAGS = flags.FLAGS

_TEXT_OR_BINARY_TYPES = (str, bytes)

# Suppress surplus entries in AssertionError stack traces.
__unittest = True  # pylint: disable=invalid-name


def expectedFailureIf(condition, reason):  # pylint: disable=invalid-name
  """Expects the test to fail if the run condition is True.

  Example usage::

      @expectedFailureIf(sys.version.major == 2, "Not yet working in py2")
      def test_foo(self):
        ...

  Args:
    condition: bool, whether to expect failure or not.
    reason: Text, the reason to expect failure.
  Returns:
    Decorator function
  """
  del reason  # Unused
  if condition:
    return unittest.expectedFailure
  else:
    return lambda f: f


class TempFileCleanup(enum.Enum):
  # Always cleanup temp files when the test completes.
  ALWAYS = 'always'