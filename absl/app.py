
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

"""Generic entry point for Abseil Python applications.

To use this module, define a ``main`` function with a single ``argv`` argument
and call ``app.run(main)``. For example::

    def main(argv):
      if len(argv) > 1:
        raise app.UsageError('Too many command-line arguments.')

    if __name__ == '__main__':
      app.run(main)
"""

import collections
import errno
import os
import pdb
import sys
import textwrap
import traceback

from absl import command_name
from absl import flags
from absl import logging

try:
  import faulthandler
except ImportError:
  faulthandler = None

FLAGS = flags.FLAGS

flags.DEFINE_boolean('run_with_pdb', False, 'Set to true for PDB debug mode')
flags.DEFINE_boolean('pdb_post_mortem', False,
                     'Set to true to handle uncaught exceptions with PDB '
                     'post mortem.')
flags.DEFINE_alias('pdb', 'pdb_post_mortem')
flags.DEFINE_boolean('run_with_profiling', False,
                     'Set to true for profiling the script. '
                     'Execution will be slower, and the output format might '
                     'change over time.')
flags.DEFINE_string('profile_file', None,
                    'Dump profile information to a file (for python -m '
                    'pstats). Implies --run_with_profiling.')
flags.DEFINE_boolean('use_cprofile_for_profiling', True,
                     'Use cProfile instead of the profile module for '
                     'profiling. This has no effect unless '
                     '--run_with_profiling is set.')
flags.DEFINE_boolean('only_check_args', False,
                     'Set to true to validate args and exit.',
                     allow_hide_cpp=True)


# If main() exits via an abnormal exception, call into these
# handlers before exiting.
EXCEPTION_HANDLERS = []


class Error(Exception):
  pass


class UsageError(Error):
  """Exception raised when the arguments supplied by the user are invalid.

  Raise this when the arguments supplied are invalid from the point of
  view of the application. For example when two mutually exclusive
  flags have been supplied or when there are not enough non-flag
  arguments. It is distinct from flags.Error which covers the lower
  level of parsing and validating individual flags.
  """

  def __init__(self, message, exitcode=1):
    super(UsageError, self).__init__(message)
    self.exitcode = exitcode


class HelpFlag(flags.BooleanFlag):
  """Special boolean flag that displays usage and raises SystemExit."""
  NAME = 'help'
  SHORT_NAME = '?'

  def __init__(self):
    super(HelpFlag, self).__init__(
        self.NAME, False, 'show this help',
        short_name=self.SHORT_NAME, allow_hide_cpp=True)

  def parse(self, arg):
    if self._parse(arg):
      usage(shorthelp=True, writeto_stdout=True)
      # Advertise --helpfull on stdout, since usage() was on stdout.
      print()
      print('Try --helpfull to get a list of all flags.')
      sys.exit(1)


class HelpshortFlag(HelpFlag):
  """--helpshort is an alias for --help."""
  NAME = 'helpshort'
  SHORT_NAME = None


class HelpfullFlag(flags.BooleanFlag):
  """Display help for flags in the main module and all dependent modules."""

  def __init__(self):
    super(HelpfullFlag, self).__init__(
        'helpfull', False, 'show full help', allow_hide_cpp=True)

  def parse(self, arg):
    if self._parse(arg):
      usage(writeto_stdout=True)
      sys.exit(1)


class HelpXMLFlag(flags.BooleanFlag):
  """Similar to HelpfullFlag, but generates output in XML format."""

  def __init__(self):
    super(HelpXMLFlag, self).__init__(
        'helpxml', False, 'like --helpfull, but generates XML output',
        allow_hide_cpp=True)

  def parse(self, arg):
    if self._parse(arg):
      flags.FLAGS.write_help_in_xml_format(sys.stdout)
      sys.exit(1)


def parse_flags_with_usage(args):
  """Tries to parse the flags, print usage, and exit if unparsable.

  Args:
    args: [str], a non-empty list of the command line arguments including
        program name.

  Returns:
    [str], a non-empty list of remaining command line arguments after parsing
    flags, including program name.
  """
  try:
    return FLAGS(args)
  except flags.Error as error:
    message = str(error)
    if '\n' in message:
      final_message = 'FATAL Flags parsing error:\n%s\n' % textwrap.indent(
          message, '  ')
    else:
      final_message = 'FATAL Flags parsing error: %s\n' % message
    sys.stderr.write(final_message)
    sys.stderr.write('Pass --helpshort or --helpfull to see help on flags.\n')
    sys.exit(1)


_define_help_flags_called = False


def define_help_flags():
  """Registers help flags. Idempotent."""
  # Use a global to ensure idempotence.
  global _define_help_flags_called

  if not _define_help_flags_called:
    flags.DEFINE_flag(HelpFlag())
    flags.DEFINE_flag(HelpshortFlag())  # alias for --help
    flags.DEFINE_flag(HelpfullFlag())
    flags.DEFINE_flag(HelpXMLFlag())
    _define_help_flags_called = True


def _register_and_parse_flags_with_usage(
    argv=None,
    flags_parser=parse_flags_with_usage,
):
  """Registers help flags, parses arguments and shows usage if appropriate.

  This also calls sys.exit(0) if flag --only_check_args is True.

  Args:
    argv: [str], a non-empty list of the command line arguments including
        program name, sys.argv is used if None.
    flags_parser: Callable[[List[Text]], Any], the function used to parse flags.
        The return value of this function is passed to `main` untouched.
        It must guarantee FLAGS is parsed after this function is called.

  Returns:
    The return value of `flags_parser`. When using the default `flags_parser`,
    it returns the following:
    [str], a non-empty list of remaining command line arguments after parsing
    flags, including program name.

  Raises:
    Error: Raised when flags_parser is called, but FLAGS is not parsed.
    SystemError: Raised when it's called more than once.
  """
  if _register_and_parse_flags_with_usage.done:
    raise SystemError('Flag registration can be done only once.')

  define_help_flags()

  original_argv = sys.argv if argv is None else argv
  args_to_main = flags_parser(original_argv)
  if not FLAGS.is_parsed():
    raise Error('FLAGS must be parsed after flags_parser is called.')

  # Exit when told so.
  if FLAGS.only_check_args:
    sys.exit(0)
  # Immediately after flags are parsed, bump verbosity to INFO if the flag has
  # not been set.
  if FLAGS['verbosity'].using_default_value:
    FLAGS.verbosity = 0
  _register_and_parse_flags_with_usage.done = True

  return args_to_main

_register_and_parse_flags_with_usage.done = False


def _run_main(main, argv):
  """Calls main, optionally with pdb or profiler."""
  if FLAGS.run_with_pdb:
    sys.exit(pdb.runcall(main, argv))
  elif FLAGS.run_with_profiling or FLAGS.profile_file:
    # Avoid import overhead since most apps (including performance-sensitive
    # ones) won't be run with profiling.