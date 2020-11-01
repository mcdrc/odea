"""Odea: Open Digital Ethnography Archives toolkit

This python toolkit is designed to operate with living collections of
ethnographic documents, organized using the BagIt archival standard.

The goal is to provide tools for automating the management of archival
documents -- storage, indexing, validation, conversion to distribution formats,
metadata cataloguing -- in ways that allow everything to remain accessible from
the computer file system and open to manipulation with standard tools.

"""


# This library contains three classes:
#
#     :py:class:`odea.Bag`
#         a collection of Items, in BagIt format
#     :py:class:`odea.Item`
#         an individual Item within the collection
#     :py:class:`odea.File`
#         a File on disk, constituting a version of the Item

import jsons #FIXME: Remove this dependency
import json
from dataclasses import dataclass, field
from typing import List
import hashlib
import uuid
import os
import sys
import datetime as dt
from datetime import datetime # needed for the type hint
from fnmatch import fnmatch
import re
import dbm
import subprocess
import tempfile
import shutil
import mimetypes

from bs4 import BeautifulSoup
from PIL import Image
import soundfile
import pathlib
import pkg_resources
import textwrap
import logging
from slugify import slugify

logger = logging.getLogger('odea')
ch = logging.StreamHandler()
ch.setLevel(logging.ERROR)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

#: The subdirectory of the bag containing metadata files for items.
ITEM_METADATA_DIR = 'item_metadata'

#: The subdirectory of the bag containing metadata files for files.
FILE_METADATA_DIR = 'file_metadata'

#: The subdirectory of the bag containing thumbnail images for files.
THUMBS_DIR = 'thumbs'

#: The payload directory of the bag (should always be 'data' for BagIt standard
#: compliance).
DATA_DIR = 'data'

#: The subdirectory directory of the bag in which derivative files will be
#: stored on generation.
DERIV_DIR = os.path.join(DATA_DIR, 'deriv')

#: The subdirectory of the bag in which generated html metadata files will
#: be stored.
HTML_DIR = 'html'

#: Regular expression for matching UUID identifiers in filenames.
RE_UUID = re.compile("[0-F]{8}-[0-F]{4}-[0-F]{4}-[0-F]{4}-[0-F]{12}", re.I)

#: Regular expression for matching hashtags in note fields.
RE_HASHTAG = re.compile(r'(#[\w\d\-_]+)', flags=re.UNICODE)

RE_URL = r'<((http://|https://|mailto:)(.*?))>'

# Algorithms to be used in preparing bag manifests.
# For BagIt standard compliance, this must include sha256 or sha512.
# Available algorithms are: sha1, sha224, sha256, sha384, sha512, blake2b,
# blake2s, and md5.
# DEFAULT_CHECKSUMS = ["sha256", "sha512"]

#: Block size used when reading files for hashing.
HASH_BLOCK_SIZE = 512 * 1024

#: List of metadata terms used in preparing html output for items.
#: These will correspond to the item properties but are listed here in
#: presentation order.
TERMS = [ 'dcmi_type', 'title', 'identifier', 'creator', 'subject', 'contributor', 'coverage', 'date', 'description', 'language', 'publisher', 'relation', 'rights', 'source', 'note']


### TEMPLATES

# #: Odea css. This path is computed from the package location.
# #: The default stylesheet is Bootstrap v5.
# ODEA_CSS = pkg_resources.resource_filename('odea', "static/bootstrap.min.css")

#: Docutils css. This path is computed from the package location.
DOCUTILS_CSS = pkg_resources.resource_filename('odea', "static/docutils_odea.css")

#: Docutils page template. This path is computed from the package location.
#: This template provides a "viewport" meta tag to enable responsive display.
DOCUTILS_TEMPLATE = pkg_resources.resource_filename('odea', "static/docutils_template.txt")

#: Pandoc css. This path is computed from the package location.
PANDOC_CSS = pkg_resources.resource_filename('odea', "static/pandoc_odea.css")

#: Custom CSS to be added to html output (currently bases Bootstrap 5).
CSS = """q::before { content: none; } q::after { content: none; } q{font-style: italic}'"""

#: Template for html page output. Variables passed to the string are {css},
#: {archive}, {title}, {body}, and {license}. Note that the default template
#: expects a Bootstrap stylesheet to be present within the html directory;
#: this needs to be downloaded from <http://v5.getbootstrap.com/>.
HTML_TEMPLATE = """<!doctype html> <html lang="en"> <head> <meta charset="utf-8"> <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no"> <link rel="stylesheet" href="bootstrap.min.css"> <style>{css}</style> <title>{title} - {archive}</title> </head> <body> <nav class="navbar navbar-expand-lg navbar-dark bg-primary"> <div class="container"> <a class="navbar-brand" href="{archive_url}">{archive}</a> </div> </nav> <div class="container py-4"> {nav} <h1>{title}</h1> {body} </div> <footer class="footer mt-5 p-3"> <div class="container"> <p class="text-muted">{page_metadata}</p> <p class="text-muted">{license}</span> </div> </footer> </body> </html>
"""

# FIXME: PDF policy <https://cromwell-intl.com/open-source/pdf-not-authorized.html>
#: Shell command for deriving a thumbnail image from a source file. This will crop the image if it does not fit the bounding box.
CMD_DF_IMG_THUMB = 'convert "{source}[{frame}]" -density 300 -thumbnail 360x360^ -gravity center -extent 360x360 -background white -alpha remove -auto-orient {target}'

#: Shell command for deriving a medium-size image from a source file.
CMD_DF_IMG_MED = 'convert "{source}[{frame}]" -density 300 -resize 800x600\> -background white -alpha remove -auto-orient {target}'

#: Shell command for deriving a large image from a source file.
CMD_DF_IMG_LG = 'convert "{source}[{frame}]" -density 300 -resize 1920x1080\> -background white -alpha remove -auto-orient {target}'

#: Shell command for generating an offline, archival copy of a web document.
#: The input (source file) should be plain-text file containing a single URL or
#: list or URLs.
CMD_PF_WEBARC = 'wget --input-file="{source}" --convert-links --page-requisites --span-hosts --adjust-extension --restrict-file-names=windows --directory-prefix={target}'

#: Shell command for deriving a WAV audio file from a source media file.
CMD_PF_WAV = 'ffmpeg -i "{source}" "{target}"'

#: Shell command for deriving an MP3 audio file from a source media file.
CMD_DF_MP3 = 'ffmpeg -i "{source}" "{target}"'

#: Shell command for deriving a pdf file from a word processor document.
#: This uses LibreOffice, which recognizes OpenDocument and MS-Office documents,
#: spreadsheets, and presentations.
#: Libreoffice does not allow output filename customization, but just writes
#: the target in the current working directory (bag root), so the resulting
#: file must be moved.
CMD_DF_PDF_DOC = 'libreoffice --headless --convert-to pdf "{source}"; filename=$(basename -- "{source}"); mv "${{filename%.*}}.pdf" "{target}"'

#: Shell command for deriving a cropped screenshot from a text document.
#: Input is a file on disk.
# CMD_DF_IMG_SCREENSHOT = 'google-chrome --headless --disable-gpu --screenshot --window-size=1280,1696 {source}; mv screenshot.png {target}'
CMD_DF_IMG_SCREENSHOT = 'xvfb-run -a -- wkhtmltoimage --crop-h 800 --quality 60 "{source}" "{target}"'

CMD_DF_PDF_WKHTML = 'xvfb-run -a -- wkhtmltopdf --print-media-type "{source}" "{target}"'

#: Shell command for deriving a pdf file from a source html document.
#: The input (source file) should be plain-text file containing a single URL or
#: list or URLs.
CMD_DF_PDF_HTML = 'read -r URL < "{source}"; wkhtmltopdf "$URL" "{target}"'

#: Shell command for deriving a full-page screenshot from a source html
#: document.
#: The input (source file) should be plain-text file containing a single URL or
#: list or URLs.
CMD_PF_SCREENSHOT = 'read -r URL < "{source}"; wkhtmltoimage "$URL" "{target}"'

#: Shell command for deriving a cropped screenshot from a source html document.
#: The input (source file) should be plain-text file containing a single URL or
#: list or URLs.
CMD_DF_SCREENSHOT_CROPPED = 'read -r URL < "{source}"; wkhtmltoimage "$URL" --crop-h 800 --quality 60 "{target}"'

#: Shell command for deriving a preservation-format uncompressed TIFF file
#: from a source image.
CMD_PF_TIFF = 'convert -compress none "{source}[{frame}]" "{target}"'

#: Shell command for deriving a pdf version of a vector image (svg)
CMD_DF_PDF_VECTOR = 'inkscape "{source}" --export-pdf="{target}"'

#: Shell command for deriving a "clean" preservation-ready version of a
#: source svg image.
CMD_PF_VECTOR = 'inkscape "{source}" --export-plain-svg="{target}"'

#: Shell command for deriving an mp4 video with h.264 codec from a source
#: video, at the input resolution.
CMD_DF_H264 = 'ffmpeg -loglevel panic -nostdin -i "{source}" -vcodec libx264 -acodec aac -ab 384K -crf 21 -bf 2 -flags +cgop -pix_fmt yuv420p -movflags faststart "{target}"'

#: Shell command for deriving an mp4 video with h.264 codec from a list of
#: source video clips, provided in a plain-text file readable by the ffmpeg
#: concat filter. See <https://ffmpeg.org/ffmpeg-formats.html#concat>.
#: This command is primarily useful for assembling raw video footage from a
#: project, stored archivally as a collection of source clips, into a single
#: file (or virtual "reel") for redistribution.
CMD_DF_H264_CONCAT = 'ffmpeg -loglevel panic -nostdin -f concat -segment_time_metadata 1 -i "{source}" -vcodec libx264 -acodec aac -ab 384K -crf 21 -bf 2 -flags +cgop -pix_fmt yuv420p -movflags faststart "{target}"'

#: Shell command for deriving a 360p webm video from a source video file,
#: for redistribution online or in limited space/bandwidth contexts.
CMD_DF_360P_VP9_400K = 'ffmpeg -loglevel panic -nostdin -i "{source}" -codec:v libvpx-vp9 -b:v 400K -crf 31 -speed 4 -tile-columns 6 -frame-parallel 1 -vf scale=-1:360 -f webm "{target}"'

#: Shell command for deriving a preservation-format video, using the ffv1
#: codec, from a source video file. Warning: the resulting files will be
#: extremely large!
CMD_PF_FFV1 = 'ffmpeg -loglevel panic -nostdin -i "{source}" -vcodec ffv1 -acodec pcm_s16le "{target}"'

# put -ss TIME *before* the input to use keyframe seeking (fast!)
#: Shell command for generating a still image from a source video, given the
#: input video and a time point ("frame"). The time can be expressed either in
#: HH:MM:SS format (e.g., "54:20") or as a number of seconds with optional
#: decimal fraction (e.g., "3260.2").
CMD_DF_IMG_STILL = 'ffmpeg -loglevel panic -nostdin -ss {frame}.0 -i "{source}" -frames:v 1 "{target}"'

#: Shell command for generating a series of still images from a video, one per
#: six seconds.
CMD_DF_IMG_STILLS = 'mkdir {target}; ffmpeg -i "{source}" -vf fps=1/6,scale=-1:360 "{target}/%%05d.jpg"'

#: Shell command to convert ReStructured Text to html via Docutils.
#: The ``--template`` value is obtained from the variable
#: :py:data:`DOCUTILS_TEMPLATE`, which defaults to the file ``/static/
#: docutils_template.txt`` in the odea package.
#: The ``--stylesheet`` value is obtained from the variable
#: :py:data:`DOCUTILS_CSS`, which defaults to the file ``/static/
#: docutils_odea.css`` in the odea package.
CMD_DF_DOCUTILS_HTML = 'rst2html5 --date --smart-quotes=yes --template="' + DOCUTILS_TEMPLATE +'" --stylesheet-path="' + DOCUTILS_CSS + '" "{source}" "{target}"'

#: Shell command to convert Markdown, ReStructured Text, or any other plain-
#: text format to html via Pandoc.
#: The ``-c`` (css) value is obtained from the variable
#: :py:data:`PANDOC_CSS`, which defaults to the file ``/static/
#: pandoc_odea.css`` in the odea package.
CMD_DF_PANDOC_HTML = 'pandoc -o "{target}" -t html5 -c "' + PANDOC_CSS + '" --standalone "{source}"'

NIL_UUID = '0000000-0000-0000-0000-000000000000'

BLANK_IMG = 'data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw=='


def new(path=None, archive=None, title=None):
    """Create a new Bag structure on disk in the current working directory.

    :param path:    Path to a directory in which to create the new Bag.

    :param archive: The name of the archive to which the collection belongs.
                    This will be added to ``bag-info.txt``.

    :param title:   The title of the collection. This will be added to ``bag-
                    info.txt``.

    Odea will abort when creating a Bag, Item, or File object if there is not
    a corresponding BagIt bag structure on disk, either in the current working
    directory or in the path above it. Since all file paths listed in Bag,
    Item, and File metadata are relative to the bag root, the root must be
    identifiable at the time any object is initialized.

    A valid BagIt structure is currently assumed to exist in a directory
    containing:

        1. A file named ``bagit.txt`` (the contents are not currently verified);
        2. A ``data`` subdirectory for payload files.

    This function will create either of these elements, as well as a template
    ``bag-info.txt`` file, if they are missing in the supplied directory path.
    The directory does not need to be empty.

    """

    if not path:
        path = os.getcwd()

    if not os.path.isdir(path):
        logger.error('Cannot create a Bag in directory: {}'.format(path))
        return

    os.chdir(path)

    if not os.path.isfile('bagit.txt'):
        logger.info('Creating bagit.txt')
        with open('bagit.txt', 'w') as bagit_txt:
            bagit_txt.write('BagIt-Version: 1.0\n'
            'Tag-File-Character-Encoding: UTF-8\n')

    if not os.path.isdir(DERIV_DIR):
        logger.info('Creating payload directory')
        os.makedirs(DERIV_DIR) # includes data dir
        os.makedirs(FILE_METADATA_DIR)
        os.makedirs(ITEM_METADATA_DIR)
        os.makedirs(HTML_DIR)

    if not os.path.isfile('bag-info.txt'):
        b = Bag(archive=archive, title=title)
        b.save()

def load_sample_file(filename):
    """Load and return a file from the ``test`` directory as a File object.

    The testing directory within the odea package contains input documents
    in the various formats supported by odea. These are used in the
    docstring examples in this module as inputs for sample commands and
    testing.

    This function loads a file and sets the following File properties:
    :py:data:`File.filename`, :py:data:`File.basename`, :py:data:`File.ext`,
    :py:data:`File.identifier`, :py:data:`File.format`, :py:data:`File.size`, :py:data:`File.sha256`.
    """

    src = pkg_resources.resource_filename('odea', 'test/{}'.format(filename))
    fn = os.path.join(DATA_DIR, filename)
    shutil.copyfile(src, fn)

    f = File(fn)
    f.identifier = NIL_UUID
    f.tag()
    f.rename()
    f.get_size()
    f.get_sha256()
    return f


def test_bag():
    """Create a sample bag for testing purposes.

    This bag is used in the docstring examples throughout this module.
    The bag is created in a temporary directory, so there should be no risk of
    side-effects in testing.

        >>> import odea
        >>> b = odea.test_bag()
        >>> b.title
        'My test bag'
        >>> b.subject
        ['spam', 'eggs']
        >>> b.identifier
        '893cddb6-6d94-4af6-be16-5cbfdb5d70e3'
        >>> print(b.tree())
        ./
            bagit.txt
            data/
                deriv/
            file_metadata/
            html/
            item_metadata/

    """

    # enter temporary directory
    tmp = tempfile.mkdtemp(prefix='odea_')
    os.chdir(tmp)

    new()
    b = Bag()
    b.title = "My test bag"
    b.subject = ["spam", "eggs"]
    b.identifier = '893cddb6-6d94-4af6-be16-5cbfdb5d70e3'
    b.preview = 'path/to/image'
    return b

def is_root(path):
    """Identify whether <path> is a bag root, returning True or False.

    .. seealso:: :py:func:`get_root`
    """

    if not os.path.isdir(path):
        return False
    if not os.path.isfile(os.path.join(path, 'bagit.txt')):
        return False
    if not os.path.isdir(os.path.join(path, 'data')):
        return False
    return True


def get_root(path):
    """Get the bag root, relative to the string <path>. Return the root or None.

    :param path: A relative or absolute filesystem path; the input path will be
                 resolved against the current directory if it is relative. The
                 path does not need to exist on disk.

    The root is resolved equivalent to :py:data:`path` or any parent directory
    thereof that contains both a ``data`` subdirectory and a file
    ``bagit.txt``.

        >>> import odea, os
        >>> b = odea.test_bag()
        >>> root = os.getcwd()
        >>> odea.get_root(root) == root
        True
        >>> d2 = os.path.join(root, 'data', 'foo', 'bar', 'baz')
        >>> os.makedirs(d2)
        >>> os.chdir(d2)
        >>> odea.get_root('.') == root
        True
        >>> odea.get_root('spam/eggs.txt') == root
        True

    If there is no bag in the path, None will be returned:

        >>> odea.get_root('/random/dir/spam.txt') == None
        True

    If there are multiple nested collections, only the lowest-level directory
    will be returned:

        >>> os.chdir(d2)
        >>> odea.new()
        >>> odea.get_root('.') == os.getcwd()
        True

    """

    p = pathlib.Path(path).resolve()

    # test if we are already in the root
    if is_root(str(p)):
        return str(p)

    # return the root from a parent path
    match = os.sep + DATA_DIR
    subpath = str(p).rpartition(match)[0]
    if is_root(subpath):
        return subpath

    return None

def _prettify(html):
    """Run an html string through BeautifulSoup to prettify it.
    """

    bs = BeautifulSoup(html, 'html.parser')
    return bs.prettify()

def _truncate(description, length=200):
    """Make a truncated description for index pages.

    The description truncates on the last full stop under the length limit, so
    very long descriptions should ideally be broken into several sentences.

        >>> import odea
        >>> text = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Curabitur efficitur nunc ante, a finibus elit malesuada nec. Etiam posuere lobortis arcu vitae fringilla."
        >>> odea._truncate(text, length=60)
        'Lorem ipsum dolor sit amet, consectetur adipiscing elit.'

    If there are no periods within the maximum string length, it will be
    truncated to the string length exactly:

        >>> odea._truncate(text, length=20)
        'Lorem ipsum dolor si ...'

    """

    if description is None:
        return ''
    if length == -1 or len(description) <= length:
        return description

    parts = description[:length].rpartition('. ')
    if parts[0] == '': # no period
        return description[:length] + ' ...'
    d = parts[0] + parts[1]
    return d.rsplit(' ', 1)[0]

def _urlize(text):
    # Format a field that is just a bare url
    if text.startswith('http') and not ' ' in text:
        return '<a href="{text}">{text}</a>'.format(text=text)

    # Format urls in angle brackets within a text field
    for m in re.finditer(RE_URL, text):
        url = m.group(1)
        link_text = url
        text = re.sub(m.group(0), '<a href="{}">{}</a>'.format(url, link_text),
                        text)
    return text

def _parse_note(note):
    """Format locators and hashtags in a note."""

    note = re.sub(RE_HASHTAG, '<span class="badge bg-secondary">\\1</span>', note)
    # note = re.sub('"', "&quot;", note)
    return note

def _make_metadata_table(o):
    """Make an html metadata representation of a Bag or Item object,
    using its attributes."""

    out = ['<table class="table">']
    m = [(k, getattr(o, k, '')) for k in TERMS if getattr(o, k)]
    for k, v in m:
        if k in ('title'):
            continue # already printed separately
        if not isinstance(v, list):
            v = [v]

        if k in ('note'):
            # support formatting of hashtags
            v = [_parse_note(note) for note in v]
        v = [_urlize(txt) for txt in v]
        out.append('<tr><th>{}</th><td><p>'.format(k))
        out.append('</p><p>'.join(v))
        out.append('</p></td></tr>')
    out.append('</table>')
    return ''.join(out)

def _isotime(timestamp):
    """Return a timstamp as string in ISO format."""
    t = datetime.fromtimestamp(int(timestamp))
    return t.strftime('%Y-%m-%dT%H:%M:%SZ')

def _get_hash(filename, hashtype):
    """Retrieve the hash of a file, using a hashtype known to hashlib. """
    m = hashlib.new(hashtype)
    if not os.path.isfile(filename):
        return None
    with open(filename, 'rb') as fh:
        while True:
            block = fh.read(HASH_BLOCK_SIZE)
            if not block:
                break
            m.update(block)
    return m.hexdigest()


def _default_items_list():
    """Return an empty list to instantiate a Bag."""
    return list()

def _byte_size(num):
    """Give a human-readable representation of a filesize, in B/KiB/MiB/etc.

        >>> import odea
        >>> odea._byte_size(18223)
        '17.8 KiB'

    """
    if num is None:
        return ''
    if not isinstance(num, int):
        num = int(num)
    suffix='B'
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%3.1f %s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f %s%s" % (num, 'Yi', suffix)

def _generate_uuid():
    """Return a version 4 uuid string."""
    return str(uuid.uuid4())

# tag code borrowed from https://github.com/LibraryOfCongress/bagit-python/
# (CC0 Public Domain)

def _make_tags(metadata, strip_nulls=False):
    """Make a tag file string out of a metadata dict."""

    # Use "TERMS" to sort the metadata, then list everything else
    headers = [t for t in metadata.keys() if t.lower() in TERMS]
    headers.extend([t for t in sorted(metadata.keys())
                        if not t in headers])
    #headers = sorted(metadata.keys())
    tags = list()
    for h in headers:
        values = metadata[h]

        if strip_nulls and values is None or values in ("None", "null"):
            continue

        h = h.lower().replace("_", " ")
        if not isinstance(values, list):
            values = [values]
        for v in values:
            # strip CR, LF and CRLF so they don't mess up the tag file
            # this should not actually be necessary!
            v = re.sub(r"(\r\n)|\n|\r", " ", str(v))
            # Don't break on hyphens because our unwrap function adds a space
            # Breaking URLS across lines hinders grepping
            lines = textwrap.wrap("{}: {}".format(h, v),
                    width=70, subsequent_indent='    ',
                    break_on_hyphens=False,
                    break_long_words=False)
            tags.append('\r\n'.join(lines))
    return '\r\n'.join(tags)

def _load_tag_file(tag_file_name):
    """Parse a BagIt tag file. Return a dict."""

    with open(tag_file_name, "r") as tag_file:
        # Store duplicate tags as list of vals
        # in order of parsing under the same key.
        tags = {}
        for name, value in _parse_tags(tag_file):
            if value in ("None", "null"):
                value = None
            if name not in tags:
                tags[name] = value
                continue
            if not isinstance(tags[name], list):
                tags[name] = [tags[name], value]
            else:
                tags[name].append(value)
        return tags


def _parse_tags(tag_file):
    """Parse a tag file, according to RFC 2822."""

    tag_name = None
    tag_value = None

    # Line folding is handled by yielding values only after we encounter
    # the start of a new tag, or if we pass the EOF.
    for num, line in enumerate(tag_file):
        # Skip over any empty or blank lines.
        if len(line) == 0 or line.isspace():
            continue
        elif line[0].isspace() and tag_value is not None:  # folded line
            # Don't break filenames, etc., which may be longer than 70 chars
            if tag_name in ('filename', 'basename', 'sha512', 'source'):
                tag_value += line.strip()
            # By default, assume lines are wrapped on spaces
            else:
                tag_value += ' ' + line.strip()
        else:
            # Starting a new tag; yield the last one.
            if tag_name:
                yield (tag_name, tag_value.strip())

            if ":" not in line:
                raise BagValidationError( "invalid tag: {}".format(line) )

            parts = line.strip().split(":", 1)
            tag_name = parts[0].strip().lower().replace(" ", "_")
            tag_value = parts[1]

    # Passed the EOF.  All done after this.
    if tag_name:
        yield (tag_name, tag_value.strip())

class File:
    """This is a file on disk."""

    def __init__(self, filename=None, sha512=None, sha256=None, size=None,
            mtime=None, identifier=None, basename=None, format=None, ext=None,
            preview=None, dimensions=None, duration=None, thumb=None):

        #: The filename, including relative directory path from the bag root
        #: (e.g., `data/subdir/file.ext`)
        self.filename = filename

        #: The sha512 hash of the file (hex string)
        self.sha512 = sha512

        #: The sha256 hash of the file (hex string)
        self.sha256 = sha256

        #: The size of the file, in bytes (integer)
        self.size = size

        #: The modification time of the file (datetime object)
        self.mtime = mtime

        #: The unique identifier of the item to which the file belongs,
        #: represented as a UUID string.
        #: The uuid identifier string is included in the filename as a dot-
        #: separated element in the pattern
        #: `<basename>[.<format>][.<uuid>].<ext>`.
        self.identifier = identifier

        #: The basename or "stem" of the filename.
        #: The basename identifier string is included in the filename as a dot-
        #: separated element in the pattern `<basename>[.<format>][.<uuid>].<ext>`.
        self.basename = basename

        #: The format of the file.
        #: The format identifier string is included in the filename as a dot-
        #: separated element in the pattern
        #: `<basename>[.<format>][.<uuid>].<ext>`.
        #: When generated by odea, this may be `src` for a source file, `df-
        #: <type>` for a distribution copy, or `pf-<type>` for an archival
        #: preservation copy. Available formats for derivative files correspond
        #: to the shell scripts listed in odea.templates.
        self.format = format

        #: The filename extension
        self.ext = ext

        #: Path to a thumbnail image representing the file.
        self.thumb = thumb

        #: Path to a medium-sized image representing the file.
        self.preview = preview

        #: Dimensions of an image or video
        self.dimensions = dimensions

        #: Duration of a video or audio file
        self.duration = duration


    def __post_init__(self):
        """ Test if this is actually a bag on disk; if not, abort."""
        root = get_root(self.filename)
        if root is None:
            sys.exit("Unable to enter bag root")
        os.chdir(root)

    def __str__(self):
        attrs = vars(self)
        return str(attrs)

    # use setters for the hashes so that we can include them as
    # properties in the object signature, to ensure they will be added
    # to the serialized output

    def get_checksum(self, alg='sha512'):
        """Calculate the hash for a file.

        :param alg: Supported algorithms are "sha256" and "sha512".

        .. seealso:: :py:meth:`get_sha256`, :py:meth:`get_sha512`.

        """

        if 'sha256' in alg:
            return self.get_sha256()
        if 'sha512' in alg:
            return self.get_sha512()

    def get_sha256(self):
        """Calculate the sha256 hash of the file.

        An empty file returns None:

            >>> import odea
            >>> b = odea.test_bag()
            >>> f = odea.load_sample_file('test_plain-text.txt')

        If the file exists, the hash should be returned and written to
        the :py:attr:`sha256` property:

            >>> f.get_sha256()
            '92b772380a3f8e27a93e57e6deeca6c01da07f5aadce78bb2fbb20de10a66925'
            >>> f.sha256
            '92b772380a3f8e27a93e57e6deeca6c01da07f5aadce78bb2fbb20de10a66925'

        """

        self.sha256 = _get_hash(self.filename, 'sha256')
        return self.sha256

    def get_sha512(self):
        """Calculate the sha512 hash of the file and save to the
        :py:attr:`sha512` property. This value should be persisted to the file
        manifest-sha512.txt.

            >>> import odea
            >>> b = odea.test_bag()
            >>> f = odea.load_sample_file('test_plain-text.txt')

        If the file exists, the hash should be returned and written to
        the :py:attr:`sha512` property:

            >>> f.get_sha512() # doctest: +ELLIPSIS
            '9751ea443fd632e147831566ccb822482220188993cd1269edbe98d2e2d69...'

        """

        self.sha512 = _get_hash(self.filename, 'sha512')
        return self.sha512

    def json(self):
        """Return a json string representing the File.

        Null values are not included in the output.

            >>> import odea
            >>> b = odea.test_bag()
            >>> f = odea.load_sample_file('test_plain-text.txt')
            >>> print(json.dumps(json.loads(f.json()), indent=4))
            {
                "basename": "data/test_plain-text",
                "ext": "txt",
                "filename": "data/test_plain-text.SRC.0000000-0000-0000-0000-000000000000.txt",
                "format": "SRC",
                "sha256": "92b772380a3f8e27a93e57e6deeca6c01da07f5aadce78bb2fbb20de10a66925",
                "size": 15,
                "uuid": "0000000-0000-0000-0000-000000000000"
            }

        """
        return jsons.dumps(self, strip_nulls=True)

    def get_mtime(self):
        """Return the mtime of a file on disk and set the :py:attr:`mtime`
        property.

        If the file does not exist, nothing is returned:

            >>> import odea
            >>> b = odea.test_bag()
            >>> spam = os.path.join('data', 'spam.txt')
            >>> f = odea.File(spam)
            >>> f.get_mtime() == None
            >>> True

            >>> open(spam, 'a').close()
            >>> os.utime(spam,(1330712280, 1330712292))
            >>> f.get_mtime() == f.mtime
            True
            >>> f.mtime
            '2012-03-02T12:18:12Z'

        """
        if not os.path.isfile(self.filename):
            return None
        self.mtime = _isotime(os.stat(self.filename).st_mtime)
        return self.mtime

    def get_img_dimensions(self):
        """Set and return the dimensions of an image file.

            >>> import odea
            >>> b = odea.test_bag()
            >>> f = odea.load_sample_file('test_img_jpeg.jpg')
            >>> f.get_img_dimensions()
            '2835x4289'

        Nothing will happen if the image dimensions cannot be determined:

            >>> f = odea.load_sample_file('test_plain-text.txt')
            >>> f.get_img_dimensions() == None
            True

        """

        try:
            im = Image.open(self.filename)
            width, height = im.size
        except:
            logging.error('Could not retrieve image dimensions')
            return None
        self.dimensions = '{}x{}'.format(width, height)
        return self.dimensions

    def get_audio_duration(self):
        """Set and return the duration of an audio file.

            >>> import odea
            >>> b = odea.test_bag()
            >>> f = odea.load_sample_file('test_wav_sound.wav')
            >>> f.get_audio_duration()
            3.0

        Nothing will happen if the sound file cannot be read:

            >>> f = odea.load_sample_file('test_plain-text.txt')
            >>> f.get_audio_duration() == None
            True

        """
        # https://stackoverflow.com/a/41617943
        # Install: https://github.com/bastibe/SoundFile

        try:
            a = soundfile.SoundFile(self.filename)
        except:
            logging.error('Could not load sound file')
            return None
        self.duration = len(a) / a.samplerate
        return self.duration

    def get_video_duration(self):
        """Set and return the duration of a video file.

            >>> import odea
            >>> b = odea.test_bag()
            >>> f = odea.load_sample_file('test_video.mp4')
            >>> f.get_audio_duration()
            3.0

        Nothing will happen if the sound file cannot be read:

            >>> f = odea.load_sample_file('test_plain-text.txt')
            >>> f.get_video_duration() == None
            True

        """

        from moviepy.editor import VideoFileClip
        clip = VideoFileClip(self.filename)
        self.duration = clip.duration
        logger.info("Duration: {}".format(self.duration))

        return self.duration


    def get_size(self):
        """Return the size of a file on disk and set the :py:attr:`size`
        property.

            >>> import odea
            >>> b = odea.test_bag()
            >>> f = odea.load_sample_file('test_img_jpeg.jpg')
            >>> f.get_size()
            3506068

        """
        if not os.path.isfile(self.filename):
            return None
        self.size = os.path.getsize(self.filename)
        return self.size

    def get_uuid(self):
        """Retrieve and set the uuid property for a file.

        If the :py:attr:`uuid` property is set, it will be returned.
        Otherwise, the filename will be scanned for a matching uuid,
        using the regular expression :py:data:`RE_UUID`.

        >>> import odea, os
        >>> b = odea.test_bag()
        >>> id = '48342ee3-9080-407e-9862-12ce05143499'
        >>> spam = os.path.join('data', 'spam.{}.txt'.format(id))
        >>> open(spam, 'w').close()
        >>> f = odea.load_file(spam)
        >>> f.identifier == id
        True
        >>> del f.identifier
        >>> f.identifier == id
        False
        >>> f.get_uuid() == id == f.identifier
        True

        """

        if not self.identifier:
            try:
                self.identifier = re.findall(RE_UUID, self.filename)[-1]
            except IndexError:
                self.identifier = _generate_uuid()
        return self.identifier

    def tag(self, _uuid=None):
        """Tag a filename with a UUID and update the File properties.

        This operation does not actually rename files on disk.

            >>> import odea
            >>> b = odea.test_bag()
            >>> f = odea.load_sample_file('test_plain-text.txt')
            >>> f.tag(_uuid=NIL_UUID)
            'data/test_plain-text.SRC.0000000-0000-0000-0000-000000000000.txt'

        The tagging operation should correctly set the following attributes:
        :py:data:`File.filename`, :py:data:`File.basename`, :py:data:`File.ext`,
        :py:data:`File.identifier`, and :py:data:`File.format`.

            >>> a = 'data/test.file.many.parts.txt'
            >>> b = 'data/a.b.0000000-0000-0000-0000-000000000000.c.d.txt'
            >>> c = 'data/test-file-no-extension'
            >>> d = 'data/test-file.SRC.txt'
            >>> f = {}
            >>> for fn in [a, b, c, d]:
            ...     open(fn, 'w').close()
            ...     f[fn] = odea.File(filename=fn)
            ...     o = f[fn].tag(_uuid=odea.NIL_UUID)

            >>> f[a].filename
            'data/test.file.many.parts.txt'
            >>> f[a].basename
            'data/test'
            >>> f[a].ext
            'txt'
            >>> f[a].identifier
            '0000000-0000-0000-0000-000000000000'
            >>> f[a].format
            'file.many.parts'

            >>> f[b].filename
            'data/a.b.0000000-0000-0000-0000-000000000000.c.d.txt'
            >>> f[b].basename
            'data/a'
            >>> f[b].ext
            'c.d.txt'
            >>> f[b].identifier
            '0000000-0000-0000-0000-000000000000'
            >>> f[b].format
            'b'

            >>> f[c].filename
            'data/test-file-no-extension'
            >>> f[c].basename
            'data/test-file-no-extension'
            >>> f[c].ext
            ''
            >>> f[c].identifier
            '0000000-0000-0000-0000-000000000000'
            >>> f[c].format
            'SRC'

            >>> f[d].filename
            'data/test-file.SRC.txt'
            >>> f[d].basename
            'data/test-file'
            >>> f[d].ext
            'txt'
            >>> f[d].identifier
            '0000000-0000-0000-0000-000000000000'
            >>> f[d].format
            'SRC'

        """

        if _uuid:
            self.identifier = _uuid
        else:
            self.get_uuid() # set uuid property
        self.get_filename_parts() # retrieve & set basename and ext properties
        if not self.format:
            self.format = 'SRC'
        return self.filename

    def slug(self):
        """Return a shortened and sanitized form of the file basename.

        The slug removes spaces and special characters from the filename, and
        truncates the basename to 60 characters (this includes the full path
        from the bag root, "data/path/to/file", but NOT the filetype, uuid, and
        extension).
        """

        regex_pattern = r'[^-a-z0-9_/.]+'
        slug = slugify(self.basename, max_length=60, regex_pattern=regex_pattern)
        return slug

    def rename(self):
        """Rename a file on disk, based on its metadata properties.

        The output format is <basename>[.<format>][.<uuid>].<ext>.

        Note that the filename components are not set automatically by the
        :py:class:`File` class on initialization. They can be set by
        :py:meth:`tag` or :py:func:`load_file`.

        >>> import odea
        >>> b = odea.test_bag()
        >>> fn = os.path.join(odea.DATA_DIR, 'test_plain-text.txt')
        >>> f = odea.File(fn)
        >>> open(fn, 'w').close()
        >>> f.identifier = 'b3050922-520f-426e-9a9c-cfe728bd178d'
        >>> f.format = 'sample'
        >>> f.basename = 'data/test_plain-text'
        >>> f.ext = 'rst'
        >>> f.filename
        'data/test_plain-text.txt'
        >>> f.rename() == f.filename
        True
        >>> f.filename
        'data/test_plain-text.sample.b3050922-520f-426e-9a9c-cfe728bd178d.rst'

        """
        parts = [getattr(self, part) for part in ('basename', 'format', 'identifier', 'ext')]
        fn = '.'.join([p for p in parts if p and p is not ''])

        if self.filename == fn:
            logger.info("Filename unchanged: {}".format(fn))
            return self.filename
        try:
            os.rename(self.filename, fn)
        except:
            logger.error("Error renaming {} -> {}".format(self.filename, fn))
            return self.filename

        self.filename = fn
        return self.filename

    def get_filename_parts(self):
        """Populate filename part properties from the filename itself.

        This should be used when importing a new file, as it will override
        any properties that have been set manually. This method is called by
        :py:meth:`tag`, which additionally creates or applies a uuid tag.

        .. seealso:: :py:meth:`tag`
        """

        if self.identifier and self.identifier in self.filename:
            b, ext = self.filename.split(self.identifier)
            base = b.strip('.')
        else:
            # we can have basename and format without UUID.
            base, ext = os.path.splitext(self.filename)
        self.ext = ext.strip('.')

        try:
            self.basename, self.format = base.split('.', 1)
        except ValueError:
            self.format = None
            self.basename = base

    def save(self):
        """Save the File data structure to disk.
        """

        o = os.path.join(FILE_METADATA_DIR,
            '{}.{}.txt'.format(self.identifier, self.format))
        logger.info('Saving to {}'.format(os.getcwd()))

        metadata = _make_tags(vars(self), strip_nulls=True)
        with open(o, 'w') as out:
            out.write(metadata)


    def derive(self, target, ext, frame=None, overwrite=False, target_dir=None):
        """Generate a derivative version of a file. Return the full filename of
        the derived file.

        :param target: Conversion target. Available targets are produced
                       through shell scripts defined in the variables
                       ``odea.CMD_<RULE>``, which can be overwritten or
                       extended. The built-in targets are listed below.

        :param frame:  The page, image, or frame number to use from the input
                       resource. For a multi-image or multi-page document
                       input, ``frame`` is an integer corresponding to the
                       image or page number (starting with '0' for the first
                       image or page). This works with multi-image TIFF files
                       as well as for PDF documents. For video files, the
                       default stills generation command will take an image
                       from the middle of the file if ``frame`` is "0" or not
                       specified, otherwise an image frame will be extracted
                       using the ffmpeg time duration syntax. The following
                       examples are all valid input values for ``frame`` in
                       this context: "55" (55 seconds), "12:03:45" (12 hours, 3
                       minutes, and 45 seconds), or "23.189" (23.189 seconds).

        :param ext:    The extension of the target filename. For some commands
                       this will change the output format (e.g., images
                       processed by Imagemagick can be generated as PNG, JPEG,
                       or another recognized format).

        :param overwrite:
                       If True, overwrite a target file if it already exits.
                       Otherwise simply return the filename.

        :param target_dir:
                       The directory for derivative output. Defaults to
                       :py:data:`DERIV_DIR`, but this can be overridden (e.g,
                       thumbnail images are located in :py:data:`"THUMBS"_DIR`)

        Default targets

           PF_WAV
               A lossless audio file in WAV format.

               Target generated by :py:data:`CMD_PF_WAV`.

           DF_MP3
               A distribution copy of an audio file, in lossy MP3 format.

               Target generated by :py:data:`CMD_DF_MP3`.

           DF_PDF_DOC
               A PDF version of word processor documents (text, spreadsheet,
               etc.)

               Target generated by :py:data:`CMD_DF_PDF_DOC`.

           DF_PDF_HTML
               For web documents given using a "url" file, this will be a PDF
               corresponding to the print version of the resource.

               Target generated by :py:data:`CMD_DF_PDF_HTML`.

           DF_IMG_THUMB
              A thumbnail image (currently 360x360).

              Target generated by :py:data:`CMD_DF_THUMB_IMG`.

           DF_IMG_MED
               A medium-sized image (currently 800x600).

               Target generated by :py:data:`CMD_DF_IMG_MED`.

           DF_IMG_LG
               A large-scale image (1920x1080).

               Target generated by :py:data:`CMD_DF_IMG_LG`.

           PF_FFV1
               A lossless video, using the FFV1 codec.
               (Note that the file sizes are extremely large!)

               Target generated by :py:data:`CMD_PF_FFV1`.

           DF_360P_VP9_400K
               A distribution copy of a video, reduced to 360p resolution in webm format using the VP9 codec.

               Target generated by :py:data:`CMD_DF_360P_VP9_400K`.

           DF_H264
               A distribution copy of the video optimized for upload to video
               hosting services such as YouTube, Vimeo, or Internet Archive.
               With the default command the video is not scaled, but the
               bitrate may be reduced from the source file and the moov atom
               will be placed at the beginning of the file in order to enable
               streaming.

               Target generated by :py:data:`CMD_DF_H264`.

           DF_H264_CONCAT
               The same as "DF_H264", but generated from an ffconcat list. All
               the clips in the source directory, as referenced by the
               "df-concat-list" file, will be assembled to create unified
               derivatives; thus the file "<project-name>.df-h264.<uuid>.mp4"
               will be a single video that could include all the footage from
               the "<project-name>.dir" directory, and subsequent derivatives
               can be created from concatenated video.

               Target generated by :py:data:`CMD_DF_H264_CONCAT`.

           PF_WEBARC
               The "web archive" is a directory containing a downloaded copy of
               the resource specified in a URL file, along with any other
               resources needed in order to display that resource (e.g.,
               embedded images, stylesheets, or fonts). Links to the associated
               resources are converted to relative hyperlinks in order to make
               the resource viewable locally, but are otherwise unchanged.

               Target generated by :py:data:`CMD_PF_WEBARC`.

           PF_SCREENSHOT
               A full screenshot that captures the entire page of a web
               resource, as viewed in a web browser. This is a bitmat image, so
               it can be very large.

               Target generated by :py:data:`CMD_PF_SCREENSHOT`.

           DF_SCREENSHOT_CROPPED
               A cropped screenshot of a web resource, showing the visible part
               of the page without scrolling.

               Target generated by :py:data:`CMD_DF_SCREENSHOT_CROPPED`.

           DF_IMG_STILL
               A still frame from a video.

               Target generated by :py:data:`CMD_DF_IMG_STILL`.

           DF_IMG_STILLS
               A sequence of still images (thumbnails) from a video.

               Target generated by :py:data:`CMD_DF_IMG_STILLS`.

        Examples

            >>> import odea
            >>> b = odea.test_bag()
            >>> c = odea.load_sample_file('test_corrupt-file.jpg')
            >>> c.derive('DF_IMG_MED', 'png')

            >>> f1 = odea.load_sample_file('test_wav_sound.wav')
            >>> d1 = f1.derive('DF_MP3', 'mp3')
            >>> fd1 = odea.File(d1)
            >>> fd1.filename
            'data/deriv/test_wav_sound.df-mp3.0000000-0000-0000-0000-000000000000.mp3'

            >>> f2 = odea.load_sample_file('test_url.urls')
            >>> d2a = f2.derive('DF_PDF_HTML', 'pdf')
            >>> d2b = f2.derive('PF_WEBARC', 'dir')
            >>> d2c = f2.derive('PF_SCREENSHOT', 'png')
            >>> print(b.tree())
            ./
                bagit.txt
                data/
                    test_corrupt-file.SRC.0000000-0000-0000-0000-000000000000.jpg
                    test_url.SRC.0000000-0000-0000-0000-000000000000.urls
                    test_wav_sound.SRC.0000000-0000-0000-0000-000000000000.wav
                    deriv/
                        test_url.df-pdf-html.0000000-0000-0000-0000-000000000000.pdf
                        test_url.pf-screenshot.0000000-0000-0000-0000-000000000000.png
                        test_wav_sound.df-mp3.0000000-0000-0000-0000-000000000000.mp3
                        test_url.pf-webarc.0000000-0000-0000-0000-000000000000.dir/
                            commons.wikimedia.org/
                                w/
                                    index.php@title=File%3A1913_Gandan_Monastery_in_Khuree.jpg&oldid=359804693.html
                            example.net/
                                index.html
                file_metadata/
                html/
                item_metadata/

            >>> f3 = odea.load_sample_file('test_img_jpeg.jpg')
            >>> d3 = f3.derive('DF_IMG_MED', 'png')
            >>> fd3 = odea.File(d3)
            >>> f3.get_img_dimensions()
            '2835x4289'
            >>> fd3.get_img_dimensions()
            '397x600'

        """
        if not getattr(self, 'basename', None):
            logging.error('No basename is set for the input file.')
            return

        if not target_dir:
            target_dir = DERIV_DIR
        if not frame:
            frame = 0

        basename = os.path.join(target_dir, os.path.basename(self.basename))
        target_fn = "{}.{}.{}.{}".format(basename,
                    target.lower().replace('_','-'), self.identifier, ext)

        if overwrite is False and os.path.exists(target_fn):
            return target_fn

        cmd_str = globals()['CMD_' + target.upper().replace('-','_')]
        source=self.filename

        cmd = cmd_str.format(
            source=source,
            target=target_fn,
            frame=frame)

        timeout = 30
        if 'ffmpeg' in cmd:
            timeout = 3600 # one hour for videos; the user can cancel manually

        # shell=True required for Windows Subsystem for Linux
        try:
            r = subprocess.run(cmd, shell=True, timeout=timeout)
        except: # TimeoutExpired
            logger.error("Process timed out: {}".format(target))
            return None
        if r.returncode == 0:
            return target_fn
        elif os.path.isfile(target_fn):
            # Error code 1 is returned by some wkhtmltopdf if some
            # resources are inaccessible, even though the image/pdf generation
            # succeeds. If the derivative has successfully been created, just
            # ignore the error. Note this may not be the expected behaviour if
            # the user was trying to update an existing derivative and the
            # command actually failed.
            logger.warning("Conversion error for command: {} (CODE: {})".format(cmd, r.returncode))
            return target_fn
        else:
            logger.error("Conversion failed for command: {} (CODE: {})".format(cmd, r.returncode))
            return None

    def thumbs(self):
        """Generate thumbnail images for the input filename.

        Two thumbnail images are generated and saved to the
        :py:data:`THUMBS_DIR` folder in the Bag root, with 360px and 800px
        widths.

        The thumbnail files are named using the hash of the input filename,
        so will remain available even if the source file is moved or renamed.
        The paths to the generated images are stored in the :py:attr:`thumb`
        and :py:attr:`preview` properties.

            >>> import odea
            >>> b = odea.test_bag()
            >>> f = odea.load_sample_file('test_img_jpeg.jpg')
            >>> f.thumbs()
            ('thumbs/46568651e13bf1416a802075827b67ed-360x256.jpeg', 'thumbs/46568651e13bf1416a802075827b67ed-800x256.jpeg')

        If the file contents change, it is necessary to remove the existing
        thumbnail images before generating a new one. The filenames are
        accessible from the properties :py:attr:`thumb` and :py:attr:`preview`.

            >>> import os
            >>> os.path.isfile(f.thumb)
            True
            >>> os.remove(f.thumb)
            >>> os.path.isfile(f.thumb)
            False
            >>> del f.thumb
            >>> f.thumb == None
            True

        """

        mtype, encoding = mimetypes.guess_type(self.filename)

        if mtype is not None and mtype.startswith('image'):
            f = self
        elif self.ext in ('pdf'):
            f = self
        else:
            # Make sure we have derivatives for non-image files
            if mtype is not None and mtype.startswith('text'):
                # plain, css, html, javascript, xml, csv
                # this can also be called manually
                fn = self.derive('DF_IMG_SCREENSHOT', 'png', overwrite=False)

            elif mtype is not None and mtype.startswith('video'):
                self.get_video_duration()
                frame = int(float(self.duration // 2))
                fn = self.derive('DF_IMG_STILL', 'jpg', frame, overwrite=False)

            elif self.ext in ('doc','docx', 'odt', 'xls', 'xlsx', 'ods'):
                fn = self.derive('DF_PDF_DOC', 'pdf', overwrite=False)
            else:
                return (None, None)

            if fn is None:
                logger.error("Unable to find an image format for {}".format(
                                self.filename))
                return (None, None)
            f = File(fn)
            f.tag()
            f.get_sha256()
            f.get_mtime()
            f.get_size()
            f.save()

        self.thumb = f.derive('DF_IMG_THUMB', 'png', target_dir=THUMBS_DIR, overwrite=False)
        self.preview = f.derive('DF_IMG_MED', 'png', target_dir=THUMBS_DIR, overwrite=False)

        return (self.thumb, self.preview)

    def _html_row(self):
        """Return an html row representing a file metadata, for use in
        tabular index lists."""

        row =  ( '<tr><td><a href="../{filename}">{format}</a></td>'
                          '<td>{size}</td><td>{mtime}</td></tr>' )
        return row.format(
                filename=self.filename,
                format=self.format,
                size=_byte_size(self.size),
                mtime=self.mtime)

class Item:

    def __init__(self, title=None, identifier=None, creator=None, subject=None,
            contributor=None, coverage=None, date=None, description=None,
            language=None, publisher=None, relation=None, rights=None,
            source=None, dcmi_type=None, embed_url=None, note=None):

        #: Identifier for the Item, represented by default as a version 4
        #: UUID hexadecimal string.
        #: This property should normally be set automatically.
        self.identifier = identifier
        if not self.identifier:
            self.identifier = _generate_uuid()

        #: Dublin Core title metadata element for the Item.
        #: Represents a name given to the resource.
        self.title = title

        #: Dublin Core creator metadata element for the Item.
        #: Represents an entity primarily responsible for making the resource.
        #: This property is a list of strings.
        self.creator = creator

        #: Dublin Core contributor metadata element for the Item.
        #: Represents An entity responsible for making contributions to the
        #: resource.
        #: This property is a list of strings.
        self.contributor = contributor

        #: Dublin Core coverage metadata element for the Item.
        #: Represents the spatial or temporal topic of the resource, the spatial
        #: applicability of the resource, or the jurisdiction under which the
        #: resource is relevant.
        self.coverage = coverage

        #: Dublin Core coverage metadata element for the Item.
        #: Represents a point or period of time associated with an event in the
        #: lifecycle of the resource.
        #: The date should be presented in an ISO 8601 string, but type checking
        #: is not enforced.
        self.date = date

        #: Dublin Core description metadata element for the Item.
        #: Represents an account of the resource that may include an abstract, a
        #: table of contents, a graphical representation, or a free-text account of
        #: the resource.
        self.description = description

        #: Dublin Core language metadata element for the Item.
        #: Represents the language of the resource, ideally using RFC 4646 language
        #: codes (e.g., "en" for English, "mn" for Mongolian).
        self.language = language

        #: Dublin Core publisher metadata element for the Item.
        #: Represents an entity responsible for making the resource available.
        self.publisher = publisher

        #: Dublin Core relation metadata element for the Item.
        #: Represents a related resource.
        self.relation = relation

        #: Dublin Core rights metadata element for the Item.
        #: Represents information about rights held in and over the resource.
        #: Typically this will be a copyright statement, license name, or link
        #: to a document providing terms of use.
        self.rights = rights

        #: Dublin Core source metadata element for the Item.
        #: Represents a related resource from which the described resource is
        #: derived.
        self.source = source

        #: Dublin Core subject metadata element for the Item.
        #: Represents the topic of the resource (keyword).
        #: This property is a list of strings.
        self.subject = subject

        #: Type of the Item, represented using the DCMI Type Vocabulary.
        #: Valid types include Event, Image, MovingImage, PhysicalObject,
        #: Software, Sound, StillImage, and Text.
        self.dcmi_type = dcmi_type

        #: Web-accessible URL from which the resource can be retrieved and
        #: displayed as an embedded resource (i.e., as the source of an iframe
        #: or object tag in html). Optional.
        if embed_url:
            self.embed_url = embed_url

        #: Annotation.
        self.note = note

    def __post_init__(self):
        """ Test if this is actually a bag on disk; if not, abort."""
        root = get_root(os.getcwd())
        try:
            os.chdir(root)
        except:
            sys.exit("Unable to enter bag root")

    def __str__(self):
        attrs = vars(self)
        return str(attrs)

    def json(self):
        """Return a json string representing the Bag"""
        # TODO: Docstring
        return jsons.dumps(self, strip_nulls=False)

    def files(self):
        """Return a list of file objects, corresponding to the files on disk
        associated with the Item. The list is generated by matching the
        identifier to tagged files.
        """
        # TODO: Docstring

        # search in data directory and subdirectories
        g = sorted(pathlib.Path('.').glob(
                    'data/**/*.{}.*'.format(self.identifier)))
        return [load_file(str(p)) for p in g]

    def save(self):
        """Save the Item data structure to disk.

            >>> import odea
            >>> b = odea.test_bag()
            >>> i = odea.Item('data/example.txt')
            >>> i.title = 'Example item'
            >>> i.identifier = odea.NIL_UUID
            >>> i.save()
            >>> t = os.path.join(ITEM_METADATA_DIR, '{}.txt'.format(i.identifier))
            >>> with open(t, 'r') as tag_file:
            ...     print(tag_file) # doctest: +ELLIPSIS

        """

        metadata = _make_tags(vars(self))
        o = os.path.join(ITEM_METADATA_DIR,
            '{}.txt'.format(self.identifier))
        with open(o, 'w') as out:
            out.write(metadata)


    def html(self):
        """Return an html Item description string.

        :Example:

            >>> import odea
            >>> b = odea.test_bag()
            >>> i = odea.Item(identifier=odea.NIL_UUID, title='Test item')
            >>> print(i.html()) # doctest: +ELLIPSIS
            <!DOCTYPE doctype html>
            <html lang="en">
             <head>
              <!-- Required meta tags -->
              <meta charset="utf-8"/>
              <meta content="width=device-width, initial-scale=1, shrink-to-fit=no" name="viewport"/>
              <!-- Bootstrap CSS -->
              <link href="https://stackpath.bootstrapcdn.com/bootstrap/4.4.1/css/bootstrap.min.css" rel="stylesheet"/>
              <style>
               .card-columns {column-count: 1;}  @media (min-width: 768px) {.card-columns {column-count: 2;}} @media (min-width: 992px) {.card-columns {column-count: 3;}} .card{max-width:360px}
              </style>
              <title>
               Test item - Digital Archive
              </title>
             </head>
             <body>
              <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
               <div class="container">
                <a class="navbar-brand" href="">
                 Digital Archive
                </a>
               </div>
              </nav>
              <div class="container py-4">
               <h1>
                <small class="text-muted text-uppercase">
                 item /
                </small>
                Test item
               </h1>
               <table class="table">
                <tr>
                 <th>
                  title
                 </th>
                 <td>
                  Test item
                 </td>
                </tr>
                <tr>
                 <th>
                  identifier
                 </th>
                 <td>
                  0000000-0000-0000-0000-000000000000
                 </td>
                </tr>
               </table>
               <h2>
                Files
               </h2>
               <table class="table">
                <tr>
                 <th>
                  file
                 </th>
                 <th>
                  size
                 </th>
                 <th>
                  date modified
                 </th>
                </tr>
               </table>
              </div>
              <footer class="footer mt-5 p-3">
               <div class="container">
                <p class="text-muted">
                 rev. ...
                </p>
                <p class="text-muted">
                 Except where otherwise noted, content on this site is licensed under a
                 <a href="http://creativecommons.org/licenses/by/4.0/" rel="license">
                  Creative Commons Attribution 4.0 International License
                 </a>
                 .
                </p>
               </div>
              </footer>
             </body>
            </html>
            <BLANKLINE>


        """
        b = load_bag()

        body = [ self._html_preview(),
                 self._metadata_table()]
        body.append('<h2>Files</h2>')
        body.append('<table class="table">')
        body.append('<tr><th>file</th><th>size</th><th>date modified</th></tr>')
        body.extend([f._html_row() for f in self.files()])
        body.append('</table>')

        html = HTML_TEMPLATE.format(
                    title=self.title,
                    nav=self._breadcrumbs(),
                    css=CSS,
                    archive_url=b.archive_url,
                    archive=b.archive,
                    body=' '.join(body),
                    page_metadata = 'rev. {}'.format(
                            dt.date.today().strftime("%Y-%m-%d")),
                    license=b.rights
                        )

        return _prettify(html)

    def _breadcrumbs(self):
        b = load_bag() # to obtain the parent collection id

        breadcrumbs = """
        <nav aria-label="breadcrumb">
          <ol class="breadcrumb bg-light px-0 py-0">
            <li class="breadcrumb-item"><a href="../">Archive</a></li>
            <li class="breadcrumb-item"><a href="{}.html">Collection</a></li>
            <li class="breadcrumb-item active" aria-current="page">Item</li>
          </ol>
        </nav>""".format(b.identifier)
        return breadcrumbs

    def _metadata_table(self):
        """Return an html table with item metadata."""
        return _make_metadata_table(self)


    def _html_preview(self):
        if getattr(self, 'embed_url', None):
            return """<div class="embed-responsive embed-responsive-16by9">
                <iframe src="{}" scrolling="no" class="embed-responsive-item"
                allowfullscreen></iframe></div>""".format(self.embed_url)

        src = self.src()
        if src:
            f = load_file(src)
            if getattr(f, 'preview', None):
                return ('<p><img src="../{}" class="img-thumbnail" />'
                        '</p>').format(f.preview)
        return ''

    def _html_row(self):
        """Return an html row representing an item metadata, for use in
        tabular index lists."""
        row = ("""<div class="col"><div class="card h-100">
          {thumb}
          <div class="card-body">
            <h5 class="card-title">{title}</h5>
            {subtitle}
            <p class="card-text">{description}</p>
            <p><small><a href="{identifier}.html" class="stretched-link">{identifier}</a></small></p>
          </div>
        </div></div>""")

        if isinstance(self.description, list):
            description = self.description[0]
        else:
            description = self.description

        return row.format(
            identifier=self.identifier,
            title=self.title,
            subtitle=self._card_dcmi_type(),
            thumb=self._card_thumb(),
            description=_truncate(description)
            )

    def _card_dcmi_type(self):
        if getattr(self, 'dcmi_type', None):
            return '<h6 class="card-subtitle mb-2 text-muted">{}</h6>'.format(self.dcmi_type)
        return ''

    def _card_thumb(self):
        """Return a string corresponding to the item thumb filename."""
        try:
            src = load_file(self.src())
        except:
            return ''
        if src and getattr(src, 'thumb', None):
            return '<img src="../{}" class="card-img-top" />'.format(src.thumb)
        return ''

    def src(self):
        """Return the path to the "SRC" file for the item"""

        g = pathlib.Path('.').glob(
                    '**/*.SRC.{}.*'.format(self.identifier))
        g = list(g)
        try:
            return str(g[0])
        except:
            return None

    def tag_file(self):
        # FIXME: extract from load_item()

        return os.path.join(os.getcwd(), ITEM_METADATA_DIR,
                    '{}.txt'.format(self.identifier))

######## BAG OBJECT ########

class Bag:
    """An abstract instance of a Bag."""

    def __init__(self, archive='odeum', archive_url=None, title=None,
        identifier=None, creator=None, subject=None, contributor=None, coverage=None, date=None, description=None, language=None, publisher=None, relation=None, rights=None, source=None, preview=None, dcmi_type='Collection', note=None):

        #: The name of the archive to which this collection belongs.
        self.archive = archive

        #: Web address (URL) of the archive responsible for this collection.
        self.archive_url = archive_url

        #: Dublin Core title metadata element for the Bag.
        #: Represents a name given to the resource.
        self.title = title

        #: Identifier for the Bag, represented by default as a version 4
        #: UUID hexadecimal string.
        #: This property should normally be set automatically.
        self.identifier = identifier
        if not self.identifier:
            self.identifier = _generate_uuid()

        #: Dublin Core creator metadata element for the Bag.
        #: Represents an entity primarily responsible for making the resource
        #: (i.e., the collection curator).
        self.creator = creator

        #: Dublin Core subject metadata element for the Bag.
        #: Represents the topic of the resource (keyword).
        self.subject = subject

        #: Dublin Core contributor metadata element for the Bag.
        #: Represents an entity responsible for making contributions to the
        #: resource.
        self.contributor = contributor

        #: Dublin Core coverage metadata element for the Bag.
        #: Represents the spatial or temporal topic of the resource, the spatial
        #: applicability of the resource, or the jurisdiction under which the
        #: resource is relevant.
        self.coverage = coverage

        #: Dublin Core coverage metadata element for the Bag.
        #: Represents a point or period of time associated with an event in the
        #: lifecycle of the resource.
        #: The date should be presented in an ISO 8601 string, but type checking
        #: is not enforced.
        self.date = date

        #: Dublin Core description metadata element for the Bag.
        #: Represents an account of the resource that may include an abstract, a
        #: table of contents, a graphical representation, or a free-text
        #: account of the resource.
        self.description = description

        #: Dublin Core language metadata element for the Bag.
        #: Represents the language of the resource, ideally using RFC 4646
        #: language codes (e.g., "en" for English, "mn" for Mongolian).
        self.language = language

        #: Dublin Core publisher metadata element for the Bag.
        #: Represents an entity responsible for making the resource available.
        self.publisher = publisher

        #: Dublin Core relation metadata element for the Bag.
        #: Represents a related resource.
        self.relation = relation

        #: Dublin Core rights metadata element for the Bag.
        #: Represents information about rights held in and over the resource.
        #: Typically this will be a copyright statement, license name, or link
        #: to a document providing terms of use.
        self.rights = rights

        #: Dublin Core source metadata element for the Bag.
        #: Represents a related resource from which the described resource is
        #: derived.
        self.source = source

        #: Path to a file within the Bag that provides a preview image representing
        #: the bag contents.
        self.preview = preview

        #: Type of the Item, represented using the DCMI Type Vocabulary.
        #: The only valid type for a Bag is Collection.
        self.dcmi_type = dcmi_type

        #: Annotation
        self.note = note


    def __post_init__(self):
        """ Test if this is actually a bag on disk; if not, abort."""

        root = get_root(os.getcwd())
        try:
            os.chdir(root)
        except:
            sys.exit("Unable to enter bag root")

    def __str__(self):
        attrs = vars(self)
        return str(attrs)

    def json(self):
        """Return a json string representing the Bag.

            >>> import odea
            >>> b = odea.test_bag()
            >>> print(json.dumps(json.loads(b.json()), indent=4))
            {
                "archive": "odeum",
                "archive_url": "",
                "contributor": null,
                "coverage": null,
                "creator": [],
                "date": null,
                "dcmi_type": "Collection",
                "description": null,
                "identifier": "893cddb6-6d94-4af6-be16-5cbfdb5d70e3",
                "language": null,
                "preview": "path/to/image",
                "publisher": null,
                "relation": null,
                "rights": null,
                "source": null,
                "subject": [
                    "spam",
                    "eggs"
                ],
                "title": "My test bag"
            }
        """
        return jsons.dumps(self, strip_nulls=False)

    def tree(self, path='.'):
        """Print a directory tree representing the bag contents.

        See the documentation for :py:func:`test_bag()` for an example.
        """
        # http://stackoverflow.com/a/9728478/992834
        out = []
        for root, dirs, files in os.walk(path):
            level = root.replace(path, '').count(os.sep)
            indent = ' ' * 4 * (level)
            out.append('{}{}/'.format(indent, os.path.basename(root)))
            subindent = ' ' * 4 * (level + 1)
            for f in files:
                out.append(subindent + f)
        return '\n'.join(out)

    def html(self):
        """Return an html Bag description string.

        :Example:

            >>> import odea
            >>> b = odea.test_bag()
            >>> print(b.html()) # doctest: +ELLIPSIS
            <!DOCTYPE doctype html>
            <html lang="en">
             <head>
              <!-- Required meta tags -->
              <meta charset="utf-8"/>
              <meta content="width=device-width, initial-scale=1, shrink-to-fit=no" name="viewport"/>
              <!-- Bootstrap CSS -->
              <link href="https://stackpath.bootstrapcdn.com/bootstrap/4.4.1/css/bootstrap.min.css"/>
              <style>
               .card-columns {column-count: 1;}  @media (min-width: 768px) {.card-columns {column-count: 2;}} @media (min-width: 992px) {.card-columns {column-count: 3;}} .card{max-width:360px}
              </style>
              <title>
               My test bag - Digital Archive
              </title>
             </head>
             <body>
              <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
               <div class="container">
                <a class="navbar-brand" href="">
                 Digital Archive
                </a>
               </div>
              </nav>
              <div class="container py-4">
               <h1>
                <small class="text-muted text-uppercase">
                 collection /
                </small>
                My test bag
               </h1>
               <p>
                <img class="img-thumbnail" src="path/to/image"/>
               </p>
               <table class="table">
                <tr>
                 <th>
                  title
                 </th>
                 <td>
                  My test bag
                 </td>
                </tr>
                <tr>
                 <th>
                  identifier
                 </th>
                 <td>
                  893cddb6-6d94-4af6-be16-5cbfdb5d70e3
                 </td>
                </tr>
                <tr>
                 <th>
                  subject
                 </th>
                 <td>
                  <ul>
                   <li>
                    spam
                   </li>
                   <li>
                    eggs
                   </li>
                  </ul>
                 </td>
                </tr>
                <tr>
                 <th>
                  dcmi_type
                 </th>
                 <td>
                  Collection
                 </td>
                </tr>
               </table>
               <div class="card-columns">
               </div>
              </div>
              <footer class="footer mt-5 p-3">
               <div class="container">
                <p class="text-muted">
                 rev. ...
                </p>
                <p class="text-muted">
                 Except where otherwise noted, content on this site is licensed under a
                 <a href="http://creativecommons.org/licenses/by/4.0/" rel="license">
                  Creative Commons Attribution 4.0 International License
                 </a>
                 .
                </p>
               </div>
              </footer>
             </body>
            </html>
            <BLANKLINE>

        """

        body = [self._html_preview(), self._metadata_table()]
        body.append('<div class="row row-cols-1 row-cols-md-2 row-cols-lg-3 g-3">')
        body.extend([i._html_row() for i in self.pub_items()])
        body.append('</div>')

        html = HTML_TEMPLATE.format(
                    title=self.title,
                    nav=self._breadcrumbs(),
                    css=CSS,
                    archive=self.archive,
                    archive_url=self.archive_url,
                    body=' '.join(body),
                    page_metadata = 'rev. {}'.format(
                            dt.date.today().strftime("%Y-%m-%d")),
                    license=self.rights
                        )

        return _prettify(html)

    def _breadcrumbs(self):

        breadcrumbs = """
        <nav aria-label="breadcrumb">
          <ol class="breadcrumb bg-light px-0 py-0">
            <li class="breadcrumb-item"><a href="../">Archive</a></li>
            <li class="breadcrumb-item active" aria-current="page">Collection</li>
          </ol>
        </nav>"""
        return breadcrumbs

    def _metadata_table(self):
        """Return an html table with bag metadata."""

        return _make_metadata_table(self)


    def _html_preview(self):
        """Return an html string containing a preview image.

            >>> import odea
            >>> b = odea.test_bag()
            >>> b._html_preview()
            '<p><img src="path/to/image" class="img-thumbnail" /></p>'

        The function should return an empty string if there is no preview
        image set.

            >>> b.preview = None
            >>> b._html_preview()
            ''

        """

        if getattr(self, 'preview', None):
            return '<p><img src="{}" class="img-thumbnail" /></p>'.format(self.preview)
        return ''

    def update_manifest(self, alg='sha512'):
        """Update the Bag manifest.

        :param alg: The algorithm to be used. Defaults to ``sha512``;
                    ``sha256`` can also be used.

        :Example:

            >>> import odea
            >>> b = odea.test_bag()

        Any new file should be added to the manifest.

            >>> spam = os.path.join('data', 'spam.txt')
            >>> with open(spam, 'w') as out:
            ...     out.write('Spam, eggs, bacon, and spam!')
            28
            >>> b.update_manifest()
            >>> with open('manifest-sha512.txt', 'r') as manifest:
            ...     manifest.readlines() # doctest: +ELLIPSIS
            ['6aec3c2caf8a5f9984fd1... data/spam.txt']

        """

        m = []
        g = sorted(pathlib.Path(DATA_DIR).glob('**/*'))
        for p in g:
            if p.is_dir():
                continue
            f = load_file(str(p))
            c = getattr(f, alg, None)
            if c is None:
                c = f.get_checksum(alg)
            m.append('{} {}'.format(c, f.filename))

        with open('manifest-{}.txt'.format(alg), 'w') as manifest:
            manifest.write('\r\n'.join(m))
        return

    def save(self):
        """Save the Bag data structure to disk in plain text format.

        This will be in the file bag-info.txt in the root of the Bag.

            >>> import odea
            >>> b = odea.test_bag()
            >>> b.title = "Modified title"
            >>> b.creator = ['Author 1', 'Author 2']
            >>> b.save()
            >>> with open('bag-info.txt', 'r') as t:
            ...     print(t)
        """

        metadata = _make_tags(vars(self))
        with open('bag-info.txt', 'w') as out:
            out.write(metadata)

    def items(self):
        """Return a list of Item objects for items in the bag.

        Items are retrieved from the tag files stored in the
        :py:data:`ITEM_METADATA_DIR` directory.

            >>> import odea
            >>> b = odea.test_bag()
            >>> i = odea.Item(identifier=odea.NIL_UUID, title='test_item')
            >>> i.save()
            >>> for i in b.items():
            ...     print(i.title)
            test_item

        """
        g = pathlib.Path(ITEM_METADATA_DIR).glob('*.txt')
        items_list = list()
        for p in g:
            item_uuid = re.findall(RE_UUID, str(p))
            items_list.append(load_item(item_uuid[0]))

        return items_list

    def pub_items(self):
        """Return a list of Item objects for published items in the bag.

        This allows the html index to be updated only with items that
        are already included in the :py:data:`HTML_DIR` directory.

            >>> import odea, os
            >>> b = odea.test_bag()
            >>> i = odea.Item(identifier=odea.NIL_UUID, title='test item')
            >>> i.save()
            >>> b.pub_items()
            []
            >>> h = os.path.join(odea.HTML_DIR, '{}.html'.format(odea.NIL_UUID))
            >>> open(h, 'w').close()
            >>> print([x.title for x in b.pub_items()])
            ['test item']

        """
        # sort by uuid
        g = sorted(pathlib.Path(HTML_DIR).glob('*.html'))
        pub = [p.stem for p in g]
        return [i for i in self.items() if i.identifier in pub]

######## CONSTRUCTORS ########

def load_bag():
    """Look for an existing 'bag-info.txt' metadata file and load
    as a Bag object. If no metadata file exists, create a new Bag object."""

    root = get_root(os.getcwd())
    if root is None:
        new()
        root = os.getcwd()
    b = Bag()
    tag_file = os.path.join(root, 'bag-info.txt' )
    if os.path.exists(tag_file):
        tags = _load_tag_file(tag_file)
        for key in tags:
            setattr(b, key, tags[key])
    return b

def load_item(item_uuid):
    """Look for an existing metadata file matching the item uuid and load
    as an Item object. If no metadata file exists, create a new Item object.

    :param item_uuid: The UUID for an item in the archive.
    """

    # TODO: Docstring (see load_file())
    root = get_root(os.getcwd())
    if root is None:
        logger.error("Load item: Could not locate bag root from dir {}".format(
                        os.getcwd() ))
        return None

    tag_file = os.path.join(root, ITEM_METADATA_DIR,
                '{}.txt'.format(item_uuid))

    i = Item(identifier=item_uuid)
    if os.path.exists(tag_file):
        tags = _load_tag_file(tag_file)
        for key in tags:
            setattr(i, key, tags[key])
    return i

def load_file(filename):
    """Look for an existing metadata file matching the filepath and load
    as a File object.

    :param filename: The path to a file in the current Bag.

    The metadata document is matched against the :py:attr:`File.identifier` and
    :py:attr:`File.format` properties; this function will ignore the filepath
    if either of these properties are not present in the filename.

    If no metadata file exists, a new File object will be created and returned.

        >>> import odea
        >>> b = odea.test_bag()
        >>> spam = os.path.join('data', 'spam.txt')
        >>> open(spam, 'w').close()
        >>> f = odea.load_file(spam)
        >>> f # doctest: +ELLIPSIS
        File(filename='data/spam.txt', ...)

    With a filename that doesn't exist:

        >>> f2 = odea.load_file('nonexistent-file.txt')

    With a file that already has metadata:

        >>> id = '2716fe6a-1fba-4dba-b34e-593450f9b975'
        >>> fn = 'data/test.txt'
        >>> tag_file = os.path.join(ITEM_METADATA_DIR, '{}.txt'.format(id))
        >>> with open(tag_file, 'w') as t:
        ...     o = t.write('{{"identifier": {}, "filename": {}"}}'.format(id,fn))
        >>> odea.load_file(fn) # doctest: +ELLIPSIS
        File(filename='data/test.txt', ...)

    """
    root = get_root(filename)
    if root is None:
        logger.error("load file {}: Could not locate bag root".format(filename))
        return None
    os.chdir(root) # necessary for File(), which takes relative path
    filename = str(pathlib.Path(filename).resolve().relative_to(root))
    f = File(filename)
    f.get_uuid()
    if not f.identifier in filename:
        return f
    f.get_filename_parts()
    if f.format:
        tag_file = os.path.join(FILE_METADATA_DIR,
            '{}.{}.txt'.format(f.identifier, f.format))
        if os.path.exists(tag_file):
            tags = _load_tag_file(tag_file)
            for key in tags:
                if key in ('filename', 'basename', 'format', 'ext'):
                    # Don't override info taken from the file path on disk.
                    # Assume that if this differs from the tag file, the file
                    # has been moved or renamed.
                    continue
                setattr(f, key, tags[key])
    return f


def _load_json(json_file):
    """Load a json file"""

    if not os.path.isfile(json_file):
        logger.error('json file could not be located: {}'.format(json_file))
        return None

    try:
        with open(json_file, 'r') as jsonfile:
            j = json.load(jsonfile)
        return jsons.load(j, strict=False)

    except:
        logger.error("Error loading json file: {}".format(json_file))
        return None


## ERRORS

# https://github.com/LibraryOfCongress/bagit-python
class BagError(Exception):
    pass

class BagValidationError(BagError):
    def __init__(self, message, details=None):
        super(BagValidationError, self).__init__()

        if details is None:
            details = []

        self.message = message
        self.details = details

    def __str__(self):
        if len(self.details) > 0:
            details = "; ".join([force_unicode(e) for e in self.details])
            return "%s: %s" % (self.message, details)
        return self.message


if __name__ == "__main__":
    import doctest
    doctest.testmod()
