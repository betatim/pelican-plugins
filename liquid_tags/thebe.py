"""
Thebe Tag
------------
This is a liquid-style tag to include a dynamic rendering of a jupyter
notebook in a blog post.

Syntax
------
{% thebe filename.ipynb [ cells[start:end] ]%}

The file should be specified relative to the ``notebooks`` subdirectory of the
content directory.  Optionally, this subdirectory can be specified in the
config file:

    NOTEBOOK_DIR = 'notebooks'

The cells[start:end] statement is optional, and can be used to specify which
block of cells from the notebook to include.

Requirements
------------
- Some ...

"""
import re
import os
from functools import partial

from .mdx_liquid_tags import LiquidTags

import IPython
IPYTHON_VERSION = IPython.version_info[0]

if not IPYTHON_VERSION >= 3:
    raise ValueError("IPython version 1.0+ required for thebe tag")

from pygments.formatters import HtmlFormatter

from IPython.nbconvert.filters.highlight import _pygments_highlight
from IPython.nbconvert.exporters import HTMLExporter
from IPython.nbconvert.preprocessors import Preprocessor
from IPython.config import Config

from IPython.utils.traitlets import Integer
from copy import deepcopy


#----------------------------------------------------------------------
# Create a custom preprocessor
class SliceIndex(Integer):
    """An integer trait that accepts None"""
    default_value = None

    def validate(self, obj, value):
        if value is None:
            return value
        else:
            return super(SliceIndex, self).validate(obj, value)


class SubCell(Preprocessor):
    """A transformer to select a slice of the cells of a notebook"""
    start = SliceIndex(0, config=True,
                       help="first cell of notebook to be converted")
    end = SliceIndex(None, config=True,
                     help="last cell of notebook to be converted")

    def preprocess(self, nb, resources):
        nbc = deepcopy(nb)
        if IPYTHON_VERSION < 3:
            for worksheet in nbc.worksheets:
                cells = worksheet.cells[:]
                worksheet.cells = cells[self.start:self.end]
        else:
            nbc.cells = nbc.cells[self.start:self.end]
        
        return nbc, resources

    call = preprocess # IPython < 2.0



#----------------------------------------------------------------------
# Custom highlighter:
#  instead of using class='highlight', use class='highlight-ipynb'
def custom_highlighter(source, language='ipython', metadata=None):
    formatter = HtmlFormatter(cssclass='highlight-ipynb')
    if not language:
        language = 'ipython'
    output = _pygments_highlight(source, formatter, language)
    return output #.replace('<pre>', '<pre class="ipynb">')


#----------------------------------------------------------------------
# Below is the pelican plugin code.
#
SYNTAX = "{% thebe /path/to/notebook.ipynb [ cells[start:end] ] [ language[language] ] %}"
FORMAT = re.compile(r"""^(\s+)?(?P<src>\S+)(\s+)?((cells\[)(?P<start>-?[0-9]*):(?P<end>-?[0-9]*)(\]))?(\s+)?((language\[)(?P<language>-?[a-z0-9\+\-]*)(\]))?(\s+)?$""")


@LiquidTags.register('thebe')
def thebe(preprocessor, tag, markup):
    match = FORMAT.search(markup)
    if match:
        argdict = match.groupdict()
        src = argdict['src']
        start = argdict['start']
        end = argdict['end']
        language = argdict['language']
    else:
        raise ValueError("Error processing input, "
                         "expected syntax: {0}".format(SYNTAX))

    if start:
        start = int(start)
    else:
        start = 0

    if end:
        end = int(end)
    else:
        end = None

    language_applied_highlighter = partial(custom_highlighter,
                                           language=language)

    nb_dir =  preprocessor.configs.getConfig('NOTEBOOK_DIR')
    nb_path = os.path.join('content', nb_dir, src)

    if not os.path.exists(nb_path):
        raise ValueError("File {0} could not be found".format(nb_path))

    # Create the custom notebook converter
    c = Config({'CSSHTMLHeaderTransformer':
                    {'enabled':True, 'highlight_class':'.highlight-ipynb'},
                'SubCell':
                    {'enabled':True, 'start':start, 'end':end}})

    
    template_file = 'liquid_tags/thebehtml_3.tplx'

    if IPYTHON_VERSION >= 2:
        subcell_kwarg = dict(preprocessors=[SubCell])
    else:
        subcell_kwarg = dict(transformers=[SubCell])

    exporter = HTMLExporter(config=c,
                            filters={'highlight2html': language_applied_highlighter},
                            template_file=template_file,
                            template_path=preprocessor.configs.getConfig('PLUGIN_PATHS'),
                            **subcell_kwarg)

    # read and parse the notebook
    with open(nb_path) as f:
        nb_text = f.read()
        if IPYTHON_VERSION < 3:
            nb_json = IPython.nbformat.current.reads_json(nb_text)
        else:
            nb_json = IPython.nbformat.reads(nb_text, as_version=4)

    (body, resources) = exporter.from_notebook_node(nb_json)    

    # this will stash special characters so that they won't be transformed
    # by subsequent processes.
    body = preprocessor.configs.htmlStash.store(body, safe=True)
    return body


#----------------------------------------------------------------------
# This import allows notebook to be a Pelican plugin
from liquid_tags import register
