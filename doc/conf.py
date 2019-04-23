# -*- coding: utf-8 -*-
#
# Sphinx configuration file for Quantiphyse documentation

# -- General configuration ------------------------------------------------

source_suffix = ['.rst',]
extensions = ['sphinx.ext.mathjax']
master_doc = 'README'
project = u'Quantiphyse'
copyright = u'2019 University of Oxford'
author = u'Martin Craig, Ben Irving'

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
language = None

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = False

# -- Options for HTML output ----------------------------------------------

import sphinx_rtd_theme
html_theme = "sphinx_rtd_theme"
html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]

# -- Options for LaTeX output ---------------------------------------------

latex_elements = {
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title,
#  author, documentclass [howto, manual, or own class]).
latex_documents = [
    (master_doc, 'quantiphyse.tex', u'quantiphyse Documentation',
     u'Martin Craig, Ben Irving', 'manual'),
]
