
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

"""Abseil Python logging module implemented on top of standard logging.

Simple usage::

    from absl import logging

    logging.info('Interesting Stuff')
    logging.info('Interesting Stuff with Arguments: %d', 42)

    logging.set_verbosity(logging.INFO)
    logging.log(logging.DEBUG, 'This will *not* be printed')
    logging.set_verbosity(logging.DEBUG)
    logging.log(logging.DEBUG, 'This will be printed')

    logging.warning('Worrying Stuff')
    logging.error('Alarming Stuff')
    logging.fatal('AAAAHHHHH!!!!')  # Process exits.

Usage note: Do not pre-format the strings in your program code.
Instead, let the logging module perform argument interpolation.
This saves cycles because strings that don't need to be printed
are never formatted.  Note that this module does not attempt to
interpolate arguments when no arguments are given.  In other words::

    logging.info('Interesting Stuff: %s')

does not raise an exception because logging.info() has only one
argument, the message string.

"Lazy" evaluation for debugging
-------------------------------

If you do something like this::

    logging.debug('Thing: %s', thing.ExpensiveOp())

then the ExpensiveOp will be evaluated even if nothing
is printed to the log. To avoid this, use the level_debug() function::

  if logging.level_debug():
    logging.debug('Thing: %s', thing.ExpensiveOp())

Per file level logging is supported by logging.vlog() and
logging.vlog_is_on(). For example::

    if logging.vlog_is_on(2):
      logging.vlog(2, very_expensive_debug_message())

Notes on Unicode
----------------

The log output is encoded as UTF-8.  Don't pass data in other encodings in
bytes() instances -- instead pass unicode string instances when you need to
(for both the format string and arguments).

Note on critical and fatal:
Standard logging module defines fatal as an alias to critical, but it's not
documented, and it does NOT actually terminate the program.
This module only defines fatal but not critical, and it DOES terminate the
program.

The differences in behavior are historical and unfortunate.
"""

import collections
from collections import abc
import getpass
import io
import itertools
import logging
import os
import socket
import struct
import sys
import tempfile
import threading
import tempfile
import time
import timeit
import traceback
import types
import warnings

from absl import flags
from absl.logging import converter

try:
  from typing import NoReturn
except ImportError:
  pass


FLAGS = flags.FLAGS


# Logging levels.
FATAL = converter.ABSL_FATAL
ERROR = converter.ABSL_ERROR
WARNING = converter.ABSL_WARNING
WARN = converter.ABSL_WARNING  # Deprecated name.
INFO = converter.ABSL_INFO
DEBUG = converter.ABSL_DEBUG

# Regex to match/parse log line prefixes.
ABSL_LOGGING_PREFIX_REGEX = (
    r'^(?P<severity>[IWEF])'
    r'(?P<month>\d\d)(?P<day>\d\d) '
    r'(?P<hour>\d\d):(?P<minute>\d\d):(?P<second>\d\d)'
    r'\.(?P<microsecond>\d\d\d\d\d\d) +'
    r'(?P<thread_id>-?\d+) '
    r'(?P<filename>[a-zA-Z<][\w._<>-]+):(?P<line>\d+)')


# Mask to convert integer thread ids to unsigned quantities for logging purposes
_THREAD_ID_MASK = 2 ** (struct.calcsize('L') * 8) - 1

# Extra property set on the LogRecord created by ABSLLogger when its level is
# CRITICAL/FATAL.
_ABSL_LOG_FATAL = '_absl_log_fatal'
# Extra prefix added to the log message when a non-absl logger logs a
# CRITICAL/FATAL message.
_CRITICAL_PREFIX = 'CRITICAL - '

# Used by findCaller to skip callers from */logging/__init__.py.
_LOGGING_FILE_PREFIX = os.path.join('logging', '__init__.')

# The ABSL logger instance, initialized in _initialize().
_absl_logger = None
# The ABSL handler instance, initialized in _initialize().
_absl_handler = None


_CPP_NAME_TO_LEVELS = {
    'debug': '0',  # Abseil C++ has no DEBUG level, mapping it to INFO here.
    'info': '0',
    'warning': '1',
    'warn': '1',
    'error': '2',
    'fatal': '3'
}

_CPP_LEVEL_TO_NAMES = {
    '0': 'info',
    '1': 'warning',
    '2': 'error',
    '3': 'fatal',
}


class _VerbosityFlag(flags.Flag):
  """Flag class for -v/--verbosity."""

  def __init__(self, *args, **kwargs):
    super(_VerbosityFlag, self).__init__(
        flags.IntegerParser(),
        flags.ArgumentSerializer(),
        *args, **kwargs)

  @property
  def value(self):
    return self._value

  @value.setter
  def value(self, v):
    self._value = v
    self._update_logging_levels()

  def _update_logging_levels(self):
    """Updates absl logging levels to the current verbosity.

    Visibility: module-private
    """
    if not _absl_logger:
      return

    if self._value <= converter.ABSL_DEBUG:
      standard_verbosity = converter.absl_to_standard(self._value)
    else:
      # --verbosity is set to higher than 1 for vlog.
      standard_verbosity = logging.DEBUG - (self._value - 1)