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

  Auxiliary function: clients should use the specialized ``DEFINE_<type>``
  function instead.

  Args:
    parser: :class:`ArgumentParser`, used to parse the flag arguments.
    name: str, the flag name.
    default: The default value of the flag.
    help: str, the help message.
    flag_values: :class:`FlagValues`, the FlagValues instance with which the
      flag will be registered. This should almost never need to be overridden.
    serializer: :class:`ArgumentSerializer`, the flag serializer instance.
    module_name: str, the name of the Python module declaring this flag. If not
      provided, it will be computed using the stack trace of this call.
    required: bool, is this a required flag. This must be used as a keyword
      argument.
    **args: dict, the extra keyword args that are passed to ``Flag.__init__``.

  Returns:
    a handle to defined flag.
  """
  return DEFINE_flag(
      _flag.Flag(parser, serializer, name, default, help, **args), flag_values,
      module_name, required)


def DEFINE_flag(  # pylint: disable=invalid-name
    flag,
    flag_values=_flagvalues.FLAGS,
    module_name=None,
    required=False):
  """Registers a :class:`Flag` object with a :class:`FlagValues` object.

  By default, the global :const:`FLAGS` ``FlagValue`` object is used.

  Typical users will use one of the more specialized DEFINE_xxx
  functions, such as :func:`DEFINE_string` or :func:`DEFINE_integer`.  But
  developers who need to create :class:`Flag` objects themselves should use
  this function to register their flags.

  Args:
    flag: :class:`Flag`, a flag that is key to the module.
    flag_values: :class:`FlagValues`, the ``FlagValues`` instance with which the
      flag will be registered. This should almost never need to be overridden.
    module_name: str, the name of the Python module declaring this flag. If not
      provided, it will be computed using the stack trace of this call.
    required: bool, is this a required flag. This must be used as a keyword
      argument.

  Returns:
    a handle to defined flag.
  """
  if required and flag.default is not None:
    raise ValueError('Required flag --%s cannot have a non-None default' %
                     flag.name)
  # Copying the reference to flag_values prevents pychecker warnings.
  fv = flag_values
  fv[flag.name] = flag
  # Tell flag_values who's defining the flag.
  if module_name:
    module = sys.modules.get(module_name)
  else:
    module, module_name = _helpers.get_calling_module_object_and_name()
  flag_values.register_flag_by_module(module_name, flag)
  flag_values.register_flag_by_module_id(id(module), flag)
  if required:
    _validators.mark_flag_as_required(flag.name, fv)
  ensure_non_none_value = (flag.default is not None) or required
  return _flagvalues.FlagHolder(
      fv, flag, ensure_non_none_value=ensure_non_none_value)


def set_default(flag_holder, value):
  """Changes the default value of the provided flag object.

  The flag's current value is also updated if the flag is currently using
  the default value, i.e. not specified in the command line, and not set
  by FLAGS.name = value.

  Args:
    flag_holder: FlagHolder, the flag to modify.
    value: The new default value.

  Raises:
    IllegalFlagValueError: Raised when value is not valid.
  """
  flag_holder._flagvalues.set_default(flag_holder.name, value)  # pylint: disable=protected-access


def _internal_declare_key_flags(flag_names,
                                flag_values=_flagvalues.FLAGS,
                                key_flag_values=None):
  """Declares a flag as key for the calling module.

  Internal function.  User code should call declare_key_flag or
  adopt_module_key_flags instead.

  Args:
    flag_names: [str], a list of names of already-registered Flag objects.
    flag_values: :class:`FlagValues`, the FlagValues instance with which the
      flags listed in flag_names have registered (the value of the flag_values
      argument from the ``DEFINE_*`` calls that defined those flags). This
      should almost never need to be overridden.
    key_flag_values: :class:`FlagValues`, the FlagValues instance that (among
      possibly many other things) keeps track of the key flags for each module.
      Default ``None`` means "same as flag_values".  This should almost never
      need to be overridden.

  Raises:
    UnrecognizedFlagError: Raised when the flag is not defined.
  """
  key_flag_values = key_flag_values or flag_values

  module = _helpers.get_calling_module()

  for flag_name in flag_names:
    key_flag_values.register_key_flag_for_module(module, flag_values[flag_name])


def declare_key_flag(flag_name, flag_values=_flagvalues.FLAGS):
  """Declares one flag as key to the current module.

  Key flags are flags that are deemed really important for a module.
  They are important when listing help messages; e.g., if the
  --helpshort command-line flag is used, then only the key flags of the
  main module are listed (instead of all flags, as in the case of
  --helpfull).

  Sample usage::

      flags.declare_key_flag('flag_1')

  Args:
    flag_name: str | :class:`FlagHolder`, the name or holder of an already
      declared flag. (Redeclaring flags as key, including flags implicitly key
      because they were declared in this module, is a no-op.)
      Positional-only parameter.
    flag_values: :class:`FlagVal