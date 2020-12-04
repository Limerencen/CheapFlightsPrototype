
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
"""Defines the FlagValues class - registry of 'Flag' objects.

Do NOT import this module directly. Import the flags package and use the
aliases defined at the package level instead.
"""

import copy
import itertools
import logging
import os
import sys
from typing import Generic, TypeVar
from xml.dom import minidom

from absl.flags import _exceptions
from absl.flags import _flag
from absl.flags import _helpers
from absl.flags import _validators_classes

# Add flagvalues module to disclaimed module ids.
_helpers.disclaim_module_ids.add(id(sys.modules[__name__]))

_T = TypeVar('_T')


class FlagValues:
  """Registry of :class:`~absl.flags.Flag` objects.

  A :class:`FlagValues` can then scan command line arguments, passing flag
  arguments through to the 'Flag' objects that it owns.  It also
  provides easy access to the flag values.  Typically only one
  :class:`FlagValues` object is needed by an application:
  :const:`FLAGS`.

  This class is heavily overloaded:

  :class:`Flag` objects are registered via ``__setitem__``::

       FLAGS['longname'] = x   # register a new flag

  The ``.value`` attribute of the registered :class:`~absl.flags.Flag` objects
  can be accessed as attributes of this :class:`FlagValues` object, through
  ``__getattr__``.  Both the long and short name of the original
  :class:`~absl.flags.Flag` objects can be used to access its value::

       FLAGS.longname  # parsed flag value
       FLAGS.x  # parsed flag value (short name)

  Command line arguments are scanned and passed to the registered
  :class:`~absl.flags.Flag` objects through the ``__call__`` method.  Unparsed
  arguments, including ``argv[0]`` (e.g. the program name) are returned::

       argv = FLAGS(sys.argv)  # scan command line arguments

  The original registered :class:`~absl.flags.Flag` objects can be retrieved
  through the use of the dictionary-like operator, ``__getitem__``::

       x = FLAGS['longname']   # access the registered Flag object

  The ``str()`` operator of a :class:`absl.flags.FlagValues` object provides
  help for all of the registered :class:`~absl.flags.Flag` objects.
  """

  # A note on collections.abc.Mapping:
  # FlagValues defines __getitem__, __iter__, and __len__. It makes perfect
  # sense to let it be a collections.abc.Mapping class. However, we are not
  # able to do so. The mixin methods, e.g. keys, values, are not uncommon flag
  # names. Those flag values would not be accessible via the FLAGS.xxx form.

  def __init__(self):
    # Since everything in this class is so heavily overloaded, the only
    # way of defining and using fields is to access __dict__ directly.

    # Dictionary: flag name (string) -> Flag object.
    self.__dict__['__flags'] = {}

    # Set: name of hidden flag (string).
    # Holds flags that should not be directly accessible from Python.
    self.__dict__['__hiddenflags'] = set()

    # Dictionary: module name (string) -> list of Flag objects that are defined
    # by that module.
    self.__dict__['__flags_by_module'] = {}
    # Dictionary: module id (int) -> list of Flag objects that are defined by
    # that module.
    self.__dict__['__flags_by_module_id'] = {}
    # Dictionary: module name (string) -> list of Flag objects that are
    # key for that module.
    self.__dict__['__key_flags_by_module'] = {}

    # Bool: True if flags were parsed.
    self.__dict__['__flags_parsed'] = False

    # Bool: True if unparse_flags() was called.
    self.__dict__['__unparse_flags_called'] = False

    # None or Method(name, value) to call from __setattr__ for an unknown flag.
    self.__dict__['__set_unknown'] = None

    # A set of banned flag names. This is to prevent users from accidentally
    # defining a flag that has the same name as a method on this class.
    # Users can still allow defining the flag by passing
    # allow_using_method_names=True in DEFINE_xxx functions.
    self.__dict__['__banned_flag_names'] = frozenset(dir(FlagValues))

    # Bool: Whether to use GNU style scanning.
    self.__dict__['__use_gnu_getopt'] = True

    # Bool: Whether use_gnu_getopt has been explicitly set by the user.
    self.__dict__['__use_gnu_getopt_explicitly_set'] = False

    # Function: Takes a flag name as parameter, returns a tuple
    # (is_retired, type_is_bool).
    self.__dict__['__is_retired_flag_func'] = None

  def set_gnu_getopt(self, gnu_getopt=True):
    """Sets whether or not to use GNU style scanning.
