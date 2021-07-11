
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

"""Decorator and context manager for saving and restoring flag values.

There are many ways to save and restore.  Always use the most convenient method
for a given use case.

Here are examples of each method.  They all call ``do_stuff()`` while
``FLAGS.someflag`` is temporarily set to ``'foo'``::

    from absl.testing import flagsaver

    # Use a decorator which can optionally override flags via arguments.
    @flagsaver.flagsaver(someflag='foo')
    def some_func():
      do_stuff()

    # Use a decorator which can optionally override flags with flagholders.
    @flagsaver.flagsaver((module.FOO_FLAG, 'foo'), (other_mod.BAR_FLAG, 23))
    def some_func():
      do_stuff()

    # Use a decorator which does not override flags itself.
    @flagsaver.flagsaver
    def some_func():
      FLAGS.someflag = 'foo'
      do_stuff()

    # Use a context manager which can optionally override flags via arguments.
    with flagsaver.flagsaver(someflag='foo'):
      do_stuff()

    # Save and restore the flag values yourself.
    saved_flag_values = flagsaver.save_flag_values()
    try:
      FLAGS.someflag = 'foo'
      do_stuff()
    finally:
      flagsaver.restore_flag_values(saved_flag_values)

    # Use the parsing version to emulate users providing the flags.
    # Note that all flags must be provided as strings (unparsed).
    @flagsaver.as_parsed(some_int_flag='123')
    def some_func():
      # Because the flag was parsed it is considered "present".
      assert FLAGS.some_int_flag.present
      do_stuff()

    # flagsaver.as_parsed() can also be used as a context manager just like
    # flagsaver.flagsaver()
    with flagsaver.as_parsed(some_int_flag='123'):
      do_stuff()

    # The flagsaver.as_parsed() interface also supports FlagHolder objects.
    @flagsaver.as_parsed((module.FOO_FLAG, 'foo'), (other_mod.BAR_FLAG, '23'))
    def some_func():
      do_stuff()

    # Using as_parsed with a multi_X flag requires a sequence of strings.
    @flagsaver.as_parsed(some_multi_int_flag=['123', '456'])
    def some_func():
      assert FLAGS.some_multi_int_flag.present
      do_stuff()

    # If a flag name includes non-identifier characters it can be specified like
    # so:
    @flagsaver.as_parsed(**{'i-like-dashes': 'true'})
    def some_func():
      do_stuff()

We save and restore a shallow copy of each Flag object's ``__dict__`` attribute.
This preserves all attributes of the flag, such as whether or not it was
overridden from its default value.

WARNING: Currently a flag that is saved and then deleted cannot be restored.  An
exception will be raised.  However if you *add* a flag after saving flag values,
and then restore flag values, the added flag will be deleted with no errors.
"""

import collections
import functools
import inspect
from typing import overload, Any, Callable, Mapping, Tuple, TypeVar, Type, Sequence, Union

from absl import flags

FLAGS = flags.FLAGS


# The type of pre/post wrapped functions.
_CallableT = TypeVar('_CallableT', bound=Callable)


@overload
def flagsaver(*args: Tuple[flags.FlagHolder, Any],
              **kwargs: Any) -> '_FlagOverrider':
  ...


@overload
def flagsaver(func: _CallableT) -> _CallableT:
  ...


def flagsaver(*args, **kwargs):
  """The main flagsaver interface. See module doc for usage."""
  return _construct_overrider(_FlagOverrider, *args, **kwargs)


@overload
def as_parsed(*args: Tuple[flags.FlagHolder, Union[str, Sequence[str]]],
              **kwargs: Union[str, Sequence[str]]) -> '_ParsingFlagOverrider':
  ...


@overload
def as_parsed(func: _CallableT) -> _CallableT:
  ...


def as_parsed(*args, **kwargs):
  """Overrides flags by parsing strings, saves flag state similar to flagsaver.

  This function can be used as either a decorator or context manager similar to
  flagsaver.flagsaver(). However, where flagsaver.flagsaver() directly sets the
  flags to new values, this function will parse the provided arguments as if
  they were provided on the command line. Among other things, this will cause
  `FLAGS['flag_name'].parsed == True`.

  A note on unparsed input: For many flag types, the unparsed version will be
  a single string. However for multi_x (multi_string, multi_integer, multi_enum)
  the unparsed version will be a Sequence of strings.

  Args:
    *args: Tuples of FlagHolders and their unparsed value.
    **kwargs: The keyword args are flag names, and the values are unparsed
      values.

  Returns:
    _ParsingFlagOverrider that serves as a context manager or decorator. Will