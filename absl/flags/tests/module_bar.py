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

"""Auxiliary module for testing flags.py.

The purpose of this module is to define a few flags.  We want to make
sure the unit tests for flags.py involve more than one module.
"""

from absl import flags
from absl.flags import _helpers

FLAGS = flags.FLAGS


def define_flags(flag_values=FLAGS):
  """Defines some flags.

  Args:
    flag_values: The FlagValues object we want to register the flags
      with.
  """
  # The 'tmod_bar_' prefix (short for 'test_module_bar') ensures there
  # is no name clash with the existing flags.
  flags.DEFINE_boolean('tmod_bar_x', True, 'Boolean flag.',
                       flag_values=flag_values)
  flags.DEFINE_string('tmod_bar_y', 'default', 'String flag.',
                      flag_values=flag_values)
  flags.DEFINE_boolean('tmod_bar_z', False,
                       'Another boolean flag from module bar.',
                       flag_values=flag_values)
  flags.DEFINE_integer('tmod_bar_t', 4, 'Sample int flag.',
                       flag_values=flag_values)
  flags.DEFINE_integer('tmod_bar_u', 5, 'Sample int flag.',
                       flag_values=flag_values)
  flags.DEFINE_integer('tmod_bar_v', 6, 'Sample int flag.',
                       flag_values=flag_values)


def remove_one_flag(flag_name, flag_values=FLAGS):
  """Removes the definition of one flag from flags.FLAGS.

  Note: if the flag is not defined in flags.FLAGS, this function does
  not do anything (in particular, it does not raise any exception).

  Motivation: We use this function for cleanup *after* a test: if
  there was a failure during a test and not all flags were declared,
  we do not want the cleanup code to crash.

  Args:
    flag_name: A string, the name of the flag to delete.
    flag_values: The FlagValues object we remove the flag from.
  """
  if flag_name in flag_values:
    flag_values.__delattr__(flag_name)


def names_of_d