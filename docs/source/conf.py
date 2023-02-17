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
    'sphinxcontrib.apidoc',  # convert .py source