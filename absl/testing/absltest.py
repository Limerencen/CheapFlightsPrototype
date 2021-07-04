
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
                      str), ('First argument is not a string: %r' % (first,))
    assert isinstance(second,
                      str), ('Second argument is not a string: %r' % (second,))
    line_limit = kwargs.pop('line_limit', 0)
    if kwargs:
      raise TypeError('Unexpected keyword args {}'.format(tuple(kwargs)))

    if first == second:
      return
    if msg:
      failure_message = [msg + ':\n']
    else:
      failure_message = ['\n']
    if line_limit:
      line_limit += len(failure_message)
    for line in difflib.ndiff(first.splitlines(True), second.splitlines(True)):
      failure_message.append(line)
      if not line.endswith('\n'):
        failure_message.append('\n')
    if line_limit and len(failure_message) > line_limit:
      n_omitted = len(failure_message) - line_limit
      failure_message = failure_message[:line_limit]
      failure_message.append(
          '(... and {} more delta lines omitted for brevity.)\n'.format(
              n_omitted))

    raise self.failureException(''.join(failure_message))

  def assertBetween(self, value, minv, maxv, msg=None):
    """Asserts that value is between minv and maxv (inclusive)."""
    msg = self._formatMessage(msg,
                              '"%r" unexpectedly not between "%r" and "%r"' %
                              (value, minv, maxv))
    self.assertTrue(minv <= value, msg)
    self.assertTrue(maxv >= value, msg)

  def assertRegexMatch(self, actual_str, regexes, message=None):
    r"""Asserts that at least one regex in regexes matches str.

    If possible you should use `assertRegex`, which is a simpler
    version of this method. `assertRegex` takes a single regular
    expression (a string or re compiled object) instead of a list.

    Notes:

    1. This function uses substring matching, i.e. the matching
       succeeds if *any* substring of the error message matches *any*
       regex in the list.  This is more convenient for the user than
       full-string matching.

    2. If regexes is the empty list, the matching will always fail.

    3. Use regexes=[''] for a regex that will always pass.

    4. '.' matches any single character *except* the newline.  To
       match any character, use '(.|\n)'.

    5. '^' matches the beginning of each line, not just the beginning
       of the string.  Similarly, '$' matches the end of each line.

    6. An exception will be thrown if regexes contains an invalid
       regex.

    Args:
      actual_str:  The string we try to match with the items in regexes.
      regexes:  The regular expressions we want to match against str.
          See "Notes" above for detailed notes on how this is interpreted.
      message:  The message to be printed if the test fails.
    """
    if isinstance(regexes, _TEXT_OR_BINARY_TYPES):
      self.fail('regexes is string or bytes; use assertRegex instead.',
                message)
    if not regexes:
      self.fail('No regexes specified.', message)

    regex_type = type(regexes[0])
    for regex in regexes[1:]:
      if type(regex) is not regex_type:  # pylint: disable=unidiomatic-typecheck
        self.fail('regexes list must all be the same type.', message)

    if regex_type is bytes and isinstance(actual_str, str):
      regexes = [regex.decode('utf-8') for regex in regexes]
      regex_type = str
    elif regex_type is str and isinstance(actual_str, bytes):
      regexes = [regex.encode('utf-8') for regex in regexes]
      regex_type = bytes

    if regex_type is str:
      regex = u'(?:%s)' % u')|(?:'.join(regexes)
    elif regex_type is bytes:
      regex = b'(?:' + (b')|(?:'.join(regexes)) + b')'
    else:
      self.fail('Only know how to deal with unicode str or bytes regexes.',
                message)

    if not re.search(regex, actual_str, re.MULTILINE):
      self.fail('"%s" does not contain any of these regexes: %s.' %
                (actual_str, regexes), message)

  def assertCommandSucceeds(self, command, regexes=(b'',), env=None,
                            close_fds=True, msg=None):
    """Asserts that a shell command succeeds (i.e. exits with code 0).

    Args:
      command: List or string representing the command to run.
      regexes: List of regular expression byte strings that match success.
      env: Dictionary of environment variable settings. If None, no environment
          variables will be set for the child process. This is to make tests
          more hermetic. NOTE: this behavior is different than the standard
          subprocess module.
      close_fds: Whether or not to close all open fd's in the child after
          forking.
      msg: Optional message to report on failure.
    """
    (ret_code, err) = get_command_stderr(command, env, close_fds)

    # We need bytes regexes here because `err` is bytes.
    # Accommodate code which listed their output regexes w/o the b'' prefix by
    # converting them to bytes for the user.
    if isinstance(regexes[0], str):
      regexes = [regex.encode('utf-8') for regex in regexes]

    command_string = get_command_string(command)
    self.assertEqual(
        ret_code, 0,
        self._formatMessage(msg,
                            'Running command\n'
                            '%s failed with error code %s and message\n'
                            '%s' % (_quote_long_string(command_string),
                                    ret_code,
                                    _quote_long_string(err)))
    )
    self.assertRegexMatch(
        err,
        regexes,
        message=self._formatMessage(
            msg,
            'Running command\n'
            '%s failed with error code %s and message\n'
            '%s which matches no regex in %s' % (
                _quote_long_string(command_string),
                ret_code,
                _quote_long_string(err),
                regexes)))

  def assertCommandFails(self, command, regexes, env=None, close_fds=True,
                         msg=None):
    """Asserts a shell command fails and the error matches a regex in a list.

    Args:
      command: List or string representing the command to run.
      regexes: the list of regular expression strings.
      env: Dictionary of environment variable settings. If None, no environment
          variables will be set for the child process. This is to make tests
          more hermetic. NOTE: this behavior is different than the standard
          subprocess module.
      close_fds: Whether or not to close all open fd's in the child after
          forking.
      msg: Optional message to report on failure.
    """
    (ret_code, err) = get_command_stderr(command, env, close_fds)

    # We need bytes regexes here because `err` is bytes.
    # Accommodate code which listed their output regexes w/o the b'' prefix by
    # converting them to bytes for the user.
    if isinstance(regexes[0], str):
      regexes = [regex.encode('utf-8') for regex in regexes]

    command_string = get_command_string(command)
    self.assertNotEqual(
        ret_code, 0,
        self._formatMessage(msg, 'The following command succeeded '
                            'while expected to fail:\n%s' %
                            _quote_long_string(command_string)))
    self.assertRegexMatch(
        err,
        regexes,
        message=self._formatMessage(
            msg,
            'Running command\n'
            '%s failed with error code %s and message\n'
            '%s which matches no regex in %s' % (
                _quote_long_string(command_string),
                ret_code,
                _quote_long_string(err),
                regexes)))

  class _AssertRaisesContext(object):

    def __init__(self, expected_exception, test_case, test_func, msg=None):
      self.expected_exception = expected_exception
      self.test_case = test_case
      self.test_func = test_func
      self.msg = msg

    def __enter__(self):
      return self

    def __exit__(self, exc_type, exc_value, tb):
      if exc_type is None:
        self.test_case.fail(self.expected_exception.__name__ + ' not raised',
                            self.msg)
      if not issubclass(exc_type, self.expected_exception):
        return False
      self.test_func(exc_value)
      if exc_value:
        self.exception = exc_value.with_traceback(None)
      return True

  @typing.overload
  def assertRaisesWithPredicateMatch(
      self, expected_exception, predicate) -> _AssertRaisesContext:
    # The purpose of this return statement is to work around
    # https://github.com/PyCQA/pylint/issues/5273; it is otherwise ignored.
    return self._AssertRaisesContext(None, None, None)

  @typing.overload
  def assertRaisesWithPredicateMatch(
      self, expected_exception, predicate, callable_obj: Callable[..., Any],
      *args, **kwargs) -> None:
    # The purpose of this return statement is to work around
    # https://github.com/PyCQA/pylint/issues/5273; it is otherwise ignored.
    return self._AssertRaisesContext(None, None, None)

  def assertRaisesWithPredicateMatch(self, expected_exception, predicate,
                                     callable_obj=None, *args, **kwargs):
    """Asserts that exception is thrown and predicate(exception) is true.

    Args:
      expected_exception: Exception class expected to be raised.
      predicate: Function of one argument that inspects the passed-in exception
          and returns True (success) or False (please fail the test).
      callable_obj: Function to be called.
      *args: Extra args.
      **kwargs: Extra keyword args.

    Returns:
      A context manager if callable_obj is None. Otherwise, None.

    Raises:
      self.failureException if callable_obj does not raise a matching exception.
    """
    def Check(err):
      self.assertTrue(predicate(err),
                      '%r does not match predicate %r' % (err, predicate))

    context = self._AssertRaisesContext(expected_exception, self, Check)
    if callable_obj is None:
      return context
    with context:
      callable_obj(*args, **kwargs)

  @typing.overload
  def assertRaisesWithLiteralMatch(
      self, expected_exception, expected_exception_message
  ) -> _AssertRaisesContext:
    # The purpose of this return statement is to work around
    # https://github.com/PyCQA/pylint/issues/5273; it is otherwise ignored.
    return self._AssertRaisesContext(None, None, None)

  @typing.overload
  def assertRaisesWithLiteralMatch(
      self, expected_exception, expected_exception_message,
      callable_obj: Callable[..., Any], *args, **kwargs) -> None:
    # The purpose of this return statement is to work around
    # https://github.com/PyCQA/pylint/issues/5273; it is otherwise ignored.
    return self._AssertRaisesContext(None, None, None)

  def assertRaisesWithLiteralMatch(self, expected_exception,
                                   expected_exception_message,
                                   callable_obj=None, *args, **kwargs):
    """Asserts that the message in a raised exception equals the given string.

    Unlike assertRaisesRegex, this method takes a literal string, not
    a regular expression.

    with self.assertRaisesWithLiteralMatch(ExType, 'message'):
      DoSomething()

    Args:
      expected_exception: Exception class expected to be raised.
      expected_exception_message: String message expected in the raised
          exception.  For a raise exception e, expected_exception_message must
          equal str(e).
      callable_obj: Function to be called, or None to return a context.
      *args: Extra args.
      **kwargs: Extra kwargs.

    Returns:
      A context manager if callable_obj is None. Otherwise, None.

    Raises:
      self.failureException if callable_obj does not raise a matching exception.
    """
    def Check(err):
      actual_exception_message = str(err)
      self.assertTrue(expected_exception_message == actual_exception_message,
                      'Exception message does not match.\n'
                      'Expected: %r\n'
                      'Actual: %r' % (expected_exception_message,
                                      actual_exception_message))

    context = self._AssertRaisesContext(expected_exception, self, Check)
    if callable_obj is None:
      return context
    with context:
      callable_obj(*args, **kwargs)

  def assertContainsInOrder(self, strings, target, msg=None):
    """Asserts that the strings provided are found in the target in order.

    This may be useful for checking HTML output.

    Args:
      strings: A list of strings, such as [ 'fox', 'dog' ]
      target: A target string in which to look for the strings, such as
          'The quick brown fox jumped over the lazy dog'.
      msg: Optional message to report on failure.
    """
    if isinstance(strings, (bytes, unicode if str is bytes else str)):
      strings = (strings,)

    current_index = 0
    last_string = None
    for string in strings:
      index = target.find(str(string), current_index)
      if index == -1 and current_index == 0:
        self.fail("Did not find '%s' in '%s'" %
                  (string, target), msg)
      elif index == -1:
        self.fail("Did not find '%s' after '%s' in '%s'" %
                  (string, last_string, target), msg)
      last_string = string
      current_index = index

  def assertContainsSubsequence(self, container, subsequence, msg=None):
    """Asserts that "container" contains "subsequence" as a subsequence.

    Asserts that "container" contains all the elements of "subsequence", in
    order, but possibly with other elements interspersed. For example, [1, 2, 3]
    is a subsequence of [0, 0, 1, 2, 0, 3, 0] but not of [0, 0, 1, 3, 0, 2, 0].

    Args:
      container: the list we're testing for subsequence inclusion.
      subsequence: the list we hope will be a subsequence of container.
      msg: Optional message to report on failure.
    """
    first_nonmatching = None
    reversed_container = list(reversed(container))
    subsequence = list(subsequence)

    for e in subsequence:
      if e not in reversed_container:
        first_nonmatching = e
        break
      while e != reversed_container.pop():
        pass

    if first_nonmatching is not None:
      self.fail('%s not a subsequence of %s. First non-matching element: %s' %
                (subsequence, container, first_nonmatching), msg)

  def assertContainsExactSubsequence(self, container, subsequence, msg=None):
    """Asserts that "container" contains "subsequence" as an exact subsequence.

    Asserts that "container" contains all the elements of "subsequence", in
    order, and without other elements interspersed. For example, [1, 2, 3] is an
    exact subsequence of [0, 0, 1, 2, 3, 0] but not of [0, 0, 1, 2, 0, 3, 0].

    Args:
      container: the list we're testing for subsequence inclusion.
      subsequence: the list we hope will be an exact subsequence of container.
      msg: Optional message to report on failure.
    """
    container = list(container)
    subsequence = list(subsequence)
    longest_match = 0

    for start in range(1 + len(container) - len(subsequence)):
      if longest_match == len(subsequence):
        break
      index = 0
      while (index < len(subsequence) and
             subsequence[index] == container[start + index]):
        index += 1
      longest_match = max(longest_match, index)

    if longest_match < len(subsequence):
      self.fail('%s not an exact subsequence of %s. '
                'Longest matching prefix: %s' %
                (subsequence, container, subsequence[:longest_match]), msg)

  def assertTotallyOrdered(self, *groups, **kwargs):
    """Asserts that total ordering has been implemented correctly.

    For example, say you have a class A that compares only on its attribute x.
    Comparators other than ``__lt__`` are omitted for brevity::

        class A(object):
          def __init__(self, x, y):
            self.x = x
            self.y = y

          def __hash__(self):
            return hash(self.x)

          def __lt__(self, other):
            try:
              return self.x < other.x
            except AttributeError:
              return NotImplemented

    assertTotallyOrdered will check that instances can be ordered correctly.
    For example::

        self.assertTotallyOrdered(
            [None],  # None should come before everything else.
            [1],  # Integers sort earlier.
            [A(1, 'a')],
            [A(2, 'b')],  # 2 is after 1.
            [A(3, 'c'), A(3, 'd')],  # The second argument is irrelevant.
            [A(4, 'z')],
            ['foo'])  # Strings sort last.

    Args:
      *groups: A list of groups of elements.  Each group of elements is a list
        of objects that are equal.  The elements in each group must be less
        than the elements in the group after it.  For example, these groups are
        totally ordered: ``[None]``, ``[1]``, ``[2, 2]``, ``[3]``.
      **kwargs: optional msg keyword argument can be passed.
    """

    def CheckOrder(small, big):
      """Ensures small is ordered before big."""
      self.assertFalse(small == big,
                       self._formatMessage(msg, '%r unexpectedly equals %r' %
                                           (small, big)))
      self.assertTrue(small != big,
                      self._formatMessage(msg, '%r unexpectedly equals %r' %
                                          (small, big)))
      self.assertLess(small, big, msg)
      self.assertFalse(big < small,
                       self._formatMessage(msg,
                                           '%r unexpectedly less than %r' %
                                           (big, small)))
      self.assertLessEqual(small, big, msg)
      self.assertFalse(big <= small, self._formatMessage(
          '%r unexpectedly less than or equal to %r' % (big, small), msg
      ))
      self.assertGreater(big, small, msg)
      self.assertFalse(small > big,
                       self._formatMessage(msg,
                                           '%r unexpectedly greater than %r' %
                                           (small, big)))
      self.assertGreaterEqual(big, small)
      self.assertFalse(small >= big, self._formatMessage(
          msg,
          '%r unexpectedly greater than or equal to %r' % (small, big)))

    def CheckEqual(a, b):
      """Ensures that a and b are equal."""
      self.assertEqual(a, b, msg)
      self.assertFalse(a != b,
                       self._formatMessage(msg, '%r unexpectedly unequals %r' %
                                           (a, b)))

      # Objects that compare equal must hash to the same value, but this only
      # applies if both objects are hashable.
      if (isinstance(a, abc.Hashable) and
          isinstance(b, abc.Hashable)):
        self.assertEqual(
            hash(a), hash(b),
            self._formatMessage(
                msg, 'hash %d of %r unexpectedly not equal to hash %d of %r' %
                (hash(a), a, hash(b), b)))

      self.assertFalse(a < b,
                       self._formatMessage(msg,
                                           '%r unexpectedly less than %r' %
                                           (a, b)))
      self.assertFalse(b < a,
                       self._formatMessage(msg,
                                           '%r unexpectedly less than %r' %
                                           (b, a)))
      self.assertLessEqual(a, b, msg)
      self.assertLessEqual(b, a, msg)  # pylint: disable=arguments-out-of-order
      self.assertFalse(a > b,
                       self._formatMessage(msg,
                                           '%r unexpectedly greater than %r' %
                                           (a, b)))
      self.assertFalse(b > a,
                       self._formatMessage(msg,
                                           '%r unexpectedly greater than %r' %
                                           (b, a)))
      self.assertGreaterEqual(a, b, msg)
      self.assertGreaterEqual(b, a, msg)  # pylint: disable=arguments-out-of-order

    msg = kwargs.get('msg')

    # For every combination of elements, check the order of every pair of
    # elements.
    for elements in itertools.product(*groups):
      elements = list(elements)
      for index, small in enumerate(elements[:-1]):
        for big in elements[index + 1:]:
          CheckOrder(small, big)

    # Check that every element in each group is equal.
    for group in groups:
      for a in group:
        CheckEqual(a, a)
      for a, b in itertools.product(group, group):
        CheckEqual(a, b)

  def assertDictEqual(self, a, b, msg=None):
    """Raises AssertionError if a and b are not equal dictionaries.

    Args:
      a: A dict, the expected value.
      b: A dict, the actual value.
      msg: An optional str, the associated message.

    Raises:
      AssertionError: if the dictionaries are not equal.
    """
    self.assertIsInstance(a, dict, self._formatMessage(
        msg,
        'First argument is not a dictionary'
    ))
    self.assertIsInstance(b, dict, self._formatMessage(
        msg,
        'Second argument is not a dictionary'
    ))

    def Sorted(list_of_items):
      try:
        return sorted(list_of_items)  # In 3.3, unordered are possible.
      except TypeError:
        return list_of_items

    if a == b:
      return
    a_items = Sorted(list(a.items()))
    b_items = Sorted(list(b.items()))

    unexpected = []
    missing = []
    different = []

    safe_repr = unittest.util.safe_repr  # pytype: disable=module-attr

    def Repr(dikt):
      """Deterministic repr for dict."""
      # Sort the entries based on their repr, not based on their sort order,
      # which will be non-deterministic across executions, for many types.
      entries = sorted((safe_repr(k), safe_repr(v)) for k, v in dikt.items())
      return '{%s}' % (', '.join('%s: %s' % pair for pair in entries))

    message = ['%s != %s%s' % (Repr(a), Repr(b), ' (%s)' % msg if msg else '')]

    # The standard library default output confounds lexical difference with
    # value difference; treat them separately.
    for a_key, a_value in a_items:
      if a_key not in b:
        missing.append((a_key, a_value))
      elif a_value != b[a_key]:
        different.append((a_key, a_value, b[a_key]))

    for b_key, b_value in b_items:
      if b_key not in a:
        unexpected.append((b_key, b_value))

    if unexpected:
      message.append(
          'Unexpected, but present entries:\n%s' % ''.join(
              '%s: %s\n' % (safe_repr(k), safe_repr(v)) for k, v in unexpected))

    if different:
      message.append(
          'repr() of differing entries:\n%s' % ''.join(
              '%s: %s != %s\n' % (safe_repr(k), safe_repr(a_value),
                                  safe_repr(b_value))
              for k, a_value, b_value in different))

    if missing:
      message.append(
          'Missing entries:\n%s' % ''.join(
              ('%s: %s\n' % (safe_repr(k), safe_repr(v)) for k, v in missing)))

    raise self.failureException('\n'.join(message))

  def assertUrlEqual(self, a, b, msg=None):
    """Asserts that urls are equal, ignoring ordering of query params."""
    parsed_a = parse.urlparse(a)
    parsed_b = parse.urlparse(b)
    self.assertEqual(parsed_a.scheme, parsed_b.scheme, msg)
    self.assertEqual(parsed_a.netloc, parsed_b.netloc, msg)
    self.assertEqual(parsed_a.path, parsed_b.path, msg)
    self.assertEqual(parsed_a.fragment, parsed_b.fragment, msg)
    self.assertEqual(sorted(parsed_a.params.split(';')),
                     sorted(parsed_b.params.split(';')), msg)
    self.assertDictEqual(
        parse.parse_qs(parsed_a.query, keep_blank_values=True),
        parse.parse_qs(parsed_b.query, keep_blank_values=True), msg)

  def assertSameStructure(self, a, b, aname='a', bname='b', msg=None):
    """Asserts that two values contain the same structural content.

    The two arguments should be data trees consisting of trees of dicts and
    lists. They will be deeply compared by walking into the contents of dicts
    and lists; other items will be compared using the == operator.
    If the two structures differ in content, the failure message will indicate
    the location within the structures where the first difference is found.
    This may be helpful when comparing large structures.

    Mixed Sequence and Set types are supported. Mixed Mapping types are
    supported, but the order of the keys will not be considered in the
    comparison.

    Args:
      a: The first structure to compare.
      b: The second structure to compare.
      aname: Variable name to use for the first structure in assertion messages.
      bname: Variable name to use for the second structure.
      msg: Additional text to include in the failure message.
    """

    # Accumulate all the problems found so we can report all of them at once
    # rather than just stopping at the first
    problems = []

    _walk_structure_for_problems(a, b, aname, bname, problems)

    # Avoid spamming the user toooo much
    if self.maxDiff is not None:
      max_problems_to_show = self.maxDiff // 80
      if len(problems) > max_problems_to_show:
        problems = problems[0:max_problems_to_show-1] + ['...']

    if problems:
      self.fail('; '.join(problems), msg)

  def assertJsonEqual(self, first, second, msg=None):
    """Asserts that the JSON objects defined in two strings are equal.

    A summary of the differences will be included in the failure message
    using assertSameStructure.

    Args:
      first: A string containing JSON to decode and compare to second.
      second: A string containing JSON to decode and compare to first.
      msg: Additional text to include in the failure message.
    """
    try:
      first_structured = json.loads(first)
    except ValueError as e:
      raise ValueError(self._formatMessage(
          msg,
          'could not decode first JSON value %s: %s' % (first, e)))

    try:
      second_structured = json.loads(second)
    except ValueError as e:
      raise ValueError(self._formatMessage(
          msg,
          'could not decode second JSON value %s: %s' % (second, e)))

    self.assertSameStructure(first_structured, second_structured,
                             aname='first', bname='second', msg=msg)

  def _getAssertEqualityFunc(self, first, second):
    # type: (Any, Any) -> Callable[..., None]
    try:
      return super(TestCase, self)._getAssertEqualityFunc(first, second)
    except AttributeError:
      # This is a workaround if unittest.TestCase.__init__ was never run.
      # It usually means that somebody created a subclass just for the
      # assertions and has overridden __init__. "assertTrue" is a safe
      # value that will not make __init__ raise a ValueError.
      test_method = getattr(self, '_testMethodName', 'assertTrue')
      super(TestCase, self).__init__(test_method)

    return super(TestCase, self)._getAssertEqualityFunc(first, second)

  def fail(self, msg=None, prefix=None):
    """Fail immediately with the given message, optionally prefixed."""
    return super(TestCase, self).fail(self._formatMessage(prefix, msg))


def _sorted_list_difference(expected, actual):
  # type: (List[_T], List[_T]) -> Tuple[List[_T], List[_T]]
  """Finds elements in only one or the other of two, sorted input lists.

  Returns a two-element tuple of lists.  The first list contains those
  elements in the "expected" list but not in the "actual" list, and the
  second contains those elements in the "actual" list but not in the
  "expected" list.  Duplicate elements in either input list are ignored.

  Args:
    expected:  The list we expected.
    actual:  The list we actually got.
  Returns:
    (missing, unexpected)
    missing: items in expected that are not in actual.
    unexpected: items in actual that are not in expected.
  """
  i = j = 0
  missing = []
  unexpected = []
  while True:
    try:
      e = expected[i]
      a = actual[j]
      if e < a:
        missing.append(e)
        i += 1
        while expected[i] == e:
          i += 1
      elif e > a:
        unexpected.append(a)
        j += 1
        while actual[j] == a:
          j += 1
      else:
        i += 1
        try:
          while expected[i] == e:
            i += 1
        finally:
          j += 1
          while actual[j] == a:
            j += 1
    except IndexError:
      missing.extend(expected[i:])
      unexpected.extend(actual[j:])
      break
  return missing, unexpected


def _are_both_of_integer_type(a, b):
  # type: (object, object) -> bool
  return isinstance(a, int) and isinstance(b, int)


def _are_both_of_sequence_type(a, b):
  # type: (object, object) -> bool
  return isinstance(a, abc.Sequence) and isinstance(
      b, abc.Sequence) and not isinstance(
          a, _TEXT_OR_BINARY_TYPES) and not isinstance(b, _TEXT_OR_BINARY_TYPES)


def _are_both_of_set_type(a, b):
  # type: (object, object) -> bool
  return isinstance(a, abc.Set) and isinstance(b, abc.Set)


def _are_both_of_mapping_type(a, b):
  # type: (object, object) -> bool
  return isinstance(a, abc.Mapping) and isinstance(
      b, abc.Mapping)


def _walk_structure_for_problems(a, b, aname, bname, problem_list):
  """The recursive comparison behind assertSameStructure."""
  if type(a) != type(b) and not (  # pylint: disable=unidiomatic-typecheck
      _are_both_of_integer_type(a, b) or _are_both_of_sequence_type(a, b) or
      _are_both_of_set_type(a, b) or _are_both_of_mapping_type(a, b)):
    # We do not distinguish between int and long types as 99.99% of Python 2
    # code should never care.  They collapse into a single type in Python 3.
    problem_list.append('%s is a %r but %s is a %r' %
                        (aname, type(a), bname, type(b)))
    # If they have different types there's no point continuing
    return

  if isinstance(a, abc.Set):
    for k in a: