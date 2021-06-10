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
  """