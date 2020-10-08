
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

"""Contains base classes used to parse and convert arguments.

Do NOT import this module directly. Import the flags package and use the
aliases defined at the package level instead.
"""

import collections
import csv
import io
import string

from absl.flags import _helpers


def _is_integer_type(instance):
  """Returns True if instance is an integer, and not a bool."""
  return (isinstance(instance, int) and
          not isinstance(instance, bool))


class _ArgumentParserCache(type):
  """Metaclass used to cache and share argument parsers among flags."""

  _instances = {}

  def __call__(cls, *args, **kwargs):
    """Returns an instance of the argument parser cls.

    This method overrides behavior of the __new__ methods in
    all subclasses of ArgumentParser (inclusive). If an instance
    for cls with the same set of arguments exists, this instance is
    returned, otherwise a new instance is created.

    If any keyword arguments are defined, or the values in args
    are not hashable, this method always returns a new instance of
    cls.

    Args:
      *args: Positional initializer arguments.
      **kwargs: Initializer keyword arguments.

    Returns:
      An instance of cls, shared or new.
    """
    if kwargs:
      return type.__call__(cls, *args, **kwargs)
    else:
      instances = cls._instances
      key = (cls,) + tuple(args)
      try:
        return instances[key]
      except KeyError:
        # No cache entry for key exists, create a new one.
        return instances.setdefault(key, type.__call__(cls, *args))
      except TypeError:
        # An object in args cannot be hashed, always return
        # a new instance.
        return type.__call__(cls, *args)


# NOTE about Genericity and Metaclass of ArgumentParser.
# (1) In the .py source (this file)
#     - is not declared as Generic
#     - has _ArgumentParserCache as a metaclass
# (2) In the .pyi source (type stub)
#     - is declared as Generic
#     - doesn't have a metaclass
# The reason we need this is due to Generic having a different metaclass
# (for python versions <= 3.7) and a class can have only one metaclass.
#
# * Lack of metaclass in .pyi is not a deal breaker, since the metaclass
#   doesn't affect any type information. Also type checkers can check the type
#   parameters.
# * However, not declaring ArgumentParser as Generic in the source affects
#   runtime annotation processing. In particular this means, subclasses should
#   inherit from `ArgumentParser` and not `ArgumentParser[SomeType]`.
#   The corresponding DEFINE_someType method (the public API) can be annotated
#   to return FlagHolder[SomeType].
class ArgumentParser(metaclass=_ArgumentParserCache):
  """Base class used to parse and convert arguments.

  The :meth:`parse` method checks to make sure that the string argument is a
  legal value and convert it to a native type.  If the value cannot be
  converted, it should throw a ``ValueError`` exception with a human
  readable explanation of why the value is illegal.

  Subclasses should also define a syntactic_help string which may be
  presented to the user to describe the form of the legal values.

  Argument parser classes must be stateless, since instances are cached
  and shared between flags. Initializer arguments are allowed, but all
  member variables must be derived from initializer arguments only.
  """

  syntactic_help = ''

  def parse(self, argument):
    """Parses the string argument and returns the native value.

    By default it returns its argument unmodified.

    Args:
      argument: string argument passed in the commandline.

    Raises:
      ValueError: Raised when it fails to parse the argument.
      TypeError: Raised when the argument has the wrong type.

    Returns:
      The parsed value in native type.
    """
    if not isinstance(argument, str):
      raise TypeError('flag value must be a string, found "{}"'.format(
          type(argument)))
    return argument

  def flag_type(self):
    """Returns a string representing the type of the flag."""
    return 'string'

  def _custom_xml_dom_elements(self, doc):
    """Returns a list of minidom.Element to add additional flag information.

    Args:
      doc: minidom.Document, the DOM document it should create nodes from.
    """
    del doc  # Unused.
    return []


class ArgumentSerializer(object):
  """Base class for generating string representations of a flag value."""

  def serialize(self, value):
    """Returns a serialized string of the value."""
    return str(value)


class NumericParser(ArgumentParser):
  """Parser of numeric values.

  Parsed value may be bounded to a given upper and lower bound.
  """

  def is_outside_bounds(self, val):
    """Returns whether the value is outside the bounds or not."""
    return ((self.lower_bound is not None and val < self.lower_bound) or
            (self.upper_bound is not None and val > self.upper_bound))

  def parse(self, argument):
    """See base class."""
    val = self.convert(argument)
    if self.is_outside_bounds(val):
      raise ValueError('%s is not %s' % (val, self.syntactic_help))
    return val

  def _custom_xml_dom_elements(self, doc):
    elements = []
    if self.lower_bound is not None:
      elements.append(_helpers.create_xml_dom_element(
          doc, 'lower_bound', self.lower_bound))
    if self.upper_bound is not None:
      elements.append(_helpers.create_xml_dom_element(
          doc, 'upper_bound', self.upper_bound))
    return elements

  def convert(self, argument):
    """Returns the correct numeric value of argument.

    Subclass must implement this method, and raise TypeError if argument is not
    string or has the right numeric type.

    Args:
      argument: string argument passed in the commandline, or the numeric type.

    Raises:
      TypeError: Raised when argument is not a string or the right numeric type.
      ValueError: Raised when failed to convert argument to the numeric value.
    """
    raise NotImplementedError


class FloatParser(NumericParser):
  """Parser of floating point values.

  Parsed value may be bounded to a given upper and lower bound.
  """
  number_article = 'a'
  number_name = 'number'
  syntactic_help = ' '.join((number_article, number_name))

  def __init__(self, lower_bound=None, upper_bound=None):
    super(FloatParser, self).__init__()
    self.lower_bound = lower_bound
    self.upper_bound = upper_bound
    sh = self.syntactic_help
    if lower_bound is not None and upper_bound is not None:
      sh = ('%s in the range [%s, %s]' % (sh, lower_bound, upper_bound))
    elif lower_bound == 0:
      sh = 'a non-negative %s' % self.number_name
    elif upper_bound == 0:
      sh = 'a non-positive %s' % self.number_name
    elif upper_bound is not None:
      sh = '%s <= %s' % (self.number_name, upper_bound)
    elif lower_bound is not None:
      sh = '%s >= %s' % (self.number_name, lower_bound)
    self.syntactic_help = sh

  def convert(self, argument):
    """Returns the float value of argument."""
    if (_is_integer_type(argument) or isinstance(argument, float) or
        isinstance(argument, str)):
      return float(argument)
    else:
      raise TypeError(
          'Expect argument to be a string, int, or float, found {}'.format(
              type(argument)))

  def flag_type(self):