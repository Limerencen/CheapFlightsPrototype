
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

"""Internal helper functions for Abseil Python flags library."""

import collections
import os
import re
import struct
import sys
import textwrap
try:
  import fcntl
except ImportError:
  fcntl = None
try:
  # Importing termios will fail on non-unix platforms.
  import termios
except ImportError:
  termios = None


_DEFAULT_HELP_WIDTH = 80  # Default width of help output.
# Minimal "sane" width of help output. We assume that any value below 40 is
# unreasonable.
_MIN_HELP_WIDTH = 40

# Define the allowed error rate in an input string to get suggestions.
#
# We lean towards a high threshold because we tend to be matching a phrase,
# and the simple algorithm used here is geared towards correcting word
# spellings.
#
# For manual testing, consider "<command> --list" which produced a large number
# of spurious suggestions when we used "least_errors > 0.5" instead of
# "least_erros >= 0.5".
_SUGGESTION_ERROR_RATE_THRESHOLD = 0.50

# Characters that cannot appear or are highly discouraged in an XML 1.0
# document. (See http://www.w3.org/TR/REC-xml/#charsets or
# https://en.wikipedia.org/wiki/Valid_characters_in_XML#XML_1.0)
_ILLEGAL_XML_CHARS_REGEX = re.compile(
    u'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f\ud800-\udfff\ufffe\uffff]')

# This is a set of module ids for the modules that disclaim key flags.
# This module is explicitly added to this set so that we never consider it to
# define key flag.
disclaim_module_ids = set([id(sys.modules[__name__])])


# Define special flags here so that help may be generated for them.
# NOTE: Please do NOT use SPECIAL_FLAGS from outside flags module.
# Initialized inside flagvalues.py.
SPECIAL_FLAGS = None


# This points to the flags module, initialized in flags/__init__.py.
# This should only be used in adopt_module_key_flags to take SPECIAL_FLAGS into
# account.
FLAGS_MODULE = None


class _ModuleObjectAndName(
    collections.namedtuple('_ModuleObjectAndName', 'module module_name')):
  """Module object and name.

  Fields:
  - module: object, module object.
  - module_name: str, module name.
  """


def get_module_object_and_name(globals_dict):
  """Returns the module that defines a global environment, and its name.

  Args:
    globals_dict: A dictionary that should correspond to an environment
      providing the values of the globals.

  Returns:
    _ModuleObjectAndName - pair of module object & module name.
    Returns (None, None) if the module could not be identified.
  """
  name = globals_dict.get('__name__', None)
  module = sys.modules.get(name, None)
  # Pick a more informative name for the main module.
  return _ModuleObjectAndName(module,
                              (sys.argv[0] if name == '__main__' else name))


def get_calling_module_object_and_name():
  """Returns the module that's calling into this module.

  We generally use this function to get the name of the module calling a
  DEFINE_foo... function.

  Returns:
    The module object that called into this one.

  Raises:
    AssertionError: Raised when no calling module could be identified.
  """
  for depth in range(1, sys.getrecursionlimit()):
    # sys._getframe is the right thing to use here, as it's the best
    # way to walk up the call stack.
    globals_for_frame = sys._getframe(depth).f_globals  # pylint: disable=protected-access
    module, module_name = get_module_object_and_name(globals_for_frame)
    if id(module) not in disclaim_module_ids and module_name is not None:
      return _ModuleObjectAndName(module, module_name)
  raise AssertionError('No module was found')


def get_calling_module():
  """Returns the name of the module that's calling into this module."""
  return get_calling_module_object_and_name().module_name


def create_xml_dom_element(doc, name, value):
  """Returns an XML DOM element with name and text value.

  Args:
    doc: minidom.Document, the DOM document it should create nodes from.
    name: str, the tag of XML element.
    value: object, whose string representation will be used
        as the value of the XML element. Illegal or highly discouraged xml 1.0
        characters are stripped.

  Returns:
    An instance of minidom.Element.
  """
  s = str(value)
  if isinstance(value, bool):
    # Display boolean values as the C++ flag library does: no caps.
    s = s.lower()
  # Remove illegal xml characters.
  s = _ILLEGAL_XML_CHARS_REGEX.sub(u'', s)

  e = doc.createElement(name)
  e.appendChild(doc.createTextNode(s))
  return e


def get_help_width():
  """Returns the integer width of help lines that is used in TextWrap."""
  if not sys.stdout.isatty() or termios is None or fcntl is None:
    return _DEFAULT_HELP_WIDTH
  try:
    data = fcntl.ioctl(sys.stdout, termios.TIOCGWINSZ, '1234')
    columns = struct.unpack('hh', data)[1]
    # Emacs mode returns 0.
    # Here we assume that any value below 40 is unreasonable.
    if columns >= _MIN_HELP_WIDTH:
      return columns
    # Returning an int as default is fine, int(int) just return the int.
    return int(os.getenv('COLUMNS', _DEFAULT_HELP_WIDTH))

  except (TypeError, IOError, struct.error):
    return _DEFAULT_HELP_WIDTH


def get_flag_suggestions(attempt, longopt_list):
  """Returns helpful similar matches for an invalid flag."""
  # Don't suggest on very short strings, or if no longopts are specified.
  if len(attempt) <= 2 or not longopt_list:
    return []

  option_names = [v.split('=')[0] for v in longopt_list]

  # Find close approximations in flag prefixes.
  # This also handles the case where the flag is spelled right but ambiguous.
  distances = [(_damerau_levenshtein(attempt, option[0:len(attempt)]), option)
               for option in option_names]
  # t[0] is distance, and sorting by t[1] allows us to have stable output.
  distances.sort()

  least_errors, _ = distances[0]
  # Don't suggest excessively bad matches.
  if least_errors >= _SUGGESTION_ERROR_RATE_THRESHOLD * len(attempt):
    return []

  suggestions = []
  for errors, name in distances:
    if errors == least_errors:
      suggestions.append(name)
    else:
      break
  return suggestions


def _damerau_levenshtein(a, b):
  """Returns Damerau-Levenshtein edit distance from a to b."""
  memo = {}

  def distance(x, y):
    """Recursively defined string distance with memoization."""
    if (x, y) in memo:
      return memo[x, y]
    if not x:
      d = len(y)
    elif not y:
      d = len(x)
    else:
      d = min(
          distance(x[1:], y) + 1,  # correct an insertion error
          distance(x, y[1:]) + 1,  # correct a deletion error
          distance(x[1:], y[1:]) + (x[0] != y[0]))  # correct a wrong character
      if len(x) >= 2 and len(y) >= 2 and x[0] == y[1] and x[1] == y[0]:
        # Correct a transposition.
        t = distance(x[2:], y[2:]) + 1
        if d > t:
          d = t

    memo[x, y] = d
    return d
  return distance(a, b)


def text_wrap(text, length=None, indent='', firstline_indent=None):
  """Wraps a given text to a maximum line length and returns it.

  It turns lines that only contain whitespace into empty lines, keeps new lines,
  and expands tabs using 4 spaces.

  Args:
    text: str, text to wrap.
    length: int, maximum length of a line, includes indentation.
        If this is None then use get_help_width()
    indent: str, indent for all but first line.
    firstline_indent: str, indent for first line; if None, fall back to indent.

  Returns:
    str, the wrapped text.

  Raises:
    ValueError: Raised if indent or firstline_indent not shorter than length.
  """
  # Get defaults where callee used None
  if length is None:
    length = get_help_width()
  if indent is None:
    indent = ''
  if firstline_indent is None:
    firstline_indent = indent

  if len(indent) >= length:
    raise ValueError('Length of indent exceeds length')
  if len(firstline_indent) >= length:
    raise ValueError('Length of first line indent exceeds length')

  text = text.expandtabs(4)

  result = []
  # Create one wrapper for the first paragraph and one for subsequent
  # paragraphs that does not have the initial wrapping.
  wrapper = textwrap.TextWrapper(