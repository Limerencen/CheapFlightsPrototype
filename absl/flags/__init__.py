
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
"""This package is used to define and parse command line flags.

This package defines a *distributed* flag-definition policy: rather than
an application having to define all flags in or near main(), each Python
module defines flags that are useful to it.  When one Python module
imports another, it gains access to the other's flags.  (This is
implemented by having all modules share a common, global registry object
containing all the flag information.)

Flags are defined through the use of one of the DEFINE_xxx functions.
The specific function used determines how the flag is parsed, checked,
and optionally type-converted, when it's seen on the command line.
"""

import getopt
import os
import re
import sys
import types
import warnings

from absl.flags import _argument_parser
from absl.flags import _defines
from absl.flags import _exceptions
from absl.flags import _flag
from absl.flags import _flagvalues
from absl.flags import _helpers
from absl.flags import _validators

__all__ = (
    'DEFINE',
    'DEFINE_flag',
    'DEFINE_string',
    'DEFINE_boolean',
    'DEFINE_bool',
    'DEFINE_float',
    'DEFINE_integer',
    'DEFINE_enum',
    'DEFINE_enum_class',
    'DEFINE_list',
    'DEFINE_spaceseplist',
    'DEFINE_multi',
    'DEFINE_multi_string',
    'DEFINE_multi_integer',
    'DEFINE_multi_float',
    'DEFINE_multi_enum',
    'DEFINE_multi_enum_class',
    'DEFINE_alias',
    # Flag validators.
    'register_validator',
    'validator',
    'register_multi_flags_validator',
    'multi_flags_validator',
    'mark_flag_as_required',
    'mark_flags_as_required',
    'mark_flags_as_mutual_exclusive',
    'mark_bool_flags_as_mutual_exclusive',
    # Flag modifiers.
    'set_default',
    # Key flag related functions.
    'declare_key_flag',
    'adopt_module_key_flags',
    'disclaim_key_flags',
    # Module exceptions.
    'Error',
    'CantOpenFlagFileError',
    'DuplicateFlagError',
    'IllegalFlagValueError',
    'UnrecognizedFlagError',
    'UnparsedFlagAccessError',
    'ValidationError',
    'FlagNameConflictsWithMethodError',
    # Public classes.
    'Flag',
    'BooleanFlag',
    'EnumFlag',
    'EnumClassFlag',
    'MultiFlag',
    'MultiEnumClassFlag',
    'FlagHolder',
    'FlagValues',
    'ArgumentParser',
    'BooleanParser',
    'EnumParser',
    'EnumClassParser',
    'ArgumentSerializer',
    'FloatParser',
    'IntegerParser',
    'BaseListParser',
    'ListParser',
    'ListSerializer',
    'EnumClassListSerializer',
    'CsvListSerializer',
    'WhitespaceSeparatedListParser',
    'EnumClassSerializer',
    # Helper functions.
    'get_help_width',
    'text_wrap',
    'flag_dict_to_args',
    'doc_to_help',
    # The global FlagValues instance.
    'FLAGS',
)

# Initialize the FLAGS_MODULE as early as possible.
# It's only used by adopt_module_key_flags to take SPECIAL_FLAGS into account.
_helpers.FLAGS_MODULE = sys.modules[__name__]

# Add current module to disclaimed module ids.
_helpers.disclaim_module_ids.add(id(sys.modules[__name__]))

# DEFINE functions. They are explained in more details in the module doc string.
# pylint: disable=invalid-name
DEFINE = _defines.DEFINE
DEFINE_flag = _defines.DEFINE_flag
DEFINE_string = _defines.DEFINE_string
DEFINE_boolean = _defines.DEFINE_boolean
DEFINE_bool = DEFINE_boolean  # Match C++ API.
DEFINE_float = _defines.DEFINE_float
DEFINE_integer = _defines.DEFINE_integer
DEFINE_enum = _defines.DEFINE_enum
DEFINE_enum_class = _defines.DEFINE_enum_class
DEFINE_list = _defines.DEFINE_list
DEFINE_spaceseplist = _defines.DEFINE_spaceseplist
DEFINE_multi = _defines.DEFINE_multi
DEFINE_multi_string = _defines.DEFINE_multi_string
DEFINE_multi_integer = _defines.DEFINE_multi_integer