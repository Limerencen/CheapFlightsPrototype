
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

"""Unit tests for the XML-format help generated by the flags.py module."""

import enum
import io
import os
import string
import sys
import xml.dom.minidom
import xml.sax.saxutils

from absl import flags
from absl.flags import _helpers
from absl.flags.tests import module_bar
from absl.testing import absltest


class CreateXMLDOMElement(absltest.TestCase):

  def _check(self, name, value, expected_output):
    doc = xml.dom.minidom.Document()
    node = _helpers.create_xml_dom_element(doc, name, value)
    output = node.toprettyxml('  ', encoding='utf-8')
    self.assertEqual(expected_output, output)

  def test_create_xml_dom_element(self):
    self._check('tag', '', b'<tag></tag>\n')
    self._check('tag', 'plain text', b'<tag>plain text</tag>\n')
    self._check('tag', '(x < y) && (a >= b)',
                b'<tag>(x &lt; y) &amp;&amp; (a &gt;= b)</tag>\n')

    # If the value is bytes with invalid unicode:
    bytes_with_invalid_unicodes = b'\x81\xff'
    # In python 3 the string representation is "b'\x81\xff'" so they are kept
    # as "b'\x81\xff'".
    self._check('tag', bytes_with_invalid_unicodes,
                b"<tag>b'\\x81\\xff'</tag>\n")

    # Some unicode chars are illegal in xml
    # (http://www.w3.org/TR/REC-xml/#charsets):
    self._check('tag', u'\x0b\x02\x08\ufffe', b'<tag></tag>\n')

    # Valid unicode will be encoded:
    self._check('tag', u'\xff', b'<tag>\xc3\xbf</tag>\n')


def _list_separators_in_xmlformat(separators, indent=''):
  """Generates XML encoding of a list of list separators.

  Args:
    separators: A list of list separators.  Usually, this should be a
      string whose characters are the valid list separators, e.g., ','
      means that both comma (',') and space (' ') are valid list
      separators.
    indent: A string that is added at the beginning of each generated
      XML element.

  Returns:
    A string.
  """
  result = ''
  separators = list(separators)
  separators.sort()
  for sep_char in separators:
    result += ('%s<list_separator>%s</list_separator>\n' %
               (indent, repr(sep_char)))
  return result


class FlagCreateXMLDOMElement(absltest.TestCase):
  """Test the create_xml_dom_element method for a single flag at a time.

  There is one test* method for each kind of DEFINE_* declaration.
  """

  def setUp(self):
    # self.fv is a FlagValues object, just like flags.FLAGS.  Each
    # test registers one flag with this FlagValues.
    self.fv = flags.FlagValues()

  def _check_flag_help_in_xml(self, flag_name, module_name,
                              expected_output, is_key=False):
    flag_obj = self.fv[flag_name]
    doc = xml.dom.minidom.Document()
    element = flag_obj._create_xml_dom_element(doc, module_name, is_key=is_key)
    output = element.toprettyxml(indent='  ')
    self.assertMultiLineEqual(expected_output, output)

  def test_flag_help_in_xml_int(self):
    flags.DEFINE_integer('index', 17, 'An integer flag', flag_values=self.fv)
    expected_output_pattern = (
        '<flag>\n'
        '  <file>module.name</file>\n'
        '  <name>index</name>\n'
        '  <meaning>An integer flag</meaning>\n'
        '  <default>17</default>\n'
        '  <current>%d</current>\n'
        '  <type>int</type>\n'
        '</flag>\n')
    self._check_flag_help_in_xml('index', 'module.name',
                                 expected_output_pattern % 17)
    # Check that the output is correct even when the current value of
    # a flag is different from the default one.
    self.fv['index'].value = 20
    self._check_flag_help_in_xml('index', 'module.name',
                                 expected_output_pattern % 20)

  def test_flag_help_in_xml_int_with_bounds(self):
    flags.DEFINE_integer('nb_iters', 17, 'An integer flag',
                         lower_bound=5, upper_bound=27,
                         flag_values=self.fv)
    expected_output = (
        '<flag>\n'
        '  <key>yes</key>\n'
        '  <file>module.name</file>\n'
        '  <name>nb_iters</name>\n'
        '  <meaning>An integer flag</meaning>\n'
        '  <default>17</default>\n'
        '  <current>17</current>\n'
        '  <type>int</type>\n'
        '  <lower_bound>5</lower_bound>\n'
        '  <upper_bound>27</upper_bound>\n'
        '</flag>\n')
    self._check_flag_help_in_xml('nb_iters', 'module.name', expected_output,
                                 is_key=True)

  def test_flag_help_in_xml_string(self):
    flags.DEFINE_string('file_path', '/path/to/my/dir', 'A test string flag.',
                        flag_values=self.fv)
    expected_output = (
        '<flag>\n'
        '  <file>simple_module</file>\n'
        '  <name>file_path</name>\n'
        '  <meaning>A test string flag.</meaning>\n'
        '  <default>/path/to/my/dir</default>\n'
        '  <current>/path/to/my/dir</current>\n'
        '  <type>string</type>\n'
        '</flag>\n')
    self._check_flag_help_in_xml('file_path', 'simple_module', expected_output)

  def test_flag_help_in_xml_string_with_xmlillegal_chars(self):
    flags.DEFINE_string('file_path', '/path/to/\x08my/dir',
                        'A test string flag.', flag_values=self.fv)
    # '\x08' is not a legal character in XML 1.0 documents.  Our
    # current code purges such characters from the generated XML.
    expected_output = (
        '<flag>\n'
        '  <file>simple_module</file>\n'
        '  <name>file_path</name>\n'
        '  <meaning>A test string flag.</meaning>\n'
        '  <default>/path/to/my/dir</default>\n'
        '  <current>/path/to/my/dir</current>\n'
        '  <type>string</type>\n'
        '</flag>\n')
    self._check_flag_help_in_xml('file_path', 'simple_module', expected_output)

  def test_flag_help_in_xml_boolean(self):
    flags.DEFINE_boolean('use_gpu', False, 'Use gpu for performance.',
                         flag_values=self.fv)
    expected_output = (
        '<flag>\n'
        '  <key>yes</key>\n'
        '  <file>a_module</file>\n'
        '  <name>use_gpu</name>\n'
        '  <meaning>Use gpu for performance.</meaning>\n'
        '  <default>false</default>\n'
        '  <current>false</current>\n'
        '  <type>bool</type>\n'
        '</flag>\n')
    self._check_flag_help_in_xml('use_gpu', 'a_module', expected_output,
                                 is_key=True)

  def test_flag_help_in_xml_enum(self):
    flags.DEFINE_enum('cc_version', 'stable', ['stable', 'experimental'],
                      'Compiler version to use.', flag_values=self.fv)
    expected_output = (
        '<flag>\n'
        '  <file>tool</file>\n'
        '  <name>cc_version</name>\n'
        '  <meaning>&lt;stable|experimental&gt;: '
        'Compiler version to use.</meaning>\n'
        '  <default>stable</default>\n'
        '  <current>stable</current>\n'
        '  <type>string enum</type>\n'
        '  <enum_value>stable</enum_value>\n'
        '  <enum_value>experimental</enum_value>\n'
        '</flag>\n')
    self._check_flag_help_in_xml('cc_version', 'tool', expected_output)

  def test_flag_help_in_xml_enum_class(self):
    class Version(enum.Enum):
      STABLE = 0
      EXPERIMENTAL = 1

    flags.DEFINE_enum_class('cc_version', 'STABLE', Version,
                            'Compiler version to use.', flag_values=self.fv)
    expected_output = ('<flag>\n'
                       '  <file>tool</file>\n'
                       '  <name>cc_version</name>\n'
                       '  <meaning>&lt;stable|experimental&gt;: '
                       'Compiler version to use.</meaning>\n'
                       '  <default>stable</default>\n'
                       '  <current>Version.STABLE</current>\n'
                       '  <type>enum class</type>\n'
                       '  <enum_value>STABLE</enum_value>\n'
                       '  <enum_value>EXPERIMENTAL</enum_value>\n'
                       '</flag>\n')
    self._check_flag_help_in_xml('cc_version', 'tool', expected_output)

  def test_flag_help_in_xml_comma_separated_list(self):
    flags.DEFINE_list('files', 'a.cc,a.h,archive/old.zip',
                      'Files to process.', flag_values=self.fv)
    expected_output = (
        '<flag>\n'
        '  <file>tool</file>\n'
        '  <name>files</name>\n'
        '  <meaning>Files to process.</meaning>\n'
        '  <default>a.cc,a.h,archive/old.zip</default>\n'
        '  <current>[\'a.cc\', \'a.h\', \'archive/old.zip\']</current>\n'
        '  <type>comma separated list of strings</type>\n'
        '  <list_separator>\',\'</list_separator>\n'
        '</flag>\n')
    self._check_flag_help_in_xml('files', 'tool', expected_output)

  def test_list_as_default_argument_comma_separated_list(self):
    flags.DEFINE_list('allow_users', ['alice', 'bob'],
                      'Users with access.', flag_values=self.fv)
    expected_output = (
        '<flag>\n'
        '  <file>tool</file>\n'
        '  <name>allow_users</name>\n'
        '  <meaning>Users with access.</meaning>\n'
        '  <default>alice,bob</default>\n'
        '  <current>[\'alice\', \'bob\']</current>\n'
        '  <type>comma separated list of strings</type>\n'
        '  <list_separator>\',\'</list_separator>\n'
        '</flag>\n')
    self._check_flag_help_in_xml('allow_users', 'tool', expected_output)

  def test_none_as_default_arguments_comma_separated_list(self):
    flags.DEFINE_list('allow_users', None,
                      'Users with access.', flag_values=self.fv)
    expected_output = (
        '<flag>\n'
        '  <file>tool</file>\n'
        '  <name>allow_users</name>\n'
        '  <meaning>Users with access.</meaning>\n'
        '  <default></default>\n'
        '  <current>None</current>\n'
        '  <type>comma separated list of strings</type>\n'
        '  <list_separator>\',\'</list_separator>\n'
        '</flag>\n')
    self._check_flag_help_in_xml('allow_users', 'tool', expected_output)

  def test_flag_help_in_xml_space_separated_list(self):
    flags.DEFINE_spaceseplist('dirs', 'src libs bin',
                              'Directories to search.', flag_values=self.fv)
    expected_separators = sorted(string.whitespace)
    expected_output = (
        '<flag>\n'
        '  <file>tool</file>\n'
        '  <name>dirs</name>\n'
        '  <meaning>Directories to search.</meaning>\n'
        '  <default>src libs bin</default>\n'
        '  <current>[\'src\', \'libs\', \'bin\']</current>\n'
        '  <type>whitespace separated list of strings</type>\n'
        'LIST_SEPARATORS'
        '</flag>\n').replace('LIST_SEPARATORS',
                             _list_separators_in_xmlformat(expected_separators,
                                                           indent='  '))
    self._check_flag_help_in_xml('dirs', 'tool', expected_output)

  def test_flag_help_in_xml_space_separated_list_with_comma_compat(self):
    flags.DEFINE_spaceseplist('dirs', 'src libs,bin',
                              'Directories to search.', comma_compat=True,
                              flag_values=self.fv)
    expected_separators = sorted(string.whitespace + ',')
    expected_output = (
        '<flag>\n'
        '  <file>tool</file>\n'
        '  <name>dirs</name>\n'
        '  <meaning>Directories to search.</meaning>\n'
        '  <default>src libs bin</default>\n'
        '  <current>[\'src\', \'libs\', \'bin\']</current>\n'
        '  <type>whitespace or comma separated list of strings</type>\n'
        'LIST_SEPARATORS'
        '</flag>\n').replace('LIST_SEPARATORS',
                             _list_separators_in_xmlformat(expected_separators,
                                                           indent='  '))
    self._check_flag_help_in_xml('dirs', 'tool', expected_output)

  def test_flag_help_in_xml_multi_string(self):
    flags.DEFINE_multi_string('to_delete', ['a.cc', 'b.h'],
                              'Files to delete', flag_values=self.fv)
    expected_output = (
        '<flag>\n'
        '  <file>tool</file>\n'
        '  <name>to_delete</name>\n'
        '  <meaning>Files to delete;\n'
        '    repeat this option to specify a list of values</meaning>\n'
        '  <default>[\'a.cc\', \'b.h\']</default>\n'
        '  <current>[\'a.cc\', \'b.h\']</current>\n'
        '  <type>multi string</type>\n'
        '</flag>\n')
    self._check_flag_help_in_xml('to_delete', 'tool', expected_output)

  def test_flag_help_in_xml_multi_int(self):
    flags.DEFINE_multi_integer('cols', [5, 7, 23],
                               'Columns to select', flag_values=self.fv)
    expected_output = (
        '<flag>\n'
        '  <file>tool</file>\n'
        '  <name>cols</name>\n'
        '  <meaning>Columns to select;\n    '
        'repeat this option to specify a list of values</meaning>\n'
        '  <default>[5, 7, 23]</default>\n'
        '  <current>[5, 7, 23]</current>\n'
        '  <type>multi int</type>\n'
        '</flag>\n')
    self._check_flag_help_in_xml('cols', 'tool', expected_output)

  def test_flag_help_in_xml_multi_enum(self):
    flags.DEFINE_multi_enum('flavours', ['APPLE', 'BANANA'],
                            ['APPLE', 'BANANA', 'CHERRY'],
                            'Compilation flavour.', flag_values=self.fv)
    expected_output = (
        '<flag>\n'
        '  <file>tool</file>\n'
        '  <name>flavours</name>\n'
        '  <meaning>&lt;APPLE|BANANA|CHERRY&gt;: Compilation flavour.;\n'
        '    repeat this option to specify a list of values</meaning>\n'
        '  <default>[\'APPLE\', \'BANANA\']</default>\n'
        '  <current>[\'APPLE\', \'BANANA\']</current>\n'
        '  <type>multi string enum</type>\n'
        '  <enum_value>APPLE</enum_value>\n'
        '  <enum_value>BANANA</enum_value>\n'
        '  <enum_value>CHERRY</enum_value>\n'
        '</flag>\n')
    self._check_flag_help_in_xml('flavours', 'tool', expected_output)

  def test_flag_help_in_xml_multi_enum_class_singleton_default(self):
    class Fruit(enum.Enum):
      ORANGE = 0
      BANANA = 1

    flags.DEFINE_multi_enum_class('fruit', ['ORANGE'],
                                  Fruit,
                                  'The fruit flag.', flag_values=self.fv)
    expected_output = (
        '<flag>\n'
        '  <file>tool</file>\n'
        '  <name>fruit</name>\n'
        '  <meaning>&lt;orange|banana&gt;: The fruit flag.;\n'
        '    repeat this option to specify a list of values</meaning>\n'
        '  <default>orange</default>\n'
        '  <current>orange</current>\n'
        '  <type>multi enum class</type>\n'
        '  <enum_value>ORANGE</enum_value>\n'
        '  <enum_value>BANANA</enum_value>\n'
        '</flag>\n')
    self._check_flag_help_in_xml('fruit', 'tool', expected_output)

  def test_flag_help_in_xml_multi_enum_class_list_default(self):
    class Fruit(enum.Enum):
      ORANGE = 0
      BANANA = 1

    flags.DEFINE_multi_enum_class('fruit', ['ORANGE', 'BANANA'],
                                  Fruit,
                                  'The fruit flag.', flag_values=self.fv)
    expected_output = (
        '<flag>\n'
        '  <file>tool</file>\n'
        '  <name>fruit</name>\n'
        '  <meaning>&lt;orange|banana&gt;: The fruit flag.;\n'
        '    repeat this option to specify a list of values</meaning>\n'
        '  <default>orange,banana</default>\n'
        '  <current>orange,banana</current>\n'
        '  <type>multi enum class</type>\n'
        '  <enum_value>ORANGE</enum_value>\n'
        '  <enum_value>BANANA</enum_value>\n'
        '</flag>\n')
    self._check_flag_help_in_xml('fruit', 'tool', expected_output)

# The next EXPECTED_HELP_XML_* constants are parts of a template for
# the expected XML output from WriteHelpInXMLFormatTest below.  When
# we assemble these parts into a single big string, we'll take into
# account the ordering between the name of the main module and the
# name of module_bar.  Next, we'll fill in the docstring for this
# module (%(usage_doc)s), the name of the main module
# (%(main_module_name)s) and the name of the module module_bar
# (%(module_bar_name)s).  See WriteHelpInXMLFormatTest below.
EXPECTED_HELP_XML_START = """\
<?xml version="1.0" encoding="utf-8"?>
<AllFlags>
  <program>%(basename_of_argv0)s</program>
  <usage>%(usage_doc)s</usage>
"""

EXPECTED_HELP_XML_FOR_FLAGS_FROM_MAIN_MODULE = """\
  <flag>
    <key>yes</key>
    <file>%(main_module_name)s</file>
    <name>allow_users</name>
    <meaning>Users with access.</meaning>
    <default>alice,bob</default>
    <current>['alice', 'bob']</current>
    <type>comma separated list of strings</type>
    <list_separator>','</list_separator>
  </flag>
  <flag>
    <key>yes</key>
    <file>%(main_module_name)s</file>
    <name>cc_version</name>
    <meaning>&lt;stable|experimental&gt;: Compiler version to use.</meaning>
    <default>stable</default>
    <current>stable</current>
    <type>string enum</type>
    <enum_value>stable</enum_value>
    <enum_value>experimental</enum_value>
  </flag>
  <flag>
    <key>yes</key>
    <file>%(main_module_name)s</file>
    <name>cols</name>
    <meaning>Columns to select;
    repeat this option to specify a list of values</meaning>
    <default>[5, 7, 23]</default>
    <current>[5, 7, 23]</current>
    <type>multi int</type>
  </flag>
  <flag>
    <key>yes</key>
    <file>%(main_module_name)s</file>
    <name>dirs</name>
    <meaning>Directories to create.</meaning>
    <default>src libs bins</default>
    <current>['src', 'libs', 'bins']</current>
    <type>whitespace separated list of strings</type>
%(whitespace_separators)s  </flag>
  <flag>
    <key>yes</key>
    <file>%(main_module_name)s</file>
    <name>file_path</name>
    <meaning>A test string flag.</meaning>
    <default>/path/to/my/dir</default>
    <current>/path/to/my/dir</current>
    <type>string</type>
  </flag>
  <flag>
    <key>yes</key>
    <file>%(main_module_name)s</file>
    <name>files</name>
    <meaning>Files to process.</meaning>
    <default>a.cc,a.h,archive/old.zip</default>
    <current>['a.cc', 'a.h', 'archive/old.zip']</current>
    <type>comma separated list of strings</type>
    <list_separator>\',\'</list_separator>
  </flag>
  <flag>
    <key>yes</key>
    <file>%(main_module_name)s</file>
    <name>flavours</name>
    <meaning>&lt;APPLE|BANANA|CHERRY&gt;: Compilation flavour.;
    repeat this option to specify a list of values</meaning>
    <default>['APPLE', 'BANANA']</default>
    <current>['APPLE', 'BANANA']</current>
    <type>multi string enum</type>