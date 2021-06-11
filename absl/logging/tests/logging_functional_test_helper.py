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

"""Helper script for logging_functional_test."""

import logging as std_logging
import logging.config as std_logging_config
import os
import sys
import threading
import time
import timeit
from unittest import mock

from absl import app
from absl import flags
from absl import logging

FLAGS = flags.FLAGS


class VerboseDel(object):
  """Dummy class to test __del__ running."""

  def __init__(self, msg):
    self._msg = msg

  def __del__(self):
    sys.stderr.write(self._msg)
    sys.stderr.flush()


def _test_do_logging():
  """Do some log operations."""
  logging.vlog(3, 'This line is VLOG level 3')
  logging.vlog(2, 'This line is VLOG level 2')
  logging.log(2, 'This line is log level 2')
  if logging.vlog_is_on(2):
    logging.log(1, 'VLOG level 1, but only if VLOG level 2 is active')

  logging.vlog(1, 'This line is VLOG level 1')
  logging.log(1, 'This line is log level 1')
  logging.debug('This line is DEBUG')

  logging.vlog(0, 'This line is VLOG level 0')
  logging.log(0, 'This line is log level 0')
  logging.info('Interesting Stuff\0')
  logging.info('Interesting Stuff with Arguments: %d', 42)
  logging.info('%(a)s Stuff with %(b)s',
               {'a': 'Interesting', 'b': 'Dictionary'})

  with mock.patch.object(timeit, 'default_timer') as mock_timer:
    mock_timer.return_value = 0
    while timeit.default_timer() < 9:
      logging.log_every_n_seconds(logging.INFO, 'This should appear 5 times.',
                                  2)
      mock_timer.return_value = mock_timer() + .2

  for i in range(1, 5):
    logging.log_first_n(logging.INFO, 'Info first %d of %d', 