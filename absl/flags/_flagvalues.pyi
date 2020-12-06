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

"""Defines type annotations for _flagvalues."""


from absl.flags import _flag

from typing import Any, Dict, Generic, Iterable, Iterator, List, Optional, Sequence, Text, Type, TypeVar


class FlagValues:

  def __getitem__(self, name: Text) -> _flag.Flag:  ...

  def __setitem__(self, name: Text, flag: _flag.Flag) -> None:  ...

  def __getattr__(self, name: Text) -> Any:  ...

  def __setattr__(self, name: Text, value: Any) -> Any:  ...

  def __call__(
      self,
      argv: Sequence[Text],
      known_only: bool = ...,
  ) -> List[Text]: ...

  def __contains__(self, name: Text) -> bool: ...

  def __copy__(self) -> Any: ...

  def __deepcopy__(self, memo) -> Any: ...

  def __delattr__(self, flag_name: Text) -> None: ...

  def __dir__(self) -> List[Text]: ...