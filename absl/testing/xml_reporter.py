
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

