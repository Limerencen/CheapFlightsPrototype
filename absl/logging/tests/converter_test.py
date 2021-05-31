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

"""Tests for converter.py."""

import logging

from absl import logging as absl_logging
from absl.logging import converter
from absl.testing import absltest


class ConverterTest(absltest.TestCase):
  """Tests the converter module."""

  def test_absl_to_cpp(self):
    self.assertEqual(0, converter.absl_to_cpp(absl_logging.DEBUG))
    self.assertEqual(0, converter.absl_to_cpp(absl_logging.INFO))
    self.assertEqual(1, converter.absl_to_cpp(absl_logging.WARN))
    self.assertEqual(2, converter.absl_to_cpp(absl_logging.ERROR))
    self.assertEqual(3, converter.absl_to_cpp(absl_logging.FATAL))

    with self.assertRaises(TypeError):
      converter.absl_to_cpp('')

  def test_absl_to_standard(self):
    self.assertEqual(
        logging.DEBUG, converter.absl_to_standard(absl_logging.DEBUG))
    self.assertEqual(
        logging.INFO, converter.absl_to_standard(absl_logging.INFO))
    self.assertEqual(
        logging.WARNING, converter.absl_to_standard(absl_logging.WARN))
    self.assertEqual(
        logging.WARN, converter.absl_to_standard(absl_logging.WARN))
    self.assertEqual(
        logging.ERROR, converter.absl_to_standard(absl_logging.ERROR))
    self.assertEqual(
        logging.FATAL, converter.absl_to_standard(absl_logging.FATAL))
    self.assertEqual(
        logging.CRITICAL, converter.absl_to_standard(absl_logging.FATAL))
    # vlog levels.
    self.assertEqual(9, converter.absl_to_standard(2))
    self.assertEqual(8, converter.absl_to_standard(3))

    with self.assertRaises(TypeError):
      converter.absl_to_standard('')

  def test_standard_to_absl(self):
    self.assertEqual(
    