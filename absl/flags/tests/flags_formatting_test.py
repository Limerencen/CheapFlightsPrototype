
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

from absl import flags
from absl.flags import _helpers
from absl.testing import absltest

FLAGS = flags.FLAGS


class FlagsUnitTest(absltest.TestCase):
  """Flags formatting Unit Test."""

  def test_get_help_width(self):
    """Verify that get_help_width() reflects _help_width."""
    default_help_width = _helpers._DEFAULT_HELP_WIDTH  # Save.
    self.assertEqual(80, _helpers._DEFAULT_HELP_WIDTH)
    self.assertEqual(_helpers._DEFAULT_HELP_WIDTH, flags.get_help_width())
    _helpers._DEFAULT_HELP_WIDTH = 10
    self.assertEqual(_helpers._DEFAULT_HELP_WIDTH, flags.get_help_width())
    _helpers._DEFAULT_HELP_WIDTH = default_help_width  # restore

  def test_text_wrap(self):
    """Test that wrapping works as expected.

    Also tests that it is using global flags._help_width by default.
    """
    default_help_width = _helpers._DEFAULT_HELP_WIDTH
    _helpers._DEFAULT_HELP_WIDTH = 10

    # Generate a string with length 40, no spaces
    text = ''
    expect = []
    for n in range(4):
      line = str(n)
      line += '123456789'
      text += line
      expect.append(line)

    # Verify we still break
    wrapped = flags.text_wrap(text).split('\n')
    self.assertEqual(4, len(wrapped))
    self.assertEqual(expect, wrapped)

    wrapped = flags.text_wrap(text, 80).split('\n')
    self.assertEqual(1, len(wrapped))
    self.assertEqual([text], wrapped)

    # Normal case, breaking at word boundaries and rewriting new lines
    input_value = 'a b c d e f g h'
    expect = {1: ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'],
              2: ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'],
              3: ['a b', 'c d', 'e f', 'g h'],
              4: ['a b', 'c d', 'e f', 'g h'],
              5: ['a b c', 'd e f', 'g h'],
              6: ['a b c', 'd e f', 'g h'],
              7: ['a b c d', 'e f g h'],
              8: ['a b c d', 'e f g h'],
              9: ['a b c d e', 'f g h'],
              10: ['a b c d e', 'f g h'],
              11: ['a b c d e f', 'g h'],
              12: ['a b c d e f', 'g h'],
              13: ['a b c d e f g', 'h'],
              14: ['a b c d e f g', 'h'],
              15: ['a b c d e f g h']}
    for width, exp in expect.items():
      self.assertEqual(exp, flags.text_wrap(input_value, width).split('\n'))

    # We turn lines with only whitespace into empty lines
    # We strip from the right up to the first new line
    self.assertEqual('', flags.text_wrap('  '))
    self.assertEqual('\n', flags.text_wrap('  \n  '))
    self.assertEqual('\n', flags.text_wrap('\n\n'))
    self.assertEqual('\n\n', flags.text_wrap('\n\n\n'))
    self.assertEqual('\n', flags.text_wrap('\n '))
    self.assertEqual('a\n\nb', flags.text_wrap('a\n  \nb'))
    self.assertEqual('a\n\n\nb', flags.text_wrap('a\n  \n  \nb'))
    self.assertEqual('a\nb', flags.text_wrap('  a\nb  '))
    self.assertEqual('\na\nb', flags.text_wrap('\na\nb\n'))
    self.assertEqual('\na\nb\n', flags.text_wrap('  \na\nb\n  '))
    self.assertEqual('\na\nb\n', flags.text_wrap('  \na\nb\n\n'))

    # Double newline.
    self.assertEqual('a\n\nb', flags.text_wrap(' a\n\n b'))

    # We respect prefix
    self.assertEqual(' a\n b\n c', flags.text_wrap('a\nb\nc', 80, ' '))
    self.assertEqual('a\n b\n c', flags.text_wrap('a\nb\nc', 80, ' ', ''))