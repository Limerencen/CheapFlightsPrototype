
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

"""Base functionality for Abseil Python tests.

This module contains base classes and high-level functions for Abseil-style
tests.
"""

from collections import abc
import contextlib
import difflib
import enum
import errno
import getpass
import inspect
import io
import itertools
import json
import os
import random
import re
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock  # pylint: disable=unused-import Allow absltest.mock.
from urllib import parse

try:
  # The faulthandler module isn't always available, and pytype doesn't
  # understand that we're catching ImportError, so suppress the error.
  # pytype: disable=import-error
  import faulthandler
  # pytype: enable=import-error
except ImportError:
  # We use faulthandler if it is available.
  faulthandler = None

from absl import app
from absl import flags
from absl import logging
from absl.testing import _pretty_print_reporter
from absl.testing import xml_reporter

# Make typing an optional import to avoid it being a required dependency
# in Python 2. Type checkers will still understand the imports.
try:
  # pylint: disable=unused-import
  import typing
  from typing import Any, AnyStr, BinaryIO, Callable, ContextManager, IO, Iterator, List, Mapping, MutableMapping, MutableSequence, Optional, Sequence, Text, TextIO, Tuple, Type, Union
  # pylint: enable=unused-import
except ImportError:
  pass
else:
  # Use an if-type-checking block to prevent leakage of type-checking only
  # symbols. We don't want people relying on these at runtime.
  if typing.TYPE_CHECKING:
    # Unbounded TypeVar for general usage
    _T = typing.TypeVar('_T')

    import unittest.case
    _OutcomeType = unittest.case._Outcome  # pytype: disable=module-attr



# Re-export a bunch of unittest functions we support so that people don't
# have to import unittest to get them
# pylint: disable=invalid-name
skip = unittest.skip
skipIf = unittest.skipIf
skipUnless = unittest.skipUnless
SkipTest = unittest.SkipTest
expectedFailure = unittest.expectedFailure
# pylint: enable=invalid-name

# End unittest re-exports

FLAGS = flags.FLAGS

_TEXT_OR_BINARY_TYPES = (str, bytes)

# Suppress surplus entries in AssertionError stack traces.
__unittest = True  # pylint: disable=invalid-name


def expectedFailureIf(condition, reason):  # pylint: disable=invalid-name
  """Expects the test to fail if the run condition is True.

  Example usage::

      @expectedFailureIf(sys.version.major == 2, "Not yet working in py2")
      def test_foo(self):
        ...

  Args:
    condition: bool, whether to expect failure or not.
    reason: Text, the reason to expect failure.
  Returns:
    Decorator function
  """
  del reason  # Unused
  if condition:
    return unittest.expectedFailure
  else:
    return lambda f: f


class TempFileCleanup(enum.Enum):
  # Always cleanup temp files when the test completes.
  ALWAYS = 'always'
  # Only cleanup temp file if the test passes. This allows easier inspection
  # of tempfile contents on test failure. absltest.TEST_TMPDIR.value determines
  # where tempfiles are created.
  SUCCESS = 'success'
  # Never cleanup temp files.
  OFF = 'never'


# Many of the methods in this module have names like assertSameElements.
# This kind of name does not comply with PEP8 style,
# but it is consistent with the naming of methods in unittest.py.
# pylint: disable=invalid-name


def _get_default_test_random_seed():
  # type: () -> int
  random_seed = 301
  value = os.environ.get('TEST_RANDOM_SEED', '')
  try:
    random_seed = int(value)
  except ValueError:
    pass
  return random_seed


def get_default_test_srcdir():
  # type: () -> Text
  """Returns default test source dir."""
  return os.environ.get('TEST_SRCDIR', '')


def get_default_test_tmpdir():
  # type: () -> Text
  """Returns default test temp dir."""
  tmpdir = os.environ.get('TEST_TMPDIR', '')
  if not tmpdir:
    tmpdir = os.path.join(tempfile.gettempdir(), 'absl_testing')

  return tmpdir


def _get_default_randomize_ordering_seed():
  # type: () -> int
  """Returns default seed to use for randomizing test order.

  This function first checks the --test_randomize_ordering_seed flag, and then
  the TEST_RANDOMIZE_ORDERING_SEED environment variable. If the first value
  we find is:
    * (not set): disable test randomization
    * 0: disable test randomization
    * 'random': choose a random seed in [1, 4294967295] for test order
      randomization
    * positive integer: use this seed for test order randomization

  (The values used are patterned after
  https://docs.python.org/3/using/cmdline.html#envvar-PYTHONHASHSEED).

  In principle, it would be simpler to return None if no override is provided;
  however, the python random module has no `get_seed()`, only `getstate()`,
  which returns far more data than we want to pass via an environment variable
  or flag.

  Returns:
    A default value for test case randomization (int). 0 means do not randomize.

  Raises:
    ValueError: Raised when the flag or env value is not one of the options
        above.
  """
  if FLAGS['test_randomize_ordering_seed'].present:
    randomize = FLAGS.test_randomize_ordering_seed
  elif 'TEST_RANDOMIZE_ORDERING_SEED' in os.environ:
    randomize = os.environ['TEST_RANDOMIZE_ORDERING_SEED']
  else:
    randomize = ''
  if not randomize:
    return 0
  if randomize == 'random':
    return random.Random().randint(1, 4294967295)
  if randomize == '0':
    return 0
  try:
    seed = int(randomize)
    if seed > 0:
      return seed
  except ValueError:
    pass
  raise ValueError(
      'Unknown test randomization seed value: {}'.format(randomize))


TEST_SRCDIR = flags.DEFINE_string(
    'test_srcdir',
    get_default_test_srcdir(),
    'Root of directory tree where source files live',
    allow_override_cpp=True)
TEST_TMPDIR = flags.DEFINE_string(
    'test_tmpdir',
    get_default_test_tmpdir(),
    'Directory for temporary testing files',
    allow_override_cpp=True)

flags.DEFINE_integer(
    'test_random_seed',
    _get_default_test_random_seed(),
    'Random seed for testing. Some test frameworks may '
    'change the default value of this flag between runs, so '
    'it is not appropriate for seeding probabilistic tests.',
    allow_override_cpp=True)
flags.DEFINE_string(
    'test_randomize_ordering_seed',
    '',
    'If positive, use this as a seed to randomize the '
    'execution order for test cases. If "random", pick a '
    'random seed to use. If 0 or not set, do not randomize '
    'test case execution order. This flag also overrides '
    'the TEST_RANDOMIZE_ORDERING_SEED environment variable.',
    allow_override_cpp=True)
flags.DEFINE_string('xml_output_file', '', 'File to store XML test results')


# We might need to monkey-patch TestResult so that it stops considering an
# unexpected pass as a as a "successful result".  For details, see
# http://bugs.python.org/issue20165
def _monkey_patch_test_result_for_unexpected_passes():
  # type: () -> None
  """Workaround for <http://bugs.python.org/issue20165>."""

  def wasSuccessful(self):
    # type: () -> bool
    """Tells whether or not this result was a success.

    Any unexpected pass is to be counted as a non-success.

    Args:
      self: The TestResult instance.

    Returns:
      Whether or not this result was a success.
    """
    return (len(self.failures) == len(self.errors) ==
            len(self.unexpectedSuccesses) == 0)

  test_result = unittest.TestResult()
  test_result.addUnexpectedSuccess(unittest.FunctionTestCase(lambda: None))
  if test_result.wasSuccessful():  # The bug is present.
    unittest.TestResult.wasSuccessful = wasSuccessful
    if test_result.wasSuccessful():  # Warn the user if our hot-fix failed.
      sys.stderr.write('unittest.result.TestResult monkey patch to report'
                       ' unexpected passes as failures did not work.\n')


_monkey_patch_test_result_for_unexpected_passes()


def _open(filepath, mode, _open_func=open):
  # type: (Text, Text, Callable[..., IO]) -> IO
  """Opens a file.

  Like open(), but ensure that we can open real files even if tests stub out
  open().

  Args:
    filepath: A filepath.
    mode: A mode.
    _open_func: A built-in open() function.

  Returns:
    The opened file object.
  """
  return _open_func(filepath, mode, encoding='utf-8')


class _TempDir(object):
  """Represents a temporary directory for tests.

  Creation of this class is internal. Using its public methods is OK.

  This class implements the `os.PathLike` interface (specifically,
  `os.PathLike[str]`). This means, in Python 3, it can be directly passed
  to e.g. `os.path.join()`.
  """

  def __init__(self, path):
    # type: (Text) -> None
    """Module-private: do not instantiate outside module."""
    self._path = path

  @property
  def full_path(self):
    # type: () -> Text
    """Returns the path, as a string, for the directory.

    TIP: Instead of e.g. `os.path.join(temp_dir.full_path)`, you can simply
    do `os.path.join(temp_dir)` because `__fspath__()` is implemented.
    """
    return self._path

  def __fspath__(self):
    # type: () -> Text
    """See os.PathLike."""
    return self.full_path

  def create_file(self, file_path=None, content=None, mode='w', encoding='utf8',
                  errors='strict'):
    # type: (Optional[Text], Optional[AnyStr], Text, Text, Text) -> _TempFile
    """Create a file in the directory.

    NOTE: If the file already exists, it will be made writable and overwritten.

    Args:
      file_path: Optional file path for the temp file. If not given, a unique
        file name will be generated and used. Slashes are allowed in the name;
        any missing intermediate directories will be created. NOTE: This path
        is the path that will be cleaned up, including any directories in the
        path, e.g., 'foo/bar/baz.txt' will `rm -r foo`
      content: Optional string or bytes to initially write to the file. If not
        specified, then an empty file is created.
      mode: Mode string to use when writing content. Only used if `content` is
        non-empty.
      encoding: Encoding to use when writing string content. Only used if
        `content` is text.
      errors: How to handle text to bytes encoding errors. Only used if
        `content` is text.

    Returns:
      A _TempFile representing the created file.
    """
    tf, _ = _TempFile._create(self._path, file_path, content, mode, encoding,
                              errors)
    return tf

  def mkdir(self, dir_path=None):
    # type: (Optional[Text]) -> _TempDir
    """Create a directory in the directory.

    Args:
      dir_path: Optional path to the directory to create. If not given,
        a unique name will be generated and used.

    Returns:
      A _TempDir representing the created directory.
    """
    if dir_path:
      path = os.path.join(self._path, dir_path)
    else:
      path = tempfile.mkdtemp(dir=self._path)

    # Note: there's no need to clear the directory since the containing
    # dir was cleared by the tempdir() function.
    os.makedirs(path, exist_ok=True)
    return _TempDir(path)


class _TempFile(object):
  """Represents a tempfile for tests.

  Creation of this class is internal. Using its public methods is OK.

  This class implements the `os.PathLike` interface (specifically,
  `os.PathLike[str]`). This means, in Python 3, it can be directly passed
  to e.g. `os.path.join()`.
  """

  def __init__(self, path):
    # type: (Text) -> None
    """Private: use _create instead."""
    self._path = path

  # pylint: disable=line-too-long
  @classmethod
  def _create(cls, base_path, file_path, content, mode, encoding, errors):
    # type: (Text, Optional[Text], AnyStr, Text, Text, Text) -> Tuple[_TempFile, Text]
    # pylint: enable=line-too-long
    """Module-private: create a tempfile instance."""
    if file_path:
      cleanup_path = os.path.join(base_path, _get_first_part(file_path))
      path = os.path.join(base_path, file_path)
      os.makedirs(os.path.dirname(path), exist_ok=True)
      # The file may already exist, in which case, ensure it's writable so that
      # it can be truncated.
      if os.path.exists(path) and not os.access(path, os.W_OK):
        stat_info = os.stat(path)
        os.chmod(path, stat_info.st_mode | stat.S_IWUSR)
    else:
      os.makedirs(base_path, exist_ok=True)
      fd, path = tempfile.mkstemp(dir=str(base_path))
      os.close(fd)
      cleanup_path = path

    tf = cls(path)

    if content:
      if isinstance(content, str):
        tf.write_text(content, mode=mode, encoding=encoding, errors=errors)
      else:
        tf.write_bytes(content, mode)

    else:
      tf.write_bytes(b'')

    return tf, cleanup_path

  @property
  def full_path(self):
    # type: () -> Text
    """Returns the path, as a string, for the file.

    TIP: Instead of e.g. `os.path.join(temp_file.full_path)`, you can simply
    do `os.path.join(temp_file)` because `__fspath__()` is implemented.
    """
    return self._path

  def __fspath__(self):
    # type: () -> Text
    """See os.PathLike."""
    return self.full_path

  def read_text(self, encoding='utf8', errors='strict'):
    # type: (Text, Text) -> Text
    """Return the contents of the file as text."""
    with self.open_text(encoding=encoding, errors=errors) as fp:
      return fp.read()

  def read_bytes(self):
    # type: () -> bytes
    """Return the content of the file as bytes."""
    with self.open_bytes() as fp:
      return fp.read()

  def write_text(self, text, mode='w', encoding='utf8', errors='strict'):
    # type: (Text, Text, Text, Text) -> None
    """Write text to the file.

    Args:
      text: Text to write. In Python 2, it can be bytes, which will be
        decoded using the `encoding` arg (this is as an aid for code that
        is 2 and 3 compatible).
      mode: The mode to open the file for writing.
      encoding: The encoding to use when writing the text to the file.
      errors: The error handling strategy to use when converting text to bytes.
    """
    with self.open_text(mode, encoding=encoding, errors=errors) as fp:
      fp.write(text)

  def write_bytes(self, data, mode='wb'):
    # type: (bytes, Text) -> None
    """Write bytes to the file.

    Args:
      data: bytes to write.
      mode: Mode to open the file for writing. The "b" flag is implicit if
        not already present. It must not have the "t" flag.
    """
    with self.open_bytes(mode) as fp:
      fp.write(data)

  def open_text(self, mode='rt', encoding='utf8', errors='strict'):
    # type: (Text, Text, Text) -> ContextManager[TextIO]
    """Return a context manager for opening the file in text mode.

    Args:
      mode: The mode to open the file in. The "t" flag is implicit if not
        already present. It must not have the "b" flag.
      encoding: The encoding to use when opening the file.
      errors: How to handle decoding errors.

    Returns:
      Context manager that yields an open file.

    Raises:
      ValueError: if invalid inputs are provided.
    """
    if 'b' in mode:
      raise ValueError('Invalid mode {!r}: "b" flag not allowed when opening '
                       'file in text mode'.format(mode))
    if 't' not in mode:
      mode += 't'
    cm = self._open(mode, encoding, errors)
    return cm

  def open_bytes(self, mode='rb'):
    # type: (Text) -> ContextManager[BinaryIO]
    """Return a context manager for opening the file in binary mode.

    Args:
      mode: The mode to open the file in. The "b" mode is implicit if not
        already present. It must not have the "t" flag.

    Returns:
      Context manager that yields an open file.

    Raises:
      ValueError: if invalid inputs are provided.
    """
    if 't' in mode:
      raise ValueError('Invalid mode {!r}: "t" flag not allowed when opening '
                       'file in binary mode'.format(mode))
    if 'b' not in mode:
      mode += 'b'
    cm = self._open(mode, encoding=None, errors=None)
    return cm

  # TODO(b/123775699): Once pytype supports typing.Literal, use overload and
  # Literal to express more precise return types. The contained type is
  # currently `Any` to avoid [bad-return-type] errors in the open_* methods.
  @contextlib.contextmanager
  def _open(
      self,
      mode: str,
      encoding: Optional[str] = 'utf8',
      errors: Optional[str] = 'strict',
  ) -> Iterator[Any]:
    with io.open(
        self.full_path, mode=mode, encoding=encoding, errors=errors) as fp:
      yield fp


class _method(object):
  """A decorator that supports both instance and classmethod invocations.

  Using similar semantics to the @property builtin, this decorator can augment
  an instance method to support conditional logic when invoked on a class
  object. This breaks support for invoking an instance method via the class
  (e.g. Cls.method(self, ...)) but is still situationally useful.
  """

  def __init__(self, finstancemethod):
    # type: (Callable[..., Any]) -> None
    self._finstancemethod = finstancemethod
    self._fclassmethod = None

  def classmethod(self, fclassmethod):
    # type: (Callable[..., Any]) -> _method
    self._fclassmethod = classmethod(fclassmethod)
    return self

  def __doc__(self):
    # type: () -> str
    if getattr(self._finstancemethod, '__doc__'):
      return self._finstancemethod.__doc__
    elif getattr(self._fclassmethod, '__doc__'):
      return self._fclassmethod.__doc__
    return ''

  def __get__(self, obj, type_):
    # type: (Optional[Any], Optional[Type[Any]]) -> Callable[..., Any]
    func = self._fclassmethod if obj is None else self._finstancemethod
    return func.__get__(obj, type_)  # pytype: disable=attribute-error


class TestCase(unittest.TestCase):
  """Extension of unittest.TestCase providing more power."""

  # When to cleanup files/directories created by our `create_tempfile()` and
  # `create_tempdir()` methods after each test case completes. This does *not*
  # affect e.g., files created outside of those methods, e.g., using the stdlib
  # tempfile module. This can be overridden at the class level, instance level,
  # or with the `cleanup` arg of `create_tempfile()` and `create_tempdir()`. See
  # `TempFileCleanup` for details on the different values.
  # TODO(b/70517332): Remove the type comment and the disable once pytype has
  # better support for enums.
  tempfile_cleanup = TempFileCleanup.ALWAYS  # type: TempFileCleanup  # pytype: disable=annotation-type-mismatch

  maxDiff = 80 * 20
  longMessage = True

  # Exit stacks for per-test and per-class scopes.
  _exit_stack = None
  _cls_exit_stack = None

  def __init__(self, *args, **kwargs):
    super(TestCase, self).__init__(*args, **kwargs)
    # This is to work around missing type stubs in unittest.pyi
    self._outcome = getattr(self, '_outcome')  # type: Optional[_OutcomeType]

  def setUp(self):
    super(TestCase, self).setUp()
    # NOTE: Only Python 3 contextlib has ExitStack
    if hasattr(contextlib, 'ExitStack'):
      self._exit_stack = contextlib.ExitStack()
      self.addCleanup(self._exit_stack.close)

  @classmethod
  def setUpClass(cls):
    super(TestCase, cls).setUpClass()
    # NOTE: Only Python 3 contextlib has ExitStack and only Python 3.8+ has
    # addClassCleanup.
    if hasattr(contextlib, 'ExitStack') and hasattr(cls, 'addClassCleanup'):
      cls._cls_exit_stack = contextlib.ExitStack()
      cls.addClassCleanup(cls._cls_exit_stack.close)

  def create_tempdir(self, name=None, cleanup=None):
    # type: (Optional[Text], Optional[TempFileCleanup]) -> _TempDir
    """Create a temporary directory specific to the test.

    NOTE: The directory and its contents will be recursively cleared before
    creation. This ensures that there is no pre-existing state.

    This creates a named directory on disk that is isolated to this test, and
    will be properly cleaned up by the test. This avoids several pitfalls of
    creating temporary directories for test purposes, as well as makes it easier
    to setup directories and verify their contents. For example::

        def test_foo(self):
          out_dir = self.create_tempdir()
          out_log = out_dir.create_file('output.log')
          expected_outputs = [
              os.path.join(out_dir, 'data-0.txt'),
              os.path.join(out_dir, 'data-1.txt'),
          ]
          code_under_test(out_dir)
          self.assertTrue(os.path.exists(expected_paths[0]))
          self.assertTrue(os.path.exists(expected_paths[1]))
          self.assertEqual('foo', out_log.read_text())

    See also: :meth:`create_tempfile` for creating temporary files.

    Args:
      name: Optional name of the directory. If not given, a unique
        name will be generated and used.
      cleanup: Optional cleanup policy on when/if to remove the directory (and
        all its contents) at the end of the test. If None, then uses
        :attr:`tempfile_cleanup`.

    Returns:
      A _TempDir representing the created directory; see _TempDir class docs
      for usage.
    """
    test_path = self._get_tempdir_path_test()

    if name:
      path = os.path.join(test_path, name)
      cleanup_path = os.path.join(test_path, _get_first_part(name))
    else:
      os.makedirs(test_path, exist_ok=True)
      path = tempfile.mkdtemp(dir=test_path)
      cleanup_path = path

    _rmtree_ignore_errors(cleanup_path)
    os.makedirs(path, exist_ok=True)

    self._maybe_add_temp_path_cleanup(cleanup_path, cleanup)

    return _TempDir(path)

  # pylint: disable=line-too-long
  def create_tempfile(self, file_path=None, content=None, mode='w',
                      encoding='utf8', errors='strict', cleanup=None):
    # type: (Optional[Text], Optional[AnyStr], Text, Text, Text, Optional[TempFileCleanup]) -> _TempFile
    # pylint: enable=line-too-long
    """Create a temporary file specific to the test.

    This creates a named file on disk that is isolated to this test, and will
    be properly cleaned up by the test. This avoids several pitfalls of
    creating temporary files for test purposes, as well as makes it easier
    to setup files, their data, read them back, and inspect them when
    a test fails. For example::

        def test_foo(self):
          output = self.create_tempfile()
          code_under_test(output)
          self.assertGreater(os.path.getsize(output), 0)
          self.assertEqual('foo', output.read_text())

    NOTE: This will zero-out the file. This ensures there is no pre-existing
    state.
    NOTE: If the file already exists, it will be made writable and overwritten.

    See also: :meth:`create_tempdir` for creating temporary directories, and
    ``_TempDir.create_file`` for creating files within a temporary directory.

    Args:
      file_path: Optional file path for the temp file. If not given, a unique
        file name will be generated and used. Slashes are allowed in the name;
        any missing intermediate directories will be created. NOTE: This path is
        the path that will be cleaned up, including any directories in the path,
        e.g., ``'foo/bar/baz.txt'`` will ``rm -r foo``.
      content: Optional string or
        bytes to initially write to the file. If not
        specified, then an empty file is created.
      mode: Mode string to use when writing content. Only used if `content` is
        non-empty.
      encoding: Encoding to use when writing string content. Only used if
        `content` is text.
      errors: How to handle text to bytes encoding errors. Only used if
        `content` is text.
      cleanup: Optional cleanup policy on when/if to remove the directory (and
        all its contents) at the end of the test. If None, then uses
        :attr:`tempfile_cleanup`.

    Returns:
      A _TempFile representing the created file; see _TempFile class docs for
      usage.
    """
    test_path = self._get_tempdir_path_test()
    tf, cleanup_path = _TempFile._create(test_path, file_path, content=content,
                                         mode=mode, encoding=encoding,
                                         errors=errors)
    self._maybe_add_temp_path_cleanup(cleanup_path, cleanup)
    return tf

  @_method
  def enter_context(self, manager):
    # type: (ContextManager[_T]) -> _T
    """Returns the CM's value after registering it with the exit stack.

    Entering a context pushes it onto a stack of contexts. When `enter_context`
    is called on the test instance (e.g. `self.enter_context`), the context is
    exited after the test case's tearDown call. When called on the test class
    (e.g. `TestCase.enter_context`), the context is exited after the test
    class's tearDownClass call.

    Contexts are exited in the reverse order of entering. They will always
    be exited, regardless of test failure/success.

    This is useful to eliminate per-test boilerplate when context managers
    are used. For example, instead of decorating every test with `@mock.patch`,
    simply do `self.foo = self.enter_context(mock.patch(...))' in `setUp()`.

    NOTE: The context managers will always be exited without any error
    information. This is an unfortunate implementation detail due to some
    internals of how unittest runs tests.

    Args:
      manager: The context manager to enter.
    """
    if not self._exit_stack:
      raise AssertionError(
          'self._exit_stack is not set: enter_context is Py3-only; also make '
          'sure that AbslTest.setUp() is called.')
    return self._exit_stack.enter_context(manager)

  @enter_context.classmethod
  def enter_context(cls, manager):  # pylint: disable=no-self-argument
    # type: (ContextManager[_T]) -> _T
    if not cls._cls_exit_stack:
      raise AssertionError(
          'cls._cls_exit_stack is not set: cls.enter_context requires '
          'Python 3.8+; also make sure that AbslTest.setUpClass() is called.')
    return cls._cls_exit_stack.enter_context(manager)

  @classmethod
  def _get_tempdir_path_cls(cls):
    # type: () -> Text
    return os.path.join(TEST_TMPDIR.value,
                        cls.__qualname__.replace('__main__.', ''))

  def _get_tempdir_path_test(self):
    # type: () -> Text
    return os.path.join(self._get_tempdir_path_cls(), self._testMethodName)

  def _get_tempfile_cleanup(self, override):
    # type: (Optional[TempFileCleanup]) -> TempFileCleanup
    if override is not None:
      return override
    return self.tempfile_cleanup

  def _maybe_add_temp_path_cleanup(self, path, cleanup):
    # type: (Text, Optional[TempFileCleanup]) -> None
    cleanup = self._get_tempfile_cleanup(cleanup)
    if cleanup == TempFileCleanup.OFF:
      return
    elif cleanup == TempFileCleanup.ALWAYS:
      self.addCleanup(_rmtree_ignore_errors, path)
    elif cleanup == TempFileCleanup.SUCCESS:
      self._internal_add_cleanup_on_success(_rmtree_ignore_errors, path)
    else:
      raise AssertionError('Unexpected cleanup value: {}'.format(cleanup))

  def _internal_add_cleanup_on_success(
      self,
      function: Callable[..., Any],
      *args: Any,
      **kwargs: Any,
  ) -> None:
    """Adds `function` as cleanup when the test case succeeds."""
    outcome = self._outcome
    previous_failure_count = (
        len(outcome.result.failures)
        + len(outcome.result.errors)
        + len(outcome.result.unexpectedSuccesses)
    )
    def _call_cleaner_on_success(*args, **kwargs):
      if not self._internal_ran_and_passed_when_called_during_cleanup(
          previous_failure_count):
        return
      function(*args, **kwargs)
    self.addCleanup(_call_cleaner_on_success, *args, **kwargs)

  def _internal_ran_and_passed_when_called_during_cleanup(
      self,
      previous_failure_count: int,
  ) -> bool:
    """Returns whether test is passed. Expected to be called during cleanup."""
    outcome = self._outcome
    if sys.version_info[:2] >= (3, 11):
      current_failure_count = (
          len(outcome.result.failures)
          + len(outcome.result.errors)
          + len(outcome.result.unexpectedSuccesses)
      )
      return current_failure_count == previous_failure_count
    else:
      # Before Python 3.11 https://github.com/python/cpython/pull/28180, errors
      # were bufferred in _Outcome before calling cleanup.
      result = self.defaultTestResult()
      self._feedErrorsToResult(result, outcome.errors)  # pytype: disable=attribute-error
      return result.wasSuccessful()

  def shortDescription(self):
    # type: () -> Text
    """Formats both the test method name and the first line of its docstring.

    If no docstring is given, only returns the method name.

    This method overrides unittest.TestCase.shortDescription(), which
    only returns the first line of the docstring, obscuring the name
    of the test upon failure.

    Returns:
      desc: A short description of a test method.
    """
    desc = self.id()

    # Omit the main name so that test name can be directly copy/pasted to
    # the command line.
    if desc.startswith('__main__.'):
      desc = desc[len('__main__.'):]

    # NOTE: super() is used here instead of directly invoking
    # unittest.TestCase.shortDescription(self), because of the
    # following line that occurs later on:
    #       unittest.TestCase = TestCase
    # Because of this, direct invocation of what we think is the
    # superclass will actually cause infinite recursion.
    doc_first_line = super(TestCase, self).shortDescription()
    if doc_first_line is not None:
      desc = '\n'.join((desc, doc_first_line))
    return desc

  def assertStartsWith(self, actual, expected_start, msg=None):
    """Asserts that actual.startswith(expected_start) is True.

    Args:
      actual: str
      expected_start: str
      msg: Optional message to report on failure.
    """
    if not actual.startswith(expected_start):
      self.fail('%r does not start with %r' % (actual, expected_start), msg)

  def assertNotStartsWith(self, actual, unexpected_start, msg=None):
    """Asserts that actual.startswith(unexpected_start) is False.

    Args:
      actual: str
      unexpected_start: str
      msg: Optional message to report on failure.
    """
    if actual.startswith(unexpected_start):
      self.fail('%r does start with %r' % (actual, unexpected_start), msg)

  def assertEndsWith(self, actual, expected_end, msg=None):
    """Asserts that actual.endswith(expected_end) is True.

    Args:
      actual: str
      expected_end: str
      msg: Optional message to report on failure.
    """
    if not actual.endswith(expected_end):
      self.fail('%r does not end with %r' % (actual, expected_end), msg)

  def assertNotEndsWith(self, actual, unexpected_end, msg=None):
    """Asserts that actual.endswith(unexpected_end) is False.

    Args:
      actual: str
      unexpected_end: str
      msg: Optional message to report on failure.
    """
    if actual.endswith(unexpected_end):
      self.fail('%r does end with %r' % (actual, unexpected_end), msg)

  def assertSequenceStartsWith(self, prefix, whole, msg=None):
    """An equality assertion for the beginning of ordered sequences.

    If prefix is an empty sequence, it will raise an error unless whole is also
    an empty sequence.

    If prefix is not a sequence, it will raise an error if the first element of
    whole does not match.

    Args:
      prefix: A sequence expected at the beginning of the whole parameter.
      whole: The sequence in which to look for prefix.
      msg: Optional message to report on failure.
    """
    try:
      prefix_len = len(prefix)
    except (TypeError, NotImplementedError):
      prefix = [prefix]
      prefix_len = 1

    try:
      whole_len = len(whole)
    except (TypeError, NotImplementedError):
      self.fail('For whole: len(%s) is not supported, it appears to be type: '
                '%s' % (whole, type(whole)), msg)

    assert prefix_len <= whole_len, self._formatMessage(
        msg,
        'Prefix length (%d) is longer than whole length (%d).' %
        (prefix_len, whole_len)
    )

    if not prefix_len and whole_len:
      self.fail('Prefix length is 0 but whole length is %d: %s' %
                (len(whole), whole), msg)

    try:
      self.assertSequenceEqual(prefix, whole[:prefix_len], msg)
    except AssertionError:
      self.fail('prefix: %s not found at start of whole: %s.' %
                (prefix, whole), msg)

  def assertEmpty(self, container, msg=None):
    """Asserts that an object has zero length.

    Args:
      container: Anything that implements the collections.abc.Sized interface.
      msg: Optional message to report on failure.
    """
    if not isinstance(container, abc.Sized):
      self.fail('Expected a Sized object, got: '
                '{!r}'.format(type(container).__name__), msg)

    # explicitly check the length since some Sized objects (e.g. numpy.ndarray)
    # have strange __nonzero__/__bool__ behavior.
    if len(container):  # pylint: disable=g-explicit-length-test
      self.fail('{!r} has length of {}.'.format(container, len(container)), msg)

  def assertNotEmpty(self, container, msg=None):
    """Asserts that an object has non-zero length.

    Args:
      container: Anything that implements the collections.abc.Sized interface.
      msg: Optional message to report on failure.
    """
    if not isinstance(container, abc.Sized):
      self.fail('Expected a Sized object, got: '
                '{!r}'.format(type(container).__name__), msg)

    # explicitly check the length since some Sized objects (e.g. numpy.ndarray)
    # have strange __nonzero__/__bool__ behavior.
    if not len(container):  # pylint: disable=g-explicit-length-test
      self.fail('{!r} has length of 0.'.format(container), msg)

  def assertLen(self, container, expected_len, msg=None):
    """Asserts that an object has the expected length.

    Args:
      container: Anything that implements the collections.abc.Sized interface.
      expected_len: The expected length of the container.
      msg: Optional message to report on failure.
    """
    if not isinstance(container, abc.Sized):
      self.fail('Expected a Sized object, got: '
                '{!r}'.format(type(container).__name__), msg)
    if len(container) != expected_len:
      container_repr = unittest.util.safe_repr(container)  # pytype: disable=module-attr
      self.fail('{} has length of {}, expected {}.'.format(
          container_repr, len(container), expected_len), msg)

  def assertSequenceAlmostEqual(self, expected_seq, actual_seq, places=None,
                                msg=None, delta=None):
    """An approximate equality assertion for ordered sequences.

    Fail if the two sequences are unequal as determined by their value
    differences rounded to the given number of decimal places (default 7) and
    comparing to zero, or by comparing that the difference between each value
    in the two sequences is more than the given delta.

    Note that decimal places (from zero) are usually not the same as significant
    digits (measured from the most significant digit).

    If the two sequences compare equal then they will automatically compare
    almost equal.

    Args:
      expected_seq: A sequence containing elements we are expecting.
      actual_seq: The sequence that we are testing.
      places: The number of decimal places to compare.
      msg: The message to be printed if the test fails.
      delta: The OK difference between compared values.
    """
    if len(expected_seq) != len(actual_seq):
      self.fail('Sequence size mismatch: {} vs {}'.format(
          len(expected_seq), len(actual_seq)), msg)

    err_list = []
    for idx, (exp_elem, act_elem) in enumerate(zip(expected_seq, actual_seq)):
      try:
        # assertAlmostEqual should be called with at most one of `places` and
        # `delta`. However, it's okay for assertSequenceAlmostEqual to pass
        # both because we want the latter to fail if the former does.
        # pytype: disable=wrong-keyword-args
        self.assertAlmostEqual(exp_elem, act_elem, places=places, msg=msg,
                               delta=delta)
        # pytype: enable=wrong-keyword-args
      except self.failureException as err:
        err_list.append('At index {}: {}'.format(idx, err))

    if err_list:
      if len(err_list) > 30:
        err_list = err_list[:30] + ['...']
      msg = self._formatMessage(msg, '\n'.join(err_list))
      self.fail(msg)

  def assertContainsSubset(self, expected_subset, actual_set, msg=None):
    """Checks whether actual iterable is a superset of expected iterable."""
    missing = set(expected_subset) - set(actual_set)
    if not missing:
      return

    self.fail('Missing elements %s\nExpected: %s\nActual: %s' % (
        missing, expected_subset, actual_set), msg)

  def assertNoCommonElements(self, expected_seq, actual_seq, msg=None):
    """Checks whether actual iterable and expected iterable are disjoint."""
    common = set(expected_seq) & set(actual_seq)
    if not common:
      return

    self.fail('Common elements %s\nExpected: %s\nActual: %s' % (
        common, expected_seq, actual_seq), msg)

  def assertItemsEqual(self, expected_seq, actual_seq, msg=None):
    """Deprecated, please use assertCountEqual instead.

    This is equivalent to assertCountEqual.

    Args:
      expected_seq: A sequence containing elements we are expecting.
      actual_seq: The sequence that we are testing.
      msg: The message to be printed if the test fails.
    """
    super().assertCountEqual(expected_seq, actual_seq, msg)

  def assertSameElements(self, expected_seq, actual_seq, msg=None):
    """Asserts that two sequences have the same elements (in any order).

    This method, unlike assertCountEqual, doesn't care about any
    duplicates in the expected and actual sequences::

        # Doesn't raise an AssertionError
        assertSameElements([1, 1, 1, 0, 0, 0], [0, 1])

    If possible, you should use assertCountEqual instead of
    assertSameElements.

    Args:
      expected_seq: A sequence containing elements we are expecting.
      actual_seq: The sequence that we are testing.
      msg: The message to be printed if the test fails.
    """
    # `unittest2.TestCase` used to have assertSameElements, but it was
    # removed in favor of assertItemsEqual. As there's a unit test
    # that explicitly checks this behavior, I am leaving this method
    # alone.
    # Fail on strings: empirically, passing strings to this test method
    # is almost always a bug. If comparing the character sets of two strings
    # is desired, cast the inputs to sets or lists explicitly.
    if (isinstance(expected_seq, _TEXT_OR_BINARY_TYPES) or
        isinstance(actual_seq, _TEXT_OR_BINARY_TYPES)):
      self.fail('Passing string/bytes to assertSameElements is usually a bug. '
                'Did you mean to use assertEqual?\n'
                'Expected: %s\nActual: %s' % (expected_seq, actual_seq))
    try:
      expected = dict([(element, None) for element in expected_seq])
      actual = dict([(element, None) for element in actual_seq])
      missing = [element for element in expected if element not in actual]
      unexpected = [element for element in actual if element not in expected]
      missing.sort()
      unexpected.sort()
    except TypeError:
      # Fall back to slower list-compare if any of the objects are
      # not hashable.
      expected = list(expected_seq)
      actual = list(actual_seq)
      expected.sort()
      actual.sort()
      missing, unexpected = _sorted_list_difference(expected, actual)
    errors = []
    if msg:
      errors.extend((msg, ':\n'))
    if missing:
      errors.append('Expected, but missing:\n  %r\n' % missing)
    if unexpected:
      errors.append('Unexpected, but present:\n  %r\n' % unexpected)
    if missing or unexpected:
      self.fail(''.join(errors))

  # unittest.TestCase.assertMultiLineEqual works very similarly, but it
  # has a different error format. However, I find this slightly more readable.
  def assertMultiLineEqual(self, first, second, msg=None, **kwargs):
    """Asserts that two multi-line strings are equal."""
    assert isinstance(first,