
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

"""Functional tests for absl.logging."""

import fnmatch
import os
import re
import shutil
import subprocess
import sys
import tempfile

from absl import logging
from absl.testing import _bazelize_command
from absl.testing import absltest
from absl.testing import parameterized


_PY_VLOG3_LOG_MESSAGE = """\
I1231 23:59:59.000000 12345 logging_functional_test_helper.py:62] This line is VLOG level 3
"""

_PY_VLOG2_LOG_MESSAGE = """\
I1231 23:59:59.000000 12345 logging_functional_test_helper.py:64] This line is VLOG level 2
I1231 23:59:59.000000 12345 logging_functional_test_helper.py:64] This line is log level 2
I1231 23:59:59.000000 12345 logging_functional_test_helper.py:64] VLOG level 1, but only if VLOG level 2 is active
"""

# VLOG1 is the same as DEBUG logs.
_PY_DEBUG_LOG_MESSAGE = """\
I1231 23:59:59.000000 12345 logging_functional_test_helper.py:65] This line is VLOG level 1
I1231 23:59:59.000000 12345 logging_functional_test_helper.py:65] This line is log level 1
I1231 23:59:59.000000 12345 logging_functional_test_helper.py:66] This line is DEBUG
"""

_PY_INFO_LOG_MESSAGE = """\
I1231 23:59:59.000000 12345 logging_functional_test_helper.py:65] This line is VLOG level 0
I1231 23:59:59.000000 12345 logging_functional_test_helper.py:65] This line is log level 0
I1231 23:59:59.000000 12345 logging_functional_test_helper.py:70] Interesting Stuff\0
I1231 23:59:59.000000 12345 logging_functional_test_helper.py:71] Interesting Stuff with Arguments: 42
I1231 23:59:59.000000 12345 logging_functional_test_helper.py:73] Interesting Stuff with Dictionary
I1231 23:59:59.000000 12345 logging_functional_test_helper.py:123] This should appear 5 times.
I1231 23:59:59.000000 12345 logging_functional_test_helper.py:123] This should appear 5 times.
I1231 23:59:59.000000 12345 logging_functional_test_helper.py:123] This should appear 5 times.
I1231 23:59:59.000000 12345 logging_functional_test_helper.py:123] This should appear 5 times.
I1231 23:59:59.000000 12345 logging_functional_test_helper.py:123] This should appear 5 times.
I1231 23:59:59.000000 12345 logging_functional_test_helper.py:76] Info first 1 of 2
I1231 23:59:59.000000 12345 logging_functional_test_helper.py:77] Info 1 (every 3)
I1231 23:59:59.000000 12345 logging_functional_test_helper.py:76] Info first 2 of 2
I1231 23:59:59.000000 12345 logging_functional_test_helper.py:77] Info 4 (every 3)
"""

_PY_INFO_LOG_MESSAGE_NOPREFIX = """\
This line is VLOG level 0
This line is log level 0
Interesting Stuff\0
Interesting Stuff with Arguments: 42
Interesting Stuff with Dictionary
This should appear 5 times.
This should appear 5 times.
This should appear 5 times.
This should appear 5 times.
This should appear 5 times.
Info first 1 of 2
Info 1 (every 3)
Info first 2 of 2
Info 4 (every 3)
"""

_PY_WARNING_LOG_MESSAGE = """\
W1231 23:59:59.000000 12345 logging_functional_test_helper.py:65] This line is VLOG level -1
W1231 23:59:59.000000 12345 logging_functional_test_helper.py:65] This line is log level -1
W1231 23:59:59.000000 12345 logging_functional_test_helper.py:79] Worrying Stuff
W0000 23:59:59.000000 12345 logging_functional_test_helper.py:81] Warn first 1 of 2
W0000 23:59:59.000000 12345 logging_functional_test_helper.py:82] Warn 1 (every 3)
W0000 23:59:59.000000 12345 logging_functional_test_helper.py:81] Warn first 2 of 2
W0000 23:59:59.000000 12345 logging_functional_test_helper.py:82] Warn 4 (every 3)
"""

if sys.version_info[0:2] == (3, 4):
  _FAKE_ERROR_EXTRA_MESSAGE = """\
Traceback (most recent call last):
  File "logging_functional_test_helper.py", line 456, in _test_do_logging
    raise OSError('Fake Error')
"""
else:
  _FAKE_ERROR_EXTRA_MESSAGE = ''

_PY_ERROR_LOG_MESSAGE = """\
E1231 23:59:59.000000 12345 logging_functional_test_helper.py:65] This line is VLOG level -2
E1231 23:59:59.000000 12345 logging_functional_test_helper.py:65] This line is log level -2
E1231 23:59:59.000000 12345 logging_functional_test_helper.py:87] An Exception %s
Traceback (most recent call last):
  File "logging_functional_test_helper.py", line 456, in _test_do_logging
    raise OSError('Fake Error')
OSError: Fake Error
E0000 00:00:00.000000 12345 logging_functional_test_helper.py:123] Once more, just because
Traceback (most recent call last):
  File "./logging_functional_test_helper.py", line 78, in _test_do_logging
    raise OSError('Fake Error')
OSError: Fake Error
E0000 00:00:00.000000 12345 logging_functional_test_helper.py:123] Exception 2 %s
Traceback (most recent call last):
  File "logging_functional_test_helper.py", line 456, in _test_do_logging
    raise OSError('Fake Error')
OSError: Fake Error
E0000 00:00:00.000000 12345 logging_functional_test_helper.py:123] Non-exception
E0000 00:00:00.000000 12345 logging_functional_test_helper.py:123] Exception 3
Traceback (most recent call last):
  File "logging_functional_test_helper.py", line 456, in _test_do_logging
    raise OSError('Fake Error')
OSError: Fake Error
E0000 00:00:00.000000 12345 logging_functional_test_helper.py:123] No traceback
{fake_error_extra}OSError: Fake Error
E1231 23:59:59.000000 12345 logging_functional_test_helper.py:90] Alarming Stuff
E0000 23:59:59.000000 12345 logging_functional_test_helper.py:92] Error first 1 of 2
E0000 23:59:59.000000 12345 logging_functional_test_helper.py:93] Error 1 (every 3)
E0000 23:59:59.000000 12345 logging_functional_test_helper.py:92] Error first 2 of 2
E0000 23:59:59.000000 12345 logging_functional_test_helper.py:93] Error 4 (every 3)
""".format(fake_error_extra=_FAKE_ERROR_EXTRA_MESSAGE)


_CRITICAL_DOWNGRADE_TO_ERROR_MESSAGE = """\
E0000 00:00:00.000000 12345 logging_functional_test_helper.py:123] CRITICAL - A critical message
"""


_VERBOSITY_FLAG_TEST_PARAMETERS = (
    ('fatal', logging.FATAL),
    ('error', logging.ERROR),
    ('warning', logging.WARN),
    ('info', logging.INFO),
    ('debug', logging.DEBUG),
    ('vlog1', 1),
    ('vlog2', 2),
    ('vlog3', 3))


def _get_fatal_log_expectation(testcase, message, include_stacktrace):
  """Returns the expectation for fatal logging tests.

  Args:
    testcase: The TestCase instance.
    message: The extra fatal logging message.
    include_stacktrace: Whether or not to include stacktrace.

  Returns:
    A callable, the expectation for fatal logging tests. It will be passed to
    FunctionalTest._exec_test as third items in the expected_logs list.
    See _exec_test's docstring for more information.
  """
  def assert_logs(logs):
    if os.name == 'nt':
      # On Windows, it also dumps extra information at the end, something like:
      # This application has requested the Runtime to terminate it in an
      # unusual way. Please contact the application's support team for more
      # information.
      logs = '\n'.join(logs.split('\n')[:-3])
    format_string = (
        'F1231 23:59:59.000000 12345 logging_functional_test_helper.py:175] '
        '%s message\n')
    expected_logs = format_string % message
    if include_stacktrace:
      expected_logs += 'Stack trace:\n'
    faulthandler_start = 'Fatal Python error: Aborted'
    testcase.assertIn(faulthandler_start, logs)
    log_message = logs.split(faulthandler_start)[0]
    testcase.assertEqual(_munge_log(expected_logs), _munge_log(log_message))

  return assert_logs


def _munge_log(buf):
  """Remove timestamps, thread ids, filenames and line numbers from logs."""

  # Remove all messages produced before the output to be tested.
  buf = re.sub(r'(?:.|\n)*START OF TEST HELPER LOGS: IGNORE PREVIOUS.\n',
               r'',
               buf)

  # Greeting
  buf = re.sub(r'(?m)^Log file created at: .*\n',
               '',
               buf)
  buf = re.sub(r'(?m)^Running on machine: .*\n',
               '',
               buf)
  buf = re.sub(r'(?m)^Binary: .*\n',
               '',
               buf)
  buf = re.sub(r'(?m)^Log line format: .*\n',
               '',
               buf)

  # Verify thread id is logged as a non-negative quantity.
  matched = re.match(r'(?m)^(\w)(\d\d\d\d \d\d:\d\d:\d\d\.\d\d\d\d\d\d) '
                     r'([ ]*-?[0-9a-fA-f]+ )?([a-zA-Z<][\w._<>-]+):(\d+)',
                     buf)
  if matched:
    threadid = matched.group(3)
    if int(threadid) < 0:
      raise AssertionError("Negative threadid '%s' in '%s'" % (threadid, buf))

  # Timestamp
  buf = re.sub(r'(?m)' + logging.ABSL_LOGGING_PREFIX_REGEX,
               r'\g<severity>0000 00:00:00.000000 12345 \g<filename>:123',
               buf)

  # Traceback
  buf = re.sub(r'(?m)^  File "(.*/)?([^"/]+)", line (\d+),',
               r'  File "\g<2>", line 456,',
               buf)

  # Stack trace is too complicated for re, just assume it extends to end of
  # output
  buf = re.sub(r'(?sm)^Stack trace:\n.*',
               r'Stack trace:\n',
               buf)
  buf = re.sub(r'(?sm)^\*\*\* Signal 6 received by PID.*\n.*',
               r'Stack trace:\n',
               buf)
  buf = re.sub((r'(?sm)^\*\*\* ([A-Z]+) received by PID (\d+) '
                r'\(TID 0x([0-9a-f]+)\)'
                r'( from PID \d+)?; stack trace: \*\*\*\n.*'),
               r'Stack trace:\n',
               buf)
  buf = re.sub(r'(?sm)^\*\*\* Check failure stack trace: \*\*\*\n.*',
               r'Stack trace:\n',
               buf)

  if os.name == 'nt':
    # On windows, we calls Python interpreter explicitly, so the file names
    # include the full path. Strip them.
    buf = re.sub(r'(  File ").*(logging_functional_test_helper\.py", line )',
                 r'\1\2',
                 buf)

  return buf


def _verify_status(expected, actual, output):
  if expected != actual:
    raise AssertionError(