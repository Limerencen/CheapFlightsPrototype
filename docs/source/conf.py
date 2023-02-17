"""Sphinx config file for https://github.com/abseil/abseil-py."""

import os
import sys

# -- Project information
project = 'Abseil Python Common Libraries'
copyright = '2022, Abseil'  # pylint: disable=redefined-builtin
author = 'The Abseil Authors'

release = ''
version = ''

# -- General configuration

extensions = [
    'sphinx.ext.duration',
    'sphinx.ext.doctest',
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.intersphinx',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.coverage',
    'sphinxcontrib.apidoc',  # convert .py sources to .rst docs.
    'm2r2',                  # for .md files
]

# sphinxcontrib.apidoc vars
apidoc_module_dir = '../../absl'
apidoc_output_dir = '.'
apidoc_toc_file = False
apidoc_excluded_paths = [
    '*/test