
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

"""Contains Flag class - information about single command-line flag.

Do NOT import this module directly. Import the flags package and use the
aliases defined at the package level instead.
"""

from collections import abc
import copy
import functools

from absl.flags import _argument_parser
from absl.flags import _exceptions
from absl.flags import _helpers


@functools.total_ordering
class Flag(object):
  """Information about a command-line flag.

  Attributes:
    name: the name for this flag
    default: the default value for this flag
    default_unparsed: the unparsed default value for this flag.
    default_as_str: default value as repr'd string, e.g., "'true'"
      (or None)
    value: the most recent parsed value of this flag set by :meth:`parse`
    help: a help string or None if no help is available
    short_name: the single letter alias for this flag (or None)
    boolean: if 'true', this flag does not accept arguments
    present: true if this flag was parsed from command line flags
    parser: an :class:`~absl.flags.ArgumentParser` object
    serializer: an ArgumentSerializer object
    allow_override: the flag may be redefined without raising an error,
      and newly defined flag overrides the old one.
    allow_override_cpp: use the flag from C++ if available the flag
      definition is replaced by the C++ flag after init
    allow_hide_cpp: use the Python flag despite having a C++ flag with
      the same name (ignore the C++ flag)
    using_default_value: the flag value has not been set by user
    allow_overwrite: the flag may be parsed more than once without
      raising an error, the last set value will be used
    allow_using_method_names: whether this flag can be defined even if
      it has a name that conflicts with a FlagValues method.
    validators: list of the flag validators.

  The only public method of a ``Flag`` object is :meth:`parse`, but it is
  typically only called by a :class:`~absl.flags.FlagValues` object.  The
  :meth:`parse` method is a thin wrapper around the
  :meth:`ArgumentParser.parse()<absl.flags.ArgumentParser.parse>` method.  The
  parsed value is saved in ``.value``, and the ``.present`` attribute is
  updated.  If this flag was already present, an Error is raised.

  :meth:`parse` is also called during ``__init__`` to parse the default value
  and initialize the ``.value`` attribute.  This enables other python modules to
  safely use flags even if the ``__main__`` module neglects to parse the
  command line arguments.  The ``.present`` attribute is cleared after
  ``__init__`` parsing.  If the default value is set to ``None``, then the
  ``__init__`` parsing step is skipped and the ``.value`` attribute is
  initialized to None.

  Note: The default value is also presented to the user in the help
  string, so it is important that it be a legal value for this flag.
  """

  def __init__(self, parser, serializer, name, default, help_string,
               short_name=None, boolean=False, allow_override=False,
               allow_override_cpp=False, allow_hide_cpp=False,
               allow_overwrite=True, allow_using_method_names=False):
    self.name = name

    if not help_string:
      help_string = '(no help available)'

    self.help = help_string
    self.short_name = short_name
    self.boolean = boolean
    self.present = 0
    self.parser = parser
    self.serializer = serializer
    self.allow_override = allow_override
    self.allow_override_cpp = allow_override_cpp
    self.allow_hide_cpp = allow_hide_cpp
    self.allow_overwrite = allow_overwrite
    self.allow_using_method_names = allow_using_method_names

    self.using_default_value = True
    self._value = None
    self.validators = []
    if self.allow_hide_cpp and self.allow_override_cpp:
      raise _exceptions.Error(
          "Can't have both allow_hide_cpp (means use Python flag) and "
          'allow_override_cpp (means use C++ flag after InitGoogle)')

    self._set_default(default)

  @property
  def value(self):
    return self._value

  @value.setter
  def value(self, value):
    self._value = value

  def __hash__(self):
    return hash(id(self))

  def __eq__(self, other):
    return self is other

  def __lt__(self, other):
    if isinstance(other, Flag):
      return id(self) < id(other)
    return NotImplemented

  def __bool__(self):
    raise TypeError('A Flag instance would always be True. '
                    'Did you mean to test the `.value` attribute?')

  def __getstate__(self):
    raise TypeError("can't pickle Flag objects")
