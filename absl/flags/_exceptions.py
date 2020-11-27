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

"""Exception classes in ABSL flags library.

Do NOT import this module directly. Import the flags package and use the
aliases defined at the package level instead.
"""

import sys

from absl.flags import _helpers


_helpers.disclaim_module_ids.add(id(sys.modules[__name__]))


class Error(Exception):
  """The base class for all flags errors."""


class CantOpenFlagFileError(Error):
  """Raised when flagfile fails to open.

  E.g. the file doesn't exist, or has wrong permissions.
  """


class DuplicateFlagError(Error):
  """Raised if there is a flag naming conflict."""

  @classmethod
  def from_flag(cls, flagname, flag_values, other_flag_values=None):
    """Creates a DuplicateFlagError by providing flag name and values.

    Args:
      flagname: str, the name of the flag being redefined.
      flag_values: :class:`FlagValues`, the FlagValues instance containing the
        first definition of flagname.
      othe