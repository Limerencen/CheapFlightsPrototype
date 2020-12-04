
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

    GNU style allows mixing of flag and non-flag arguments. See
    http://docs.python.org/library/getopt.html#getopt.gnu_getopt

    Args:
      gnu_getopt: bool, whether or not to use GNU style scanning.
    """
    self.__dict__['__use_gnu_getopt'] = gnu_getopt
    self.__dict__['__use_gnu_getopt_explicitly_set'] = True

  def is_gnu_getopt(self):
    return self.__dict__['__use_gnu_getopt']

  def _flags(self):
    return self.__dict__['__flags']

  def flags_by_module_dict(self):
    """Returns the dictionary of module_name -> list of defined flags.

    Returns:
      A dictionary.  Its keys are module names (strings).  Its values
      are lists of Flag objects.
    """
    return self.__dict__['__flags_by_module']

  def flags_by_module_id_dict(self):
    """Returns the dictionary of module_id -> list of defined flags.

    Returns:
      A dictionary.  Its keys are module IDs (ints).  Its values
      are lists of Flag objects.
    """
    return self.__dict__['__flags_by_module_id']

  def key_flags_by_module_dict(self):
    """Returns the dictionary of module_name -> list of key flags.

    Returns:
      A dictionary.  Its keys are module names (strings).  Its values
      are lists of Flag objects.
    """
    return self.__dict__['__key_flags_by_module']

  def register_flag_by_module(self, module_name, flag):
    """Records the module that defines a specific flag.

    We keep track of which flag is defined by which module so that we
    can later sort the flags by module.

    Args:
      module_name: str, the name of a Python module.
      flag: Flag, the Flag instance that is key to the module.
    """
    flags_by_module = self.flags_by_module_dict()
    flags_by_module.setdefault(module_name, []).append(flag)

  def register_flag_by_module_id(self, module_id, flag):
    """Records the module that defines a specific flag.

    Args:
      module_id: int, the ID of the Python module.
      flag: Flag, the Flag instance that is key to the module.
    """
    flags_by_module_id = self.flags_by_module_id_dict()
    flags_by_module_id.setdefault(module_id, []).append(flag)

  def register_key_flag_for_module(self, module_name, flag):
    """Specifies that a flag is a key flag for a module.

    Args:
      module_name: str, the name of a Python module.
      flag: Flag, the Flag instance that is key to the module.
    """
    key_flags_by_module = self.key_flags_by_module_dict()
    # The list of key flags for the module named module_name.
    key_flags = key_flags_by_module.setdefault(module_name, [])
    # Add flag, but avoid duplicates.
    if flag not in key_flags:
      key_flags.append(flag)

  def _flag_is_registered(self, flag_obj):
    """Checks whether a Flag object is registered under long name or short name.

    Args:
      flag_obj: Flag, the Flag instance to check for.

    Returns:
      bool, True iff flag_obj is registered under long name or short name.
    """
    flag_dict = self._flags()
    # Check whether flag_obj is registered under its long name.
    name = flag_obj.name
    if flag_dict.get(name, None) == flag_obj:
      return True
    # Check whether flag_obj is registered under its short name.
    short_name = flag_obj.short_name
    if (short_name is not None and flag_dict.get(short_name, None) == flag_obj):
      return True
    return False

  def _cleanup_unregistered_flag_from_module_dicts(self, flag_obj):
    """Cleans up unregistered flags from all module -> [flags] dictionaries.

    If flag_obj is registered under either its long name or short name, it
    won't be removed from the dictionaries.

    Args:
      flag_obj: Flag, the Flag instance to clean up for.
    """
    if self._flag_is_registered(flag_obj):
      return
    for flags_by_module_dict in (self.flags_by_module_dict(),
                                 self.flags_by_module_id_dict(),
                                 self.key_flags_by_module_dict()):
      for flags_in_module in flags_by_module_dict.values():
        # While (as opposed to if) takes care of multiple occurrences of a
        # flag in the list for the same module.
        while flag_obj in flags_in_module:
          flags_in_module.remove(flag_obj)

  def get_flags_for_module(self, module):
    """Returns the list of flags defined by a module.

    Args:
      module: module|str, the module to get flags from.

    Returns:
      [Flag], a new list of Flag instances.  Caller may update this list as
      desired: none of those changes will affect the internals of this
      FlagValue instance.
    """
    if not isinstance(module, str):
      module = module.__name__
    if module == '__main__':
      module = sys.argv[0]

    return list(self.flags_by_module_dict().get(module, []))

  def get_key_flags_for_module(self, module):
    """Returns the list of key flags for a module.

    Args:
      module: module|str, the module to get key flags from.

    Returns:
      [Flag], a new list of Flag instances.  Caller may update this list as
      desired: none of those changes will affect the internals of this
      FlagValue instance.
    """
    if not isinstance(module, str):
      module = module.__name__
    if module == '__main__':
      module = sys.argv[0]

    # Any flag is a key flag for the module that defined it.  NOTE:
    # key_flags is a fresh list: we can update it without affecting the
    # internals of this FlagValues object.
    key_flags = self.get_flags_for_module(module)

    # Take into account flags explicitly declared as key for a module.
    for flag in self.key_flags_by_module_dict().get(module, []):
      if flag not in key_flags:
        key_flags.append(flag)
    return key_flags

  def find_module_defining_flag(self, flagname, default=None):
    """Return the name of the module defining this flag, or default.

    Args:
      flagname: str, name of the flag to lookup.
      default: Value to return if flagname is not defined. Defaults to None.

    Returns:
      The name of the module which registered the flag with this name.
      If no such module exists (i.e. no flag with this name exists),
      we return default.
    """
    registered_flag = self._flags().get(flagname)
    if registered_flag is None:
      return default
    for module, flags in self.flags_by_module_dict().items():
      for flag in flags:
        # It must compare the flag with the one in _flags. This is because a
        # flag might be overridden only for its long name (or short name),
        # and only its short name (or long name) is considered registered.
        if (flag.name == registered_flag.name and
            flag.short_name == registered_flag.short_name):
          return module
    return default

  def find_module_id_defining_flag(self, flagname, default=None):
    """Return the ID of the module defining this flag, or default.

    Args:
      flagname: str, name of the flag to lookup.
      default: Value to return if flagname is not defined. Defaults to None.

    Returns:
      The ID of the module which registered the flag with this name.
      If no such module exists (i.e. no flag with this name exists),
      we return default.
    """
    registered_flag = self._flags().get(flagname)
    if registered_flag is None:
      return default