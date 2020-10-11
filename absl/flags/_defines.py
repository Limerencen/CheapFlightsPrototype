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
"""This modules contains flags DEFINE functions.

Do NOT import this module directly. Import the flags package and use the
aliases defined at the package level instead.
"""

import sys
import types

from absl.flags import _argument_parser
from absl.flags import _exceptions
from absl.flags import _flag
from absl.flags import _flagvalues
from absl.flags import _helpers
from absl.flags import _validators

# pylint: disable=unused-import
try:
  from typing import Text, List, Any
except ImportError:
  pass

try:
  import enum
except ImportError:
  pass
# pylint: enable=unused-import

_helpers.disclaim_module_ids.add(id(sys.modules[__name__]))


def _register_bounds_validator_if_needed(parser, name, flag_values):
  """Enforces lower and upper bounds for numeric flags.

  Args:
    parser: NumericParser (either FloatParser or IntegerParser), provides lower
      and upper bounds, and help text to display.
    name: str, name of the flag
    flag_values: FlagValues.
  """
  if parser.lower_bound is not None or parser.upper_bound is not None:

    def checker(value):
      if value is not None and parser.is_outside_bounds(value):
        message = '%s is not %s' % (value, parser.syntactic_help)
        raise _exceptions.ValidationError(message)
      return True

    _validators.register_validator(name, checker, flag_values=flag_values)


def DEFINE(  # pylint: disable=invalid-name
    parser,
    name,
    default,
    help,  # pylint: disable=redefined-builtin
    flag_values=_flagvalues.FLAGS,
    serializer=None,
    module_name=None,
    required=False,
    **args):
  """Registers a generic Flag object.

  NOTE: in the docstrings of all DEFINE* functions, "registers" is short
  for "creates a new flag and registers it".

 