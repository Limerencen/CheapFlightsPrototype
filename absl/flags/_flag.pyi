
# Copyright 2020 The Abseil Authors.
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

"""Contains type annotations for Flag class."""

import copy
import functools

from absl.flags import _argument_parser
import enum

from typing import Callable, Text, TypeVar, Generic, Iterable, Type, List, Optional, Any, Union, Sequence

_T = TypeVar('_T')
_ET = TypeVar('_ET', bound=enum.Enum)


class Flag(Generic[_T]):

  name = ... # type: Text
  default = ... # type: Any
  default_unparsed = ... # type: Any
  default_as_str = ... # type: Optional[Text]
  help = ... # type: Text
  short_name = ... # type: Text
  boolean = ... # type: bool
  present = ... # type: bool
  parser = ... # type: _argument_parser.ArgumentParser[_T]
  serializer = ... # type: _argument_parser.ArgumentSerializer[_T]
  allow_override = ... # type: bool
  allow_override_cpp = ... # type: bool
  allow_hide_cpp = ... # type: bool
  using_default_value = ... # type: bool
  allow_overwrite = ... # type: bool
  allow_using_method_names = ... # type: bool
  validators = ... # type: List[Callable[[Any], bool]]
