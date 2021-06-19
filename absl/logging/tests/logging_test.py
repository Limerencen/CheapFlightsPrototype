
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

"""Unit tests for absl.logging."""

import contextlib
import functools
import getpass
import io
import logging as std_logging
import os
import re
import socket
import sys
import tempfile
import threading
import time
import traceback
import unittest
from unittest import mock

from absl import flags
from absl import logging
from absl.testing import absltest
from absl.testing import flagsaver
from absl.testing import parameterized

FLAGS = flags.FLAGS


class ConfigurationTest(absltest.TestCase):
  """Tests the initial logging configuration."""

  def test_logger_and_handler(self):
    absl_logger = std_logging.getLogger('absl')
    self.assertIs(absl_logger, logging.get_absl_logger())
    self.assertIsInstance(absl_logger, logging.ABSLLogger)
    self.assertIsInstance(
        logging.get_absl_handler().python_handler.formatter,
        logging.PythonFormatter)


class LoggerLevelsTest(parameterized.TestCase):

  def setUp(self):
    super(LoggerLevelsTest, self).setUp()
    # Since these tests muck with the flag, always save/restore in case the
    # tests forget to clean up properly.
    # enter_context() is py3-only, but manually enter/exit should suffice.
    cm = self.set_logger_levels({})
    cm.__enter__()
    self.addCleanup(lambda: cm.__exit__(None, None, None))

  @contextlib.contextmanager
  def set_logger_levels(self, levels):
    original_levels = {
        name: std_logging.getLogger(name).level for name in levels
    }

    try:
      with flagsaver.flagsaver(logger_levels=levels):
        yield
    finally:
      for name, level in original_levels.items():
        std_logging.getLogger(name).setLevel(level)

  def assert_logger_level(self, name, expected_level):
    logger = std_logging.getLogger(name)
    self.assertEqual(logger.level, expected_level)

  def assert_logged(self, logger_name, expected_msgs):
    logger = std_logging.getLogger(logger_name)
    # NOTE: assertLogs() sets the logger to INFO if not specified.
    with self.assertLogs(logger, logger.level) as cm:
      logger.debug('debug')
      logger.info('info')
      logger.warning('warning')
      logger.error('error')
      logger.critical('critical')

    actual = {r.getMessage() for r in cm.records}
    self.assertEqual(set(expected_msgs), actual)

  def test_setting_levels(self):
    # Other tests change the root logging level, so we can't
    # assume it's the default.
    orig_root_level = std_logging.root.getEffectiveLevel()
    with self.set_logger_levels({'foo': 'ERROR', 'bar': 'DEBUG'}):

      self.assert_logger_level('foo', std_logging.ERROR)
      self.assert_logger_level('bar', std_logging.DEBUG)
      self.assert_logger_level('', orig_root_level)

      self.assert_logged('foo', {'error', 'critical'})
      self.assert_logged('bar',
                         {'debug', 'info', 'warning', 'error', 'critical'})

  @parameterized.named_parameters(
      ('empty', ''),
      ('one_value', 'one:INFO'),
      ('two_values', 'one.a:INFO,two.b:ERROR'),
      ('whitespace_ignored', ' one : DEBUG , two : INFO'),
  )
  def test_serialize_parse(self, levels_str):
    fl = FLAGS['logger_levels']
    fl.parse(levels_str)
    expected = levels_str.replace(' ', '')
    actual = fl.serialize()
    self.assertEqual('--logger_levels={}'.format(expected), actual)

  def test_invalid_value(self):
    with self.assertRaisesRegex(ValueError, 'Unknown level.*10'):
      FLAGS['logger_levels'].parse('foo:10')


class PythonHandlerTest(absltest.TestCase):
  """Tests the PythonHandler class."""

  def setUp(self):
    super().setUp()
    (year, month, day, hour, minute, sec,
     dunno, dayofyear, dst_flag) = (1979, 10, 21, 18, 17, 16, 3, 15, 0)
    self.now_tuple = (year, month, day, hour, minute, sec,
                      dunno, dayofyear, dst_flag)
    self.python_handler = logging.PythonHandler()

  def tearDown(self):
    mock.patch.stopall()
    super().tearDown()

  @flagsaver.flagsaver(logtostderr=False)
  def test_set_google_log_file_no_log_to_stderr(self):
    with mock.patch.object(self.python_handler, 'start_logging_to_file'):
      self.python_handler.use_absl_log_file()
      self.python_handler.start_logging_to_file.assert_called_once_with(
          program_name=None, log_dir=None)

  @flagsaver.flagsaver(logtostderr=True)
  def test_set_google_log_file_with_log_to_stderr(self):
    self.python_handler.stream = None
    self.python_handler.use_absl_log_file()
    self.assertEqual(sys.stderr, self.python_handler.stream)

  @mock.patch.object(logging, 'find_log_dir_and_names')
  @mock.patch.object(logging.time, 'localtime')
  @mock.patch.object(logging.time, 'time')
  @mock.patch.object(os.path, 'islink')
  @mock.patch.object(os, 'unlink')
  @mock.patch.object(os, 'getpid')
  def test_start_logging_to_file(
      self, mock_getpid, mock_unlink, mock_islink, mock_time,
      mock_localtime, mock_find_log_dir_and_names):
    mock_find_log_dir_and_names.return_value = ('here', 'prog1', 'prog1')
    mock_time.return_value = '12345'
    mock_localtime.return_value = self.now_tuple
    mock_getpid.return_value = 4321
    symlink = os.path.join('here', 'prog1.INFO')
    mock_islink.return_value = True
    with mock.patch.object(
        logging, 'open', return_value=sys.stdout, create=True):
      if getattr(os, 'symlink', None):
        with mock.patch.object(os, 'symlink'):
          self.python_handler.start_logging_to_file()
          mock_unlink.assert_called_once_with(symlink)
          os.symlink.assert_called_once_with(
              'prog1.INFO.19791021-181716.4321', symlink)
      else:
        self.python_handler.start_logging_to_file()

  def test_log_file(self):
    handler = logging.PythonHandler()
    self.assertEqual(sys.stderr, handler.stream)

    stream = mock.Mock()
    handler = logging.PythonHandler(stream)
    self.assertEqual(stream, handler.stream)

  def test_flush(self):
    stream = mock.Mock()
    handler = logging.PythonHandler(stream)
    handler.flush()
    stream.flush.assert_called_once()

  def test_flush_with_value_error(self):
    stream = mock.Mock()
    stream.flush.side_effect = ValueError