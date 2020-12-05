
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
    for module_id, flags in self.flags_by_module_id_dict().items():
      for flag in flags:
        # It must compare the flag with the one in _flags. This is because a
        # flag might be overridden only for its long name (or short name),
        # and only its short name (or long name) is considered registered.
        if (flag.name == registered_flag.name and
            flag.short_name == registered_flag.short_name):
          return module_id
    return default

  def _register_unknown_flag_setter(self, setter):
    """Allow set default values for undefined flags.

    Args:
      setter: Method(name, value) to call to __setattr__ an unknown flag. Must
        raise NameError or ValueError for invalid name/value.
    """
    self.__dict__['__set_unknown'] = setter

  def _set_unknown_flag(self, name, value):
    """Returns value if setting flag |name| to |value| returned True.

    Args:
      name: str, name of the flag to set.
      value: Value to set.

    Returns:
      Flag value on successful call.

    Raises:
      UnrecognizedFlagError
      IllegalFlagValueError
    """
    setter = self.__dict__['__set_unknown']
    if setter:
      try:
        setter(name, value)
        return value
      except (TypeError, ValueError):  # Flag value is not valid.
        raise _exceptions.IllegalFlagValueError(
            '"{1}" is not valid for --{0}'.format(name, value))
      except NameError:  # Flag name is not valid.
        pass
    raise _exceptions.UnrecognizedFlagError(name, value)

  def append_flag_values(self, flag_values):
    """Appends flags registered in another FlagValues instance.

    Args:
      flag_values: FlagValues, the FlagValues instance from which to copy flags.
    """
    for flag_name, flag in flag_values._flags().items():  # pylint: disable=protected-access
      # Each flags with short_name appears here twice (once under its
      # normal name, and again with its short name).  To prevent
      # problems (DuplicateFlagError) with double flag registration, we
      # perform a check to make sure that the entry we're looking at is
      # for its normal name.
      if flag_name == flag.name:
        try:
          self[flag_name] = flag
        except _exceptions.DuplicateFlagError:
          raise _exceptions.DuplicateFlagError.from_flag(
              flag_name, self, other_flag_values=flag_values)

  def remove_flag_values(self, flag_values):
    """Remove flags that were previously appended from another FlagValues.

    Args:
      flag_values: FlagValues, the FlagValues instance containing flags to
        remove.
    """
    for flag_name in flag_values:
      self.__delattr__(flag_name)

  def __setitem__(self, name, flag):
    """Registers a new flag variable."""
    fl = self._flags()
    if not isinstance(flag, _flag.Flag):
      raise _exceptions.IllegalFlagValueError(
          f'Expect Flag instances, found type {type(flag)}. '
          "Maybe you didn't mean to use FlagValue.__setitem__?")
    if not isinstance(name, str):
      raise _exceptions.Error('Flag name must be a string')
    if not name:
      raise _exceptions.Error('Flag name cannot be empty')
    if ' ' in name:
      raise _exceptions.Error('Flag name cannot contain a space')
    self._check_method_name_conflicts(name, flag)
    if name in fl and not flag.allow_override and not fl[name].allow_override:
      module, module_name = _helpers.get_calling_module_object_and_name()
      if (self.find_module_defining_flag(name) == module_name and
          id(module) != self.find_module_id_defining_flag(name)):
        # If the flag has already been defined by a module with the same name,
        # but a different ID, we can stop here because it indicates that the
        # module is simply being imported a subsequent time.
        return
      raise _exceptions.DuplicateFlagError.from_flag(name, self)
    short_name = flag.short_name
    # If a new flag overrides an old one, we need to cleanup the old flag's
    # modules if it's not registered.
    flags_to_cleanup = set()
    if short_name is not None:
      if (short_name in fl and not flag.allow_override and
          not fl[short_name].allow_override):
        raise _exceptions.DuplicateFlagError.from_flag(short_name, self)
      if short_name in fl and fl[short_name] != flag:
        flags_to_cleanup.add(fl[short_name])
      fl[short_name] = flag
    if (name not in fl  # new flag
        or fl[name].using_default_value or not flag.using_default_value):
      if name in fl and fl[name] != flag:
        flags_to_cleanup.add(fl[name])
      fl[name] = flag
    for f in flags_to_cleanup:
      self._cleanup_unregistered_flag_from_module_dicts(f)

  def __dir__(self):
    """Returns list of names of all defined flags.

    Useful for TAB-completion in ipython.

    Returns:
      [str], a list of names of all defined flags.
    """
    return sorted(self.__dict__['__flags'])

  def __getitem__(self, name):
    """Returns the Flag object for the flag --name."""
    return self._flags()[name]

  def _hide_flag(self, name):
    """Marks the flag --name as hidden."""
    self.__dict__['__hiddenflags'].add(name)

  def __getattr__(self, name):
    """Retrieves the 'value' attribute of the flag --name."""
    fl = self._flags()
    if name not in fl:
      raise AttributeError(name)
    if name in self.__dict__['__hiddenflags']:
      raise AttributeError(name)

    if self.__dict__['__flags_parsed'] or fl[name].present:
      return fl[name].value
    else:
      raise _exceptions.UnparsedFlagAccessError(
          'Trying to access flag --%s before flags were parsed.' % name)

  def __setattr__(self, name, value):
    """Sets the 'value' attribute of the flag --name."""
    self._set_attributes(**{name: value})
    return value

  def _set_attributes(self, **attributes):
    """Sets multiple flag values together, triggers validators afterwards."""
    fl = self._flags()
    known_flags = set()
    for name, value in attributes.items():
      if name in self.__dict__['__hiddenflags']:
        raise AttributeError(name)
      if name in fl:
        fl[name].value = value
        known_flags.add(name)
      else:
        self._set_unknown_flag(name, value)
    for name in known_flags:
      self._assert_validators(fl[name].validators)
      fl[name].using_default_value = False

  def validate_all_flags(self):
    """Verifies whether all flags pass validation.

    Raises:
      AttributeError: Raised if validators work with a non-existing flag.
      IllegalFlagValueError: Raised if validation fails for at least one
          validator.
    """
    all_validators = set()
    for flag in self._flags().values():
      all_validators.update(flag.validators)
    self._assert_validators(all_validators)

  def _assert_validators(self, validators):
    """Asserts if all validators in the list are satisfied.

    It asserts validators in the order they were created.

    Args:
      validators: Iterable(validators.Validator), validators to be verified.

    Raises:
      AttributeError: Raised if validators work with a non-existing flag.
      IllegalFlagValueError: Raised if validation fails for at least one
          validator.
    """
    messages = []
    bad_flags = set()
    for validator in sorted(
        validators, key=lambda validator: validator.insertion_index):
      try:
        if isinstance(validator, _validators_classes.SingleFlagValidator):
          if validator.flag_name in bad_flags:
            continue
        elif isinstance(validator, _validators_classes.MultiFlagsValidator):
          if bad_flags & set(validator.flag_names):
            continue
        validator.verify(self)
      except _exceptions.ValidationError as e:
        if isinstance(validator, _validators_classes.SingleFlagValidator):
          bad_flags.add(validator.flag_name)
        elif isinstance(validator, _validators_classes.MultiFlagsValidator):
          bad_flags.update(set(validator.flag_names))
        message = validator.print_flags_with_values(self)
        messages.append('%s: %s' % (message, str(e)))
    if messages:
      raise _exceptions.IllegalFlagValueError('\n'.join(messages))

  def __delattr__(self, flag_name):
    """Deletes a previously-defined flag from a flag object.

    This method makes sure we can delete a flag by using

      del FLAGS.<flag_name>

    E.g.,

      flags.DEFINE_integer('foo', 1, 'Integer flag.')
      del flags.FLAGS.foo

    If a flag is also registered by its the other name (long name or short
    name), the other name won't be deleted.

    Args:
      flag_name: str, the name of the flag to be deleted.

    Raises:
      AttributeError: Raised when there is no registered flag named flag_name.
    """
    fl = self._flags()
    if flag_name not in fl:
      raise AttributeError(flag_name)

    flag_obj = fl[flag_name]
    del fl[flag_name]

    self._cleanup_unregistered_flag_from_module_dicts(flag_obj)

  def set_default(self, name, value):
    """Changes the default value of the named flag object.

    The flag's current value is also updated if the flag is currently using
    the default value, i.e. not specified in the command line, and not set
    by FLAGS.name = value.

    Args:
      name: str, the name of the flag to modify.
      value: The new default value.

    Raises:
      UnrecognizedFlagError: Raised when there is no registered flag named name.
      IllegalFlagValueError: Raised when value is not valid.
    """
    fl = self._flags()
    if name not in fl:
      self._set_unknown_flag(name, value)
      return
    fl[name]._set_default(value)  # pylint: disable=protected-access
    self._assert_validators(fl[name].validators)

  def __contains__(self, name):
    """Returns True if name is a value (flag) in the dict."""
    return name in self._flags()

  def __len__(self):
    return len(self.__dict__['__flags'])

  def __iter__(self):
    return iter(self._flags())

  def __call__(self, argv, known_only=False):
    """Parses flags from argv; stores parsed flags into this FlagValues object.

    All unparsed arguments are returned.

    Args:
       argv: a tuple/list of strings.
       known_only: bool, if True, parse and remove known flags; return the rest
         untouched. Unknown flags specified by --undefok are not returned.

    Returns:
       The list of arguments not parsed as options, including argv[0].

    Raises:
       Error: Raised on any parsing error.
       TypeError: Raised on passing wrong type of arguments.
       ValueError: Raised on flag value parsing error.
    """
    if isinstance(argv, (str, bytes)):
      raise TypeError(
          'argv should be a tuple/list of strings, not bytes or string.')
    if not argv:
      raise ValueError(
          'argv cannot be an empty list, and must contain the program name as '
          'the first element.')

    # This pre parses the argv list for --flagfile=<> options.
    program_name = argv[0]
    args = self.read_flags_from_files(argv[1:], force_gnu=False)

    # Parse the arguments.
    unknown_flags, unparsed_args = self._parse_args(args, known_only)

    # Handle unknown flags by raising UnrecognizedFlagError.
    # Note some users depend on us raising this particular error.
    for name, value in unknown_flags:
      suggestions = _helpers.get_flag_suggestions(name, list(self))
      raise _exceptions.UnrecognizedFlagError(
          name, value, suggestions=suggestions)

    self.mark_as_parsed()
    self.validate_all_flags()
    return [program_name] + unparsed_args

  def __getstate__(self):
    raise TypeError("can't pickle FlagValues")

  def __copy__(self):
    raise TypeError('FlagValues does not support shallow copies. '
                    'Use absl.testing.flagsaver or copy.deepcopy instead.')

  def __deepcopy__(self, memo):
    result = object.__new__(type(self))
    result.__dict__.update(copy.deepcopy(self.__dict__, memo))
    return result

  def _set_is_retired_flag_func(self, is_retired_flag_func):
    """Sets a function for checking retired flags.

    Do not use it. This is a private absl API used to check retired flags
    registered by the absl C++ flags library.

    Args:
      is_retired_flag_func: Callable(str) -> (bool, bool), a function takes flag
        name as parameter, returns a tuple (is_retired, type_is_bool).
    """
    self.__dict__['__is_retired_flag_func'] = is_retired_flag_func

  def _parse_args(self, args, known_only):
    """Helper function to do the main argument parsing.

    This function goes through args and does the bulk of the flag parsing.
    It will find the corresponding flag in our flag dictionary, and call its
    .parse() method on the flag value.

    Args:
      args: [str], a list of strings with the arguments to parse.
      known_only: bool, if True, parse and remove known flags; return the rest
        untouched. Unknown flags specified by --undefok are not returned.

    Returns:
      A tuple with the following:
          unknown_flags: List of (flag name, arg) for flags we don't know about.
          unparsed_args: List of arguments we did not parse.

    Raises:
       Error: Raised on any parsing error.
       ValueError: Raised on flag value parsing error.
    """
    unparsed_names_and_args = []  # A list of (flag name or None, arg).
    undefok = set()
    retired_flag_func = self.__dict__['__is_retired_flag_func']

    flag_dict = self._flags()
    args = iter(args)
    for arg in args:
      value = None

      def get_value():
        # pylint: disable=cell-var-from-loop
        try:
          return next(args) if value is None else value
        except StopIteration:
          raise _exceptions.Error('Missing value for flag ' + arg)  # pylint: disable=undefined-loop-variable

      if not arg.startswith('-'):
        # A non-argument: default is break, GNU is skip.
        unparsed_names_and_args.append((None, arg))
        if self.is_gnu_getopt():
          continue
        else:
          break

      if arg == '--':
        if known_only:
          unparsed_names_and_args.append((None, arg))
        break

      # At this point, arg must start with '-'.
      if arg.startswith('--'):
        arg_without_dashes = arg[2:]
      else:
        arg_without_dashes = arg[1:]

      if '=' in arg_without_dashes:
        name, value = arg_without_dashes.split('=', 1)
      else: