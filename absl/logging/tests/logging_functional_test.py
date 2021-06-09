
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
        'Test exited with unexpected status code %d (expected %d). '
        'Output was:\n%s' % (actual, expected, output))


def _verify_ok(status, output):
  """Check that helper exited with no errors."""
  _verify_status(0, status, output)


def _verify_fatal(status, output):
  """Check that helper died as expected."""
  # os.abort generates a SIGABRT signal (-6). On Windows, the process
  # immediately returns an exit code of 3.
  # See https://docs.python.org/3.6/library/os.html#os.abort.
  expected_exit_code = 3 if os.name == 'nt' else -6
  _verify_status(expected_exit_code, status, output)


def _verify_assert(status, output):
  """.Check that helper failed with assertion."""
  _verify_status(1, status, output)


class FunctionalTest(parameterized.TestCase):
  """Functional tests using the logging_functional_test_helper script."""

  def _get_helper(self):
    helper_name = 'absl/logging/tests/logging_functional_test_helper'
    return _bazelize_command.get_executable_path(helper_name)

  def _get_logs(self,
                verbosity,
                include_info_prefix=True):
    logs = []
    if verbosity >= 3:
      logs.append(_PY_VLOG3_LOG_MESSAGE)
    if verbosity >= 2:
      logs.append(_PY_VLOG2_LOG_MESSAGE)
    if verbosity >= logging.DEBUG:
      logs.append(_PY_DEBUG_LOG_MESSAGE)

    if verbosity >= logging.INFO:
      if include_info_prefix:
        logs.append(_PY_INFO_LOG_MESSAGE)
      else:
        logs.append(_PY_INFO_LOG_MESSAGE_NOPREFIX)
    if verbosity >= logging.WARN:
      logs.append(_PY_WARNING_LOG_MESSAGE)
    if verbosity >= logging.ERROR:
      logs.append(_PY_ERROR_LOG_MESSAGE)

    expected_logs = ''.join(logs)
    expected_logs = expected_logs.replace(
        "<type 'exceptions.OSError'>", "<class 'OSError'>")
    return expected_logs

  def setUp(self):
    super(FunctionalTest, self).setUp()
    self._log_dir = tempfile.mkdtemp(dir=absltest.TEST_TMPDIR.value)

  def tearDown(self):
    shutil.rmtree(self._log_dir)
    super(FunctionalTest, self).tearDown()

  def _exec_test(self,
                 verify_exit_fn,
                 expected_logs,
                 test_name='do_logging',
                 pass_logtostderr=False,
                 use_absl_log_file=False,
                 show_info_prefix=1,
                 call_dict_config=False,
                 extra_args=()):
    """Execute the helper script and verify its output.

    Args:
      verify_exit_fn: A function taking (status, output).
      expected_logs: List of tuples, or None if output shouldn't be checked.
          Tuple is (log prefix, log type, expected contents):
          - log prefix: A program name, or 'stderr'.
          - log type: 'INFO', 'ERROR', etc.
          - expected: Can be the following:
            - A string
            - A callable, called with the logs as a single argument
            - None, means don't check contents of log file
      test_name: Name to pass to helper.
      pass_logtostderr: Pass --logtostderr to the helper script if True.
      use_absl_log_file: If True, call
          logging.get_absl_handler().use_absl_log_file() before test_fn in
          logging_functional_test_helper.
      show_info_prefix: --showprefixforinfo value passed to the helper script.
      call_dict_config: True if helper script should call
          logging.config.dictConfig.
      extra_args: Iterable of str (optional, defaults to ()) - extra arguments
          to pass to the helper script.

    Raises:
      AssertionError: Assertion error when test fails.
    """
    args = ['--log_dir=%s' % self._log_dir]
    if pass_logtostderr:
      args.append('--logtostderr')
    if not show_info_prefix:
      args.append('--noshowprefixforinfo')
    args += extra_args

    # Execute helper in subprocess.
    env = os.environ.copy()
    env.update({
        'TEST_NAME': test_name,
        'USE_ABSL_LOG_FILE': '%d' % (use_absl_log_file,),
        'CALL_DICT_CONFIG': '%d' % (call_dict_config,),
    })
    cmd = [self._get_helper()] + args

    print('env: %s' % env, file=sys.stderr)
    print('cmd: %s' % cmd, file=sys.stderr)
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
        universal_newlines=True)
    output, _ = process.communicate()
    status = process.returncode

    # Verify exit status.
    verify_exit_fn(status, output)

    # Check outputs?
    if expected_logs is None:
      return

    # Get list of log files.
    logs = os.listdir(self._log_dir)
    logs = fnmatch.filter(logs, '*.log.*')
    logs.append('stderr')

    # Look for a log matching each expected pattern.
    matched = []
    unmatched = []
    unexpected = logs[:]
    for log_prefix, log_type, expected in expected_logs:
      # What pattern?
      if log_prefix == 'stderr':
        assert log_type is None
        pattern = 'stderr'
      else:
        pattern = r'%s[.].*[.]log[.]%s[.][\d.-]*$' % (log_prefix, log_type)

      # Is it there
      for basename in logs:
        if re.match(pattern, basename):
          matched.append([expected, basename])
          unexpected.remove(basename)
          break
      else:
        unmatched.append(pattern)

    # Mismatch?
    errors = ''
    if unmatched:
      errors += 'The following log files were expected but not found: %s' % (
          '\n '.join(unmatched))
    if unexpected:
      if errors:
        errors += '\n'
      errors += 'The following log files were not expected: %s' % (
          '\n '.join(unexpected))
    if errors:
      raise AssertionError(errors)

    # Compare contents of matches.
    for (expected, basename) in matched:
      if expected is None:
        continue

      if basename == 'stderr':
        actual = output
      else:
        path = os.path.join(self._log_dir, basename)
        with open(path, encoding='utf-8') as f:
          actual = f.read()

      if callable(expected):
        try:
          expected(actual)
        except AssertionError:
          print('expected_logs assertion failed, actual {} log:\n{}'.format(
              basename, actual), file=sys.stderr)
          raise
      elif isinstance(expected, str):
        self.assertMultiLineEqual(_munge_log(expected), _munge_log(actual),
                                  '%s differs' % basename)
      else:
        self.fail(
            'Invalid value found for expected logs: {}, type: {}'.format(
                expected, type(expected)))

  @parameterized.named_parameters(
      ('', False),
      ('logtostderr', True))
  def test_py_logging(self, logtostderr):
    # Python logging by default logs to stderr.
    self._exec_test(