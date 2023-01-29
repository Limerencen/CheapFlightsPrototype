
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

"""A Python test reporter that generates test reports in JUnit XML format."""

import datetime
import re
import sys
import threading
import time
import traceback
import unittest
from xml.sax import saxutils
from absl.testing import _pretty_print_reporter


# See http://www.w3.org/TR/REC-xml/#NT-Char
_bad_control_character_codes = set(range(0, 0x20)) - {0x9, 0xA, 0xD}


_control_character_conversions = {
    chr(i): '\\x{:02x}'.format(i) for i in _bad_control_character_codes}


_escape_xml_attr_conversions = {
    '"': '&quot;',
    "'": '&apos;',
    '\n': '&#xA;',
    '\t': '&#x9;',
    '\r': '&#xD;',
    ' ': '&#x20;'}
_escape_xml_attr_conversions.update(_control_character_conversions)


# When class or module level function fails, unittest/suite.py adds a
# _ErrorHolder instance instead of a real TestCase, and it has a description
# like "setUpClass (__main__.MyTestCase)".
_CLASS_OR_MODULE_LEVEL_TEST_DESC_REGEX = re.compile(r'^(\w+) \((\S+)\)$')


# NOTE: while saxutils.quoteattr() theoretically does the same thing; it
# seems to often end up being too smart for it's own good not escaping properly.
# This function is much more reliable.
def _escape_xml_attr(content):
  """Escapes xml attributes."""
  # Note: saxutils doesn't escape the quotes.
  return saxutils.escape(content, _escape_xml_attr_conversions)


def _escape_cdata(s):
  """Escapes a string to be used as XML CDATA.

  CDATA characters are treated strictly as character data, not as XML markup,
  but there are still certain restrictions on them.

  Args:
    s: the string to be escaped.
  Returns:
    An escaped version of the input string.
  """
  for char, escaped in _control_character_conversions.items():
    s = s.replace(char, escaped)
  return s.replace(']]>', ']] >')


def _iso8601_timestamp(timestamp):
  """Produces an ISO8601 datetime.

  Args:
    timestamp: an Epoch based timestamp in seconds.

  Returns:
    A iso8601 format timestamp if the input is a valid timestamp, None otherwise
  """
  if timestamp is None or timestamp < 0:
    return None
  return datetime.datetime.fromtimestamp(
      timestamp, tz=datetime.timezone.utc).isoformat()


def _print_xml_element_header(element, attributes, stream, indentation=''):
  """Prints an XML header of an arbitrary element.

  Args:
    element: element name (testsuites, testsuite, testcase)
    attributes: 2-tuple list with (attributes, values) already escaped
    stream: output stream to write test report XML to
    indentation: indentation added to the element header
  """
  stream.write('%s<%s' % (indentation, element))
  for attribute in attributes:
    if (len(attribute) == 2 and attribute[0] is not None and
        attribute[1] is not None):
      stream.write(' %s="%s"' % (attribute[0], attribute[1]))
  stream.write('>\n')

# Copy time.time which ensures the real time is used internally.
# This prevents bad interactions with tests that stub out time.
_time_copy = time.time

if hasattr(traceback, '_some_str'):
  # Use the traceback module str function to format safely.
  _safe_str = traceback._some_str
else:
  _safe_str = str  # pylint: disable=invalid-name


class _TestCaseResult(object):
  """Private helper for _TextAndXMLTestResult that represents a test result.

  Attributes:
    test: A TestCase instance of an individual test method.
    name: The name of the individual test method.
    full_class_name: The full name of the test class.
    run_time: The duration (in seconds) it took to run the test.
    start_time: Epoch relative timestamp of when test started (in seconds)
    errors: A list of error 4-tuples. Error tuple entries are
        1) a string identifier of either "failure" or "error"
        2) an exception_type
        3) an exception_message
        4) a string version of a sys.exc_info()-style tuple of values
           ('error', err[0], err[1], self._exc_info_to_string(err))
           If the length of errors is 0, then the test is either passed or
           skipped.
    skip_reason: A string explaining why the test was skipped.
  """

  def __init__(self, test):
    self.run_time = -1
    self.start_time = -1
    self.skip_reason = None
    self.errors = []
    self.test = test

    # Parse the test id to get its test name and full class path.
    # Unfortunately there is no better way of knowning the test and class.
    # Worse, unittest uses _ErrorHandler instances to represent class / module
    # level failures.
    test_desc = test.id() or str(test)
    # Check if it's something like "setUpClass (__main__.TestCase)".
    match = _CLASS_OR_MODULE_LEVEL_TEST_DESC_REGEX.match(test_desc)
    if match:
      name = match.group(1)
      full_class_name = match.group(2)
    else:
      class_name = unittest.util.strclass(test.__class__)
      if isinstance(test, unittest.case._SubTest):
        # If the test case is a _SubTest, the real TestCase instance is
        # available as _SubTest.test_case.
        class_name = unittest.util.strclass(test.test_case.__class__)
      if test_desc.startswith(class_name + '.'):
        # In a typical unittest.TestCase scenario, test.id() returns with
        # a class name formatted using unittest.util.strclass.
        name = test_desc[len(class_name)+1:]
        full_class_name = class_name
      else:
        # Otherwise make a best effort to guess the test name and full class
        # path.
        parts = test_desc.rsplit('.', 1)
        name = parts[-1]
        full_class_name = parts[0] if len(parts) == 2 else ''
    self.name = _escape_xml_attr(name)
    self.full_class_name = _escape_xml_attr(full_class_name)

  def set_run_time(self, time_in_secs):
    self.run_time = time_in_secs

  def set_start_time(self, time_in_secs):
    self.start_time = time_in_secs

  def print_xml_summary(self, stream):
    """Prints an XML Summary of a TestCase.

    Status and result are populated as per JUnit XML test result reporter.
    A test that has been skipped will always have a skip reason,
    as every skip method in Python's unittest requires the reason arg to be
    passed.

    Args:
      stream: output stream to write test report XML to
    """

    if self.skip_reason is None:
      status = 'run'
      result = 'completed'
    else:
      status = 'notrun'
      result = 'suppressed'

    test_case_attributes = [
        ('name', '%s' % self.name),
        ('status', '%s' % status),
        ('result', '%s' % result),
        ('time', '%.3f' % self.run_time),
        ('classname', self.full_class_name),
        ('timestamp', _iso8601_timestamp(self.start_time)),
    ]
    _print_xml_element_header('testcase', test_case_attributes, stream, '  ')
    self._print_testcase_details(stream)
    stream.write('  </testcase>\n')

  def _print_testcase_details(self, stream):
    for error in self.errors:
      outcome, exception_type, message, error_msg = error  # pylint: disable=unpacking-non-sequence
      message = _escape_xml_attr(_safe_str(message))
      exception_type = _escape_xml_attr(str(exception_type))
      error_msg = _escape_cdata(error_msg)
      stream.write('  <%s message="%s" type="%s"><![CDATA[%s]]></%s>\n'
                   % (outcome, message, exception_type, error_msg, outcome))


class _TestSuiteResult(object):
  """Private helper for _TextAndXMLTestResult."""

  def __init__(self):
    self.suites = {}
    self.failure_counts = {}
    self.error_counts = {}
    self.overall_start_time = -1
    self.overall_end_time = -1
    self._testsuites_properties = {}

  def add_test_case_result(self, test_case_result):