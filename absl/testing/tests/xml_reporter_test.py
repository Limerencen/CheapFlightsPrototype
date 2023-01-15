
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

import datetime
import io
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
from xml.etree import ElementTree
from xml.parsers import expat

from absl import logging
from absl.testing import _bazelize_command
from absl.testing import absltest
from absl.testing import parameterized
from absl.testing import xml_reporter


class StringIOWriteLn(io.StringIO):

  def writeln(self, line):
    self.write(line + '\n')


class MockTest(absltest.TestCase):
  failureException = AssertionError

  def __init__(self, name):
    super(MockTest, self).__init__()
    self.name = name

  def id(self):
    return self.name

  def runTest(self):
    return

  def shortDescription(self):
    return "This is this test's description."


# str(exception_type) is different between Python 2 and 3.
def xml_escaped_exception_type(exception_type):
  return xml_reporter._escape_xml_attr(str(exception_type))


OUTPUT_STRING = '\n'.join([
    r'<\?xml version="1.0"\?>',
    ('<testsuites name="" tests="%(tests)d" failures="%(failures)d"'
     ' errors="%(errors)d" time="%(run_time).3f" timestamp="%(start_time)s">'),
    ('<testsuite name="%(suite_name)s" tests="%(tests)d"'
     ' failures="%(failures)d" errors="%(errors)d" time="%(run_time).3f"'
     ' timestamp="%(start_time)s">'),
    ('  <testcase name="%(test_name)s" status="%(status)s" result="%(result)s"'
     ' time="%(run_time).3f" classname="%(classname)s"'
     ' timestamp="%(start_time)s">%(message)s'),
    '  </testcase>', '</testsuite>',
    '</testsuites>',
])

FAILURE_MESSAGE = r"""
  <failure message="e" type="{}"><!\[CDATA\[Traceback \(most recent call last\):
  File ".*xml_reporter_test\.py", line \d+, in get_sample_failure
    self.fail\(\'e\'\)
AssertionError: e
\]\]></failure>""".format(xml_escaped_exception_type(AssertionError))

ERROR_MESSAGE = r"""
  <error message="invalid&#x20;literal&#x20;for&#x20;int\(\)&#x20;with&#x20;base&#x20;10:&#x20;(&apos;)?a(&apos;)?" type="{}"><!\[CDATA\[Traceback \(most recent call last\):
  File ".*xml_reporter_test\.py", line \d+, in get_sample_error
    int\('a'\)
ValueError: invalid literal for int\(\) with base 10: '?a'?
\]\]></error>""".format(xml_escaped_exception_type(ValueError))

UNICODE_MESSAGE = r"""
  <%s message="{0}" type="{1}"><!\[CDATA\[Traceback \(most recent call last\):
  File ".*xml_reporter_test\.py", line \d+, in get_unicode_sample_failure
    raise AssertionError\(u'\\xe9'\)
AssertionError: {0}
\]\]></%s>""".format(
        r'\xe9',
        xml_escaped_exception_type(AssertionError))

NEWLINE_MESSAGE = r"""
  <%s message="{0}" type="{1}"><!\[CDATA\[Traceback \(most recent call last\):
  File ".*xml_reporter_test\.py", line \d+, in get_newline_message_sample_failure
    raise AssertionError\(\'{2}'\)
AssertionError: {3}
\]\]></%s>""".format(
    'new&#xA;line',
    xml_escaped_exception_type(AssertionError),
    r'new\\nline',
    'new\nline')

UNEXPECTED_SUCCESS_MESSAGE = '\n'.join([
    '',
    (r'  <error message="" type=""><!\[CDATA\[Test case '
     r'__main__.MockTest.unexpectedly_passing_test should have failed, '
     r'but passed.\]\]></error>'),
])

UNICODE_ERROR_MESSAGE = UNICODE_MESSAGE % ('error', 'error')
NEWLINE_ERROR_MESSAGE = NEWLINE_MESSAGE % ('error', 'error')


class TextAndXMLTestResultTest(absltest.TestCase):

  def setUp(self):
    super().setUp()
    self.stream = StringIOWriteLn()
    self.xml_stream = io.StringIO()

  def _make_result(self, times):
    timer = mock.Mock()
    timer.side_effect = times
    return xml_reporter._TextAndXMLTestResult(self.xml_stream, self.stream,
                                              'foo', 0, timer)

  def _assert_match(self, regex, output):
    fail_msg = 'Expected regex:\n{}\nTo match:\n{}'.format(regex, output)
    self.assertRegex(output, regex, fail_msg)

  def _assert_valid_xml(self, xml_output):
    try:
      expat.ParserCreate().Parse(xml_output)
    except expat.ExpatError as e:
      raise AssertionError('Bad XML output: {}\n{}'.format(e, xml_output))

  def _simulate_error_test(self, test, result):
    result.startTest(test)
    result.addError(test, self.get_sample_error())
    result.stopTest(test)

  def _simulate_failing_test(self, test, result):
    result.startTest(test)
    result.addFailure(test, self.get_sample_failure())
    result.stopTest(test)

  def _simulate_passing_test(self, test, result):
    result.startTest(test)
    result.addSuccess(test)
    result.stopTest(test)

  def _iso_timestamp(self, timestamp):
    return datetime.datetime.utcfromtimestamp(timestamp).isoformat() + '+00:00'

  def test_with_passing_test(self):
    start_time = 0
    end_time = 2
    result = self._make_result((start_time, start_time, end_time, end_time))

    test = MockTest('__main__.MockTest.passing_test')
    result.startTestRun()
    result.startTest(test)
    result.addSuccess(test)
    result.stopTest(test)
    result.stopTestRun()
    result.printErrors()

    run_time = end_time - start_time
    expected_re = OUTPUT_STRING % {
        'suite_name': 'MockTest',
        'tests': 1,
        'failures': 0,
        'errors': 0,
        'run_time': run_time,
        'start_time': re.escape(self._iso_timestamp(start_time),),
        'test_name': 'passing_test',
        'classname': '__main__.MockTest',
        'status': 'run',
        'result': 'completed',
        'attributes': '',
        'message': ''
    }
    self._assert_match(expected_re, self.xml_stream.getvalue())

  def test_with_passing_subtest(self):
    start_time = 0
    end_time = 2
    result = self._make_result((start_time, start_time, end_time, end_time))

    test = MockTest('__main__.MockTest.passing_test')
    subtest = unittest.case._SubTest(test, 'msg', None)
    result.startTestRun()
    result.startTest(test)
    result.addSubTest(test, subtest, None)
    result.stopTestRun()
    result.printErrors()
