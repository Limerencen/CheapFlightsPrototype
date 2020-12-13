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

"""Module to enforce different constraints on flags.

Flags validators can be registered using following functions / decorators::

    flags.register_validator
    @flags.validator
    flags.register_multi_flags_validator
    @flags.multi_flags_validator

Three convenience functions are also provided for common flag constraints::

    flags.mark_flag_as_required
    flags.mark_flags_as_required
    flags.mark_flags_as_mutual_exclusive
    flags.mark_bool_flags_as_mutual_exclusive

See their docstring in this module for a usage manual.

Do NOT import this module directly. Import the flags package and use the
aliases defined at the package level instead.
"""

import warnings

from absl.flags import _exceptions
from absl.flags import _flagvalues
from absl.flags import _validators_classes


def register_validator(flag_name,
                       checker,
                       message='Flag validation failed',
                       flag_values=_flagvalues.FLAGS):
  """Adds a constraint, which will be enforced during program execution.

  The constraint is validated when flags are initially parsed, and after each
  change of the corresponding flag's value.

  Args:
    flag_name: str | FlagHolder, name or holder of the flag to be checked.
        Positional-only parameter.
    checker: callable, a function to validate the flag.

        * input - A single positional argument: The value of the corresponding
          flag (string, boolean, etc.  This value will be passed to