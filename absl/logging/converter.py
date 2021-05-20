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

"""Module to convert log levels between Abseil Python, C++, and Python standard.

This converter has to convert (best effort) between three different
logging level schemes:

  * **cpp**: The C++ logging level scheme used in Abseil C++.
  * **absl**: The absl.logging level scheme used in Abseil Python.
  * **standard**: The python standard library logging level scheme.

Here is a handy ascii chart for easy mental mapping::

    LEVEL    | cpp |  absl  | standard |
    ---------+-----+--------+----------+
    DEBUG    |  0  |    1   |    10    |
    INFO     |  0  |    0   |    20    |
    WARNING  |  1  |   -1   |    30    |
    ERROR    |  2  |   -2   |    40    |
    CRITICAL |  3  |   -3   |    50    |
    FATAL    |  3  |   -3   |    50    |

Note: standard logging ``CRITICAL`` is mapped to absl/cpp ``FATAL``.
However, only ``CRITICAL`` logs from the absl logger (or absl.logging.fatal)
will terminate the program. ``CRITICAL`` logs from non-absl loggers are treated
as error logs with a message prefix ``"CRITICAL - "``.

Converting from standard to absl or cpp is a lossy conversion.
Converting back to standard will lose granularity.  For this reason,
users should always try to convert to standard, the richest
representation, before manipulating the levels, and then only to cpp
or absl if those level schemes are absolutely necessary.
"""

import logging

STANDARD_CRITICAL = logging.CRITICAL
STANDARD_ERROR = logging.ERROR
STANDARD_WARNING = logging.WARNING
STANDARD_INFO = logging.INFO
STANDARD_DEBUG = logging.DEBUG

# These levels are also used to define the constants
# FATAL, ERROR, WARNING, INFO, and DEBUG in the
# absl.logging module.
ABSL_FATAL = -3
ABSL_ERROR = -2
ABSL_WARNING = -1
ABSL_WARN = -1  # Deprecated name.
ABSL_INFO = 0
ABSL_DEBUG = 1

ABSL_LEVELS = {ABSL_FATAL: 'FATAL',
               ABSL_ERROR: 'ERROR',
               ABSL_WARNING: 'WARNING',
             