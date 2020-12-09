
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

"""Internal helper functions for Abseil Python flags library."""

import collections
import os
import re
import struct
import sys
import textwrap
try:
  import fcntl
except ImportError:
  fcntl = None
try:
  # Importing termios will fail on non-unix platforms.
  import termios
except ImportError:
  termios = None


_DEFAULT_HELP_WIDTH = 80  # Default width of help output.
# Minimal "sane" width of help output. We assume that any value below 40 is
# unreasonable.
_MIN_HELP_WIDTH = 40

# Define the allowed error rate in an input string to get suggestions.
#
# We lean towards a high threshold because we tend to be matching a phrase,
# and the simple algorithm used here is geared towards correcting word
# spellings.
#
# For manual testing, consider "<command> --list" which produced a large number
# of spurious suggestions when we used "least_errors > 0.5" instead of
# "least_erros >= 0.5".
_SUGGESTION_ERROR_RATE_THRESHOLD = 0.50

# Characters that cannot appear or are highly discouraged in an XML 1.0
# document. (See http://www.w3.org/TR/REC-xml/#charsets or
# https://en.wikipedia.org/wiki/Valid_characters_in_XML#XML_1.0)
_ILLEGAL_XML_CHARS_REGEX = re.compile(
    u'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f\ud800-\udfff\ufffe\uffff]')

# This is a set of module ids for the modules that disclaim key flags.
# This module is explicitly added to this set so that we never consider it to
# define key flag.
disclaim_module_ids = set([id(sys.modules[__name__])])


# Define special flags here so that help may be generated for them.
# NOTE: Please do NOT use SPECIAL_FLAGS from outside flags module.
# Initialized inside flagvalues.py.
SPECIAL_FLAGS = None


# This points to the flags module, initialized in flags/__init__.py.
# This should only be used in adopt_module_key_flags to take SPECIAL_FLAGS into
# account.
FLAGS_MODULE = None


class _ModuleObjectAndName(
    collections.namedtuple('_ModuleObjectAndName', 'module module_name')):
  """Module object and name.

  Fields:
  - module: object, module object.
  - module_name: str, module name.
  """


def get_module_object_and_name(globals_dict):
  """Returns the module that defines a global environment, and its name.

  Args:
    globals_dict: A dictionary that should correspond to an environment
      providing the values of the globals.

  Returns:
    _ModuleObjectAndName - pair of module object & module name.
    Returns (None, None) if the module could not be identified.